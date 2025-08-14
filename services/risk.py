from __future__ import annotations

import pandas as pd
import hashlib
import json
from dataclasses import dataclass
from services.benchmark import get_benchmark_series, BENCHMARK_SYMBOL_DEFAULT
from services.risk_free import get_risk_free_rate


@dataclass(slots=True)
class RiskMetrics:
    max_drawdown_pct: float
    rolling_volatility_pct: float
    sharpe_like: float
    concentration_top1_pct: float
    concentration_top3_pct: float
    beta_like: float = 0.0
    sortino_like: float = 0.0
    sharpe: float | None = None  # canonical sharpe (excess mean / std * sqrt(252))


def compute_drawdown(equity_series: pd.Series) -> pd.Series:
    running_max = equity_series.cummax()
    dd = (equity_series / running_max - 1.0) * 100.0
    return dd


def max_drawdown(equity_series: pd.Series) -> float:
    if equity_series.empty:
        return 0.0
    return float(compute_drawdown(equity_series).min())


def rolling_volatility(daily_returns: pd.Series, window: int = 20) -> float:
    if daily_returns.empty:
        return 0.0
    return float(daily_returns.tail(window).std(ddof=0) * 100.0)


def sharpe_like(daily_returns: pd.Series) -> float:
    if daily_returns.empty:
        return 0.0
    mean = daily_returns.mean()
    std = daily_returns.std(ddof=0)
    if std == 0:
        return 0.0
    return float((mean / std) * (252 ** 0.5))


def concentration(portfolio_df: pd.DataFrame) -> tuple[float, float]:
    if portfolio_df.empty:
        return 0.0, 0.0
    if "total_value" not in portfolio_df.columns:
        return 0.0, 0.0
    by_value = portfolio_df[portfolio_df["ticker"] != "TOTAL"]["total_value"].fillna(0)
    total = by_value.sum()
    if total <= 0:
        return 0.0, 0.0
    sorted_vals = by_value.sort_values(ascending=False)
    top1 = sorted_vals.iloc[0] if not sorted_vals.empty else 0.0
    top3 = sorted_vals.head(3).sum()
    return float(top1 / total * 100.0), float(top3 / total * 100.0)


def downside_deviation(daily_returns: pd.Series) -> float:
    if daily_returns.empty:
        return 0.0
    downside = daily_returns[daily_returns < 0]
    if downside.empty:
        return 0.0
    return float((downside.pow(2).mean()) ** 0.5)


def beta_like(asset_returns: pd.Series, benchmark_returns: pd.Series) -> float:
    if asset_returns.empty or benchmark_returns.empty:
        return 0.0
    aligned = pd.concat([asset_returns, benchmark_returns], axis=1).dropna()
    if aligned.shape[0] < 3:
        return 0.0
    cov = aligned.iloc[:, 0].cov(aligned.iloc[:, 1])
    var = aligned.iloc[:, 1].var()
    if var == 0:
        return 0.0
    return float(cov / var)


def sortino_like_ratio(daily_returns: pd.Series) -> float:
    if daily_returns.empty:
        return 0.0
    dd = downside_deviation(daily_returns)
    if dd == 0:
        return 0.0
    return float(daily_returns.mean() / dd * (252 ** 0.5))


def _history_fingerprint(history_df: pd.DataFrame) -> str:
    """Return a stable fingerprint for history to drive caching.

    Uses last 50 TOTAL rows (date,total_equity) plus count of rows to keep it cheap.
    """
    try:
        subset = history_df[history_df["ticker"] == "TOTAL"][[-1]]  # type: ignore[index]
    except Exception:
        pass  # fall through
    try:
        total_rows = history_df[history_df["ticker"] == "TOTAL"]["date"].shape[0]
        tail = (
            history_df[history_df["ticker"] == "TOTAL"]["date"].tail(50).astype(str).tolist()
        )
        eq_tail = (
            history_df[history_df["ticker"] == "TOTAL"]["total_equity"].tail(50).astype(str).tolist()
        )
        payload = {"n": total_rows, "dates": tail, "eq": eq_tail}
        raw = json.dumps(payload, separators=(",", ":"))
        return hashlib.md5(raw.encode("utf-8")).hexdigest()
    except Exception:
        # fallback to id based key (no caching effectively) if something unexpected
        return str(id(history_df))


_risk_cache: dict[str, RiskMetrics] = {}


def clear_risk_cache() -> None:
    _risk_cache.clear()


