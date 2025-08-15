"""Attribution utilities (factor & position level).

Simplified methodologies:
- Factor attribution: OLS betas (no intercept) against selected factor ETF daily returns.
- Position contributions: weight_{t-1} * asset_return_t summed over window.

Returns are additive approximations; future enhancements may add alpha and multi-period decomposition.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict
import pandas as pd
import numpy as np

from services.factors import get_factor_returns, DEFAULT_FACTORS


@dataclass
class FactorAttributionResult:
    betas: pd.Series
    factor_cum_returns: pd.Series
    factor_contributions: pd.Series  # absolute contribution (same return units)
    residual: float
    portfolio_cum_return: float

    @property
    def contributions_pct(self) -> pd.Series:
        if self.portfolio_cum_return == 0:
            return self.factor_contributions * 0.0
        return self.factor_contributions / self.portfolio_cum_return * 100.0

    @property
    def residual_pct(self) -> float:
        return (self.residual / self.portfolio_cum_return * 100.0) if self.portfolio_cum_return != 0 else 0.0


def _align_series(port_ret: pd.Series, factor_returns: pd.DataFrame) -> tuple[pd.Series, pd.DataFrame]:
    df = pd.concat([port_ret.rename("portfolio"), factor_returns], axis=1).dropna()
    if df.empty:
        return port_ret.iloc[0:0], factor_returns.iloc[0:0]
    return df["portfolio"], df.drop(columns=["portfolio"])  # type: ignore


def compute_factor_betas(portfolio_returns: pd.Series, factor_returns: pd.DataFrame) -> pd.Series:
    """Compute OLS betas (no intercept) using normal equations."""
    y, X = _align_series(portfolio_returns, factor_returns)
    if y.empty:
        return pd.Series(dtype=float)
    if y.shape[0] < (X.shape[1] + 5):  # minimal observations heuristic
        return pd.Series(dtype=float)
    try:
        XtX = X.to_numpy().T @ X.to_numpy()
        XtY = X.to_numpy().T @ y.to_numpy()
        betas = np.linalg.solve(XtX, XtY)
    except Exception:
        return pd.Series(dtype=float)
    return pd.Series(betas, index=X.columns)


def compute_factor_attribution(history_df: pd.DataFrame, factor_symbols: List[str] | None = None, window: int | None = None) -> FactorAttributionResult | None:
    factor_symbols = factor_symbols or DEFAULT_FACTORS[:3]
    total = history_df[history_df["ticker"] == "TOTAL"].sort_values("date")
    if total.empty or "total_equity" not in total.columns:
        return None
    eq = pd.to_numeric(total["total_equity"], errors="coerce").ffill()
    port_ret = eq.pct_change(fill_method=None).dropna()
    factors = get_factor_returns(factor_symbols)
    if not factors:
        return None
    df_f = pd.DataFrame(factors)
    # Drop columns that are entirely NA
    df_f = df_f.dropna(how="all", axis=1)
    # If after cleaning we have <1 column with at least some data, abort
    valid_cols = [c for c in df_f.columns if df_f[c].dropna().shape[0] >= 5]
    if len(valid_cols) == 0:
        return None
    df_f = df_f[valid_cols]
    if not isinstance(port_ret.index, pd.DatetimeIndex):
        # assume total has same ordering; set index to dates
        port_ret.index = total.loc[port_ret.index, "date"].values  # type: ignore
    port_ret_aligned, factor_ret_aligned = _align_series(port_ret, df_f)
    # Require minimum aligned observations for stability
    if port_ret_aligned.shape[0] < 30 or factor_ret_aligned.shape[0] < 30:
        return None
    if window and port_ret_aligned.shape[0] > window:
        port_ret_aligned = port_ret_aligned.tail(window)
        factor_ret_aligned = factor_ret_aligned.tail(window)
    betas = compute_factor_betas(port_ret_aligned, factor_ret_aligned)
    if betas.empty:
        return None
    factor_cum = (factor_ret_aligned + 1.0).prod() - 1.0
    port_cum = (port_ret_aligned + 1.0).prod() - 1.0
    factor_contrib = betas * factor_cum
    residual = float(port_cum - factor_contrib.sum())
    return FactorAttributionResult(
        betas=betas,
        factor_cum_returns=factor_cum,
        factor_contributions=factor_contrib,
        residual=residual,
        portfolio_cum_return=float(port_cum),
    )


def compute_position_contributions(history_df: pd.DataFrame, window: int = 60) -> pd.DataFrame:
    df = history_df.copy()
    total = df[df["ticker"] == "TOTAL"].sort_values("date")
    if total.empty:
        return pd.DataFrame()
    if window:
        cutoff = total["date"].sort_values().tail(window).min()
        df = df[df["date"] >= cutoff]
        total = total[total["date"] >= cutoff]
    pivot = df[df["ticker"] != "TOTAL"].pivot(index="date", columns="ticker", values="total_value").sort_index()
    if pivot.empty:
        return pd.DataFrame()
    total_eq = pd.to_numeric(total.set_index("date")["total_equity"], errors="coerce").reindex(pivot.index).ffill()
    pivot = pivot.reindex(total_eq.index).ffill()
    returns = pivot.pct_change().fillna(0.0)
    weights = pivot.div(total_eq, axis=0).fillna(0.0)
    # Use bfill() instead of deprecated fillna(method="bfill")
    w_lag = weights.shift(1).bfill().fillna(0.0)
    contrib = (w_lag * returns).sum()
    port_return = (total_eq.pct_change().fillna(0.0) + 1.0).prod() - 1.0
    if port_return == 0:
        contrib_pct = contrib * 0.0
    else:
        contrib_pct = contrib / port_return * 100.0
    out = pd.DataFrame({
        "ticker": contrib.index,
        "contribution_pct": contrib_pct.values,
        "weight_last_pct": (weights.tail(1).T * 100.0).iloc[:, 0].values,
    }).sort_values("contribution_pct", ascending=False)
    return out.reset_index(drop=True)


__all__ = [
    "compute_factor_betas",
    "compute_factor_attribution",
    "compute_position_contributions",
    "FactorAttributionResult",
]