def compute_risk_block(history_df: pd.DataFrame, use_cache: bool = True, benchmark_symbol: str = BENCHMARK_SYMBOL_DEFAULT) -> RiskMetrics:
    total_rows = history_df[history_df["ticker"] == "TOTAL"].copy()
    if use_cache:
        key = _history_fingerprint(history_df)
        cached = _risk_cache.get(key)
        if cached is not None:
            return cached
    if total_rows.empty:
        return RiskMetrics(0.0, 0.0, 0.0, 0.0, 0.0)
    total_rows = total_rows.sort_values("date")
    eq = pd.to_numeric(total_rows["total_equity"], errors="coerce").dropna()
    daily_ret = eq.pct_change().dropna()
    mdd = max_drawdown(eq)
    vol = rolling_volatility(daily_ret)
    # Risk-free adjustment: subtract daily rf from returns before Sharpe/Sortino
    rf_annual = get_risk_free_rate()
    rf_daily = rf_annual / 252.0
    excess_ret = daily_ret - rf_daily
    sharpe = sharpe_like(excess_ret)
    canonical_sharpe = sharpe  # identical now; kept for forward extensibility
    sortino = sortino_like_ratio(excess_ret)
    # Benchmark integration (fallback to self if not enough data)
    bench_series = get_benchmark_series(benchmark_symbol)
    beta = beta_like(daily_ret, daily_ret)  # default fallback
    if bench_series and not total_rows.empty:
        try:
            bench_df = pd.DataFrame(bench_series)
            bench_df["date"] = pd.to_datetime(bench_df["date"], errors="coerce")
            # Ensure total_rows date is datetime
            tr = total_rows.copy()
            tr["date"] = pd.to_datetime(tr["date"], errors="coerce")
            merged = pd.DataFrame({"date": tr["date"].values, "portfolio": eq.values})
            merged = merged.merge(bench_df, on="date", how="inner")
            merged = merged.sort_values("date")
            bench_ret = pd.to_numeric(merged["close"], errors="coerce").pct_change().dropna()
            port_ret_aligned = pd.to_numeric(merged["portfolio"], errors="coerce").pct_change().dropna()
            if len(bench_ret) >= 5 and len(port_ret_aligned) == len(bench_ret):
                beta = beta_like(port_ret_aligned, bench_ret)
        except Exception:
            pass
    latest_date = total_rows["date"].max()
    latest_positions = history_df[history_df["date"] == latest_date]
    c1, c3 = concentration(latest_positions)
    metrics = RiskMetrics(mdd, vol, sharpe, c1, c3, beta_like=beta, sortino_like=sortino, sharpe=canonical_sharpe)
    if use_cache:
        _risk_cache[key] = metrics  # type: ignore[name-defined]
    return metrics


def attribute_pnl(current_df: pd.DataFrame, prev_df: pd.DataFrame) -> pd.DataFrame:
    if current_df.empty:
        return current_df
    cols_needed = {"ticker", "shares", "buy_price"}
    if not cols_needed.issubset(set(current_df.columns)):
        return current_df
    prev = prev_df.set_index("ticker") if not prev_df.empty else pd.DataFrame().set_index(pd.Index([]))
    cur = current_df.set_index("ticker")
    cur["position_prev"] = prev["shares"] if "shares" in prev.columns else 0.0
    cur["buy_price_prev"] = prev["buy_price"] if "buy_price" in prev.columns else cur["buy_price"]
    cur["pnl_price"] = (cur["buy_price"] - cur["buy_price_prev"]) * cur["position_prev"]
    cur["pnl_position"] = (cur["shares"] - cur["position_prev"]) * cur["buy_price"]
    cur["pnl_total_attr"] = cur["pnl_price"] + cur["pnl_position"]
    return cur.reset_index()


# --- Rolling Beta Utilities ---
def _prepare_returns(equity_series: pd.Series, benchmark_closes: pd.Series) -> pd.DataFrame:
    """Align portfolio and benchmark daily returns for rolling beta.

    Returns DataFrame with columns [port, bench] of aligned percentage returns.
    """
    port_ret = pd.to_numeric(equity_series, errors="coerce").pct_change().rename("port")
    bench_ret = pd.to_numeric(benchmark_closes, errors="coerce").pct_change().rename("bench")
    df = pd.concat([port_ret, bench_ret], axis=1).dropna()
    return df


def compute_rolling_beta_series(equity_series: pd.Series, benchmark_closes: pd.Series, window: int = 60) -> pd.Series:
    """Compute rolling beta time series (window length) of portfolio vs benchmark.

    Beta for each window = Cov(port, bench)/Var(bench). Requires >=3 points in window.
    Returns series indexed by date (end of window) with beta values.
    """
    if window < 3:
        raise ValueError("window must be >=3")
    df = _prepare_returns(equity_series, benchmark_closes)
    if df.empty or df.shape[0] < window:
        return pd.Series(dtype=float)
    betas = []
    idx = []
    port = df["port"].values
    bench = df["bench"].values
    for i in range(window, len(df) + 1):
        sub_p = port[i - window : i]
        sub_b = bench[i - window : i]
        var_b = sub_b.var(ddof=1)
        if var_b == 0:
            beta_val = 0.0
        else:
            # covariance
            cov_pb = ((sub_p - sub_p.mean()) * (sub_b - sub_b.mean())).sum() / (window - 1)
            beta_val = float(cov_pb / var_b)
        betas.append(beta_val)
        idx.append(df.index[i - 1])
    return pd.Series(betas, index=idx, name=f"beta_{window}")


def compute_rolling_betas(equity_series: pd.Series, benchmark_closes: pd.Series, windows: list[int] | None = None) -> dict[int, pd.Series]:
    """Return dict of window->rolling beta series.

    Skips windows without sufficient data.
    """
    if windows is None:
        windows = [30, 60, 90]
    out: dict[int, pd.Series] = {}
    for w in windows:
        try:
            s = compute_rolling_beta_series(equity_series, benchmark_closes, window=w)
            if not s.empty:
                out[w] = s
        except Exception:
            continue
    return out


# --- Drawdown Episodes / Table ---
def compute_drawdown_episodes(equity_series: pd.Series) -> list[dict]:
    """Return list of drawdown episodes with peak, trough, recovery and depth.

    Each episode dict contains:
        peak_date, trough_date, recovery_date (or None), depth_pct (negative),
        days_to_trough, recovery_days, total_days (if recovered), open (bool)
    Episodes are detected by scanning for new peaks; a drawdown starts after a peak
    when equity declines, ends when a new high above the peak is reached.
    The final episode may be open (no recovery yet).
    """
    if equity_series is None or equity_series.empty:
        return []
    s = pd.to_numeric(equity_series, errors="coerce").dropna()
    if s.empty:
        return []
    # Ensure datetime index for durations
    if not isinstance(s.index, pd.DatetimeIndex):
        try:
            s.index = pd.to_datetime(s.index)
        except Exception:
            # fallback: create a synthetic daily index
            s.index = pd.date_range("2000-01-01", periods=len(s), freq="D")
    episodes: list[dict] = []
    peak_val = s.iloc[0]
    peak_date = s.index[0]
    trough_val = peak_val
    trough_date = peak_date
    in_drawdown = False
    for date, val in s.iloc[1:].items():
        if val > peak_val:  # new peak; close any open drawdown
            if in_drawdown:
                episodes.append({
                    "peak_date": peak_date,
                    "trough_date": trough_date,
                    "recovery_date": date,
                    "depth_pct": (trough_val / peak_val - 1) * 100.0,
                    "days_to_trough": (trough_date - peak_date).days,
                    "recovery_days": (date - trough_date).days,
                    "total_days": (date - peak_date).days,
                    "open": False,
                })
                in_drawdown = False
            # reset peak
            peak_val = val
            peak_date = date
            trough_val = val
            trough_date = date
        else:  # below peak
            if val < trough_val:
                trough_val = val
                trough_date = date
                if trough_val < peak_val:
                    in_drawdown = True
    # Handle open drawdown
    if in_drawdown:
        episodes.append({
            "peak_date": peak_date,
            "trough_date": trough_date,
            "recovery_date": None,
            "depth_pct": (trough_val / peak_val - 1) * 100.0,
            "days_to_trough": (trough_date - peak_date).days,
            "recovery_days": None,
            "total_days": None,
            "open": True,
        })
    return episodes


def drawdown_table(equity_series: pd.Series, top_n: int = 5) -> pd.DataFrame:
    """Produce a table (DataFrame) of top N drawdowns by depth.

    Columns: Rank, Peak Date, Trough Date, Recovery Date, Depth (%), Days To Trough,
             Recovery Days, Total Days, Open.
    """
    episodes = compute_drawdown_episodes(equity_series)
    if not episodes:
        return pd.DataFrame(columns=[
            "Rank","Peak Date","Trough Date","Recovery Date","Depth (%)","Days To Trough","Recovery Days","Total Days","Open"
        ])
    df = pd.DataFrame(episodes)
    df = df.sort_values("depth_pct")  # most negative first
    df["Rank"] = range(1, len(df) + 1)
    df = df.head(top_n)
    # Format columns / rename
    df_formatted = pd.DataFrame({
        "Rank": df["Rank"],
        "Peak Date": df["peak_date"].dt.date,
        "Trough Date": df["trough_date"].dt.date,
        "Recovery Date": df["recovery_date"].dt.date if df["recovery_date"].notnull().any() else df["recovery_date"],
        "Depth (%)": df["depth_pct"],
        "Days To Trough": df["days_to_trough"],
        "Recovery Days": df["recovery_days"],
        "Total Days": df["total_days"],
        "Open": df["open"],
    })
    return df_formatted.reset_index(drop=True)
