"""Strategy registry & multi-strategy allocation framework.

Phase 7 addition: provides a lightweight pluggable architecture so multiple
independent alpha / allocation strategies can propose target weights which are
then fused into a single composite target allocation.

Design goals:
  - ZERO side effects on import (safe for tests & UI)
  - Simple in-memory registry (can be swapped later for DB / plugins)
  - Minimal Strategy interface (name + target_weights())
  - Context object passed to every strategy (extensible without breaking API)
  - Deterministic / testable combination logic with clear normalization rules

Public API (stable):
  register_strategy(obj: Strategy)
  get_strategy(name) -> Strategy | None
  list_strategies(active_only=True) -> list[Strategy]
  set_strategy_active(name, active: bool)
  combine_strategy_targets(strategies, strategy_capital=None, normalize=True) -> pd.DataFrame

Target weights contract:
  - Each strategy returns dict[str, float] where floats can be any real numbers.
  - Negative weights are preserved (support long/short) but final normalization
    divides by sum(abs(weights)) if all weights are zero sign-consistent to
    avoid division by zero. For now we use sum of positive weights if any
    positives exist else sum(abs(weights)). This can be revisited when adding
    leverage controls.

Allocation logic:
  1. For each active strategy acquire its raw weight map.
  2. Apply strategy-level capital weight (defaults equal across strategies).
  3. Aggregate per ticker: composite_weight = sum(strategy_capital[s] * w_s_t)
  4. If normalize=True, scale composite weights to sum to 1.0 over positive
     weights (if any); else if all <=0, scale by sum(abs()).
  5. Return DataFrame with columns:
        ticker, composite_weight, raw_weight, strategy, strategy_capital
     plus a pivoted summary (wide form) is trivial for the caller if needed.

Edge cases handled:
  - No strategies registered -> empty DataFrame.
  - Strategy returns empty dict -> skipped.
  - Capital weights not summing to 1 -> auto-normalized (logged via debug).

NOTE: This is an initial scaffold intentionally conservative. Future phases:
  - Add persistence & plugin discovery
  - Add risk overlay (vol targeting / exposure caps)
  - Add execution planner turning deltas into orders.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, Optional, Protocol, List
import logging
import pandas as pd
import json
import sqlite3
from app_settings import settings

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class StrategyContext:
    """Container for data a strategy may need.

    Keep intentionally sparse; call sites can construct on-demand. Additional
    optional attributes can be added without breaking existing strategies.
    """
    as_of: pd.Timestamp
    portfolio: Optional[pd.DataFrame] = None  # current positions snapshot
    prices: Optional[pd.DataFrame] = None     # latest prices (ticker -> price)
    factors: Optional[pd.DataFrame] = None    # factor returns / levels
    extra: dict = field(default_factory=dict) # arbitrary extensions


class Strategy(Protocol):  # structural typing for flexibility
    name: str

    def target_weights(self, ctx: StrategyContext) -> Dict[str, float]:  # pragma: no cover - interface
        """Return raw target weights (not normalized) for tickers.

        Returned weights can be any real numbers. Implementations should be
        fast and side-effect free (purely compute based on context).
        """
        ...


# ---------------- In-memory registry -----------------
_REGISTRY: dict[str, dict] = {}


def register_strategy(strategy: Strategy, active: bool = True, replace: bool = True) -> None:
    """Register a strategy instance.

    Args:
        strategy: Object implementing Strategy protocol.
        active: Whether strategy participates in combination by default.
        replace: If False and name exists, ignore; if True overwrite.
    """
    if not hasattr(strategy, "name"):
        raise ValueError("Strategy must have a 'name' attribute")
    name = str(strategy.name)
    if name in _REGISTRY and not replace:
        return
    _REGISTRY[name] = {"obj": strategy, "active": bool(active)}


def unregister_strategy(name: str) -> None:
    _REGISTRY.pop(name, None)


def get_strategy(name: str) -> Optional[Strategy]:
    entry = _REGISTRY.get(name)
    return entry["obj"] if entry else None


def set_strategy_active(name: str, active: bool) -> None:
    if name in _REGISTRY:
        _REGISTRY[name]["active"] = bool(active)


def list_strategies(active_only: bool = True) -> list[Strategy]:
    if active_only:
        return [v["obj"] for v in _REGISTRY.values() if v.get("active")]
    return [v["obj"] for v in _REGISTRY.values()]


# --------------- Combination / Allocation -----------------
def _normalize_capital_weights(cap_w: Dict[str, float]) -> Dict[str, float]:
    total = sum(max(float(v), 0.0) for v in cap_w.values())
    if total <= 0:
        # fallback equal
        n = len(cap_w)
        return {k: 1.0 / n for k in cap_w} if n else {}
    if abs(total - 1.0) > 1e-9:
        return {k: max(float(v), 0.0) / total for k, v in cap_w.items()}
    return {k: max(float(v), 0.0) for k, v in cap_w.items()}


def combine_strategy_targets(
    strategies: Iterable[Strategy] | None = None,
    ctx: Optional[StrategyContext] = None,
    strategy_capital: Optional[Dict[str, float]] = None,
    normalize: bool = True,
) -> pd.DataFrame:
    """Fuse raw target weight outputs of multiple strategies.

    Returns long-form DataFrame with columns:
        strategy, ticker, raw_weight, strategy_capital, weighted_contribution, composite_weight
    (composite_weight only populated on final rows after aggregation).
    """
    strategies = list(strategies) if strategies is not None else list_strategies()
    if not strategies:
        return pd.DataFrame(columns=["strategy","ticker","raw_weight","strategy_capital","weighted_contribution","composite_weight"])

    if strategy_capital is None:
        strategy_capital = {s.name: 1.0 for s in strategies}
    # Ensure all present; missing -> 0
    for s in strategies:
        strategy_capital.setdefault(s.name, 1.0)
    cw = _normalize_capital_weights(strategy_capital)

    rows: list[dict] = []
    for strat in strategies:
        try:
            raw = strat.target_weights(ctx) if ctx is not None else strat.target_weights(StrategyContext(as_of=pd.Timestamp.utcnow()))
        except Exception as e:  # pragma: no cover - defensive
            logger.error("strategy_compute_failed", extra={"strategy": strat.name, "error": str(e)})
            continue
        if not raw:
            continue
        cap = cw.get(strat.name, 0.0)
        for ticker, weight in raw.items():
            if weight is None:
                continue
            w = float(weight)
            rows.append({
                "strategy": strat.name,
                "ticker": ticker.upper(),
                "raw_weight": w,
                "strategy_capital": cap,
                "weighted_contribution": cap * w,
            })

    if not rows:
        return pd.DataFrame(columns=["strategy","ticker","raw_weight","strategy_capital","weighted_contribution","composite_weight"])

    df = pd.DataFrame(rows)
    agg = df.groupby("ticker", as_index=False)["weighted_contribution"].sum().rename(columns={"weighted_contribution": "composite_weight"})
    # Normalization step
    if normalize and not agg.empty:
        positives = agg[agg["composite_weight"] > 0]
        if not positives.empty:
            total_pos = positives["composite_weight"].sum()
            if total_pos > 0:
                agg["composite_weight"] = agg["composite_weight"] / total_pos
        else:
            # all non-positive -> scale by sum(abs)
            denom = agg["composite_weight"].abs().sum()
            if denom > 0:
                agg["composite_weight"] = agg["composite_weight"] / denom

    out = df.merge(agg, on="ticker", how="left")
    return out


# ---------------- Example reference strategies -----------------
class EqualWeightStrategy:
    """Equal weight across provided tickers in context.portfolio or prices.

    If context.portfolio provided, uses its tickers; else if ctx.prices provided
    uses those; else returns empty.
    """
    name = "equal_weight"

    def target_weights(self, ctx: StrategyContext) -> Dict[str, float]:
        if ctx.portfolio is not None and not ctx.portfolio.empty and "ticker" in ctx.portfolio.columns:
            tickers = sorted(set(ctx.portfolio["ticker"].astype(str)))
        elif ctx.prices is not None and not ctx.prices.empty and "ticker" in ctx.prices.columns:
            tickers = sorted(set(ctx.prices["ticker"].astype(str)))
        else:
            return {}
        if not tickers:
            return {}
        w = 1.0 / len(tickers)
        return {t: w for t in tickers}


class TopNPriceMomentumStrategy:
    """Naive momentum: rank by % change column in ctx.prices, long top N equally."""
    def __init__(self, top_n: int = 5, name: str | None = None):
        self.top_n = int(top_n)
        self.name = name or f"mom_top{self.top_n}"

    def target_weights(self, ctx: StrategyContext) -> Dict[str, float]:
        if ctx.prices is None or ctx.prices.empty:
            return {}
        if "pct_change" not in ctx.prices.columns:
            return {}
        df = ctx.prices.dropna(subset=["pct_change"]).sort_values("pct_change", ascending=False)
        if df.empty:
            return {}
        sel = df.head(self.top_n)["ticker"].astype(str).tolist()
        if not sel:
            return {}
        w = 1.0 / len(sel)
        return {t: w for t in sel}


__all__ = [
    "StrategyContext",
    "Strategy",
    "register_strategy",
    "unregister_strategy",
    "get_strategy",
    "list_strategies",
    "set_strategy_active",
    "combine_strategy_targets",
    "EqualWeightStrategy",
    "TopNPriceMomentumStrategy",
    "compute_allocation_deltas",
    "save_strategy_registry",
    "load_strategy_registry",
    "generate_rebalance_orders",
    "cap_composite_weights",
    "apply_sector_caps",
]


def compute_allocation_deltas(
    portfolio_df: pd.DataFrame,
    combined_alloc_df: pd.DataFrame,
    price_map: dict[str, float],
    total_equity: float,
    weight_col: str = "composite_weight",
) -> pd.DataFrame:
    """Return per-ticker allocation delta given composite targets.

    Args:
        portfolio_df: Current positions with at least columns ticker, shares.
        combined_alloc_df: Output of combine_strategy_targets (long form with composite_weight).
        price_map: Mapping ticker -> latest price.
        total_equity: Equity base for target sizing (uses total position value if <=0).
        weight_col: Column in combined_alloc_df representing final composite weight.

    Returns DataFrame columns:
        ticker, composite_weight, current_weight, delta_weight, price, current_value,
        target_value, value_delta, shares_delta
    """
    if combined_alloc_df.empty:
        return pd.DataFrame(columns=[
            "ticker","composite_weight","current_weight","delta_weight","price","current_value","target_value","value_delta","shares_delta"
        ])
    # Aggregate composite weights (drop duplicates from long form)
    comp = (
        combined_alloc_df.drop_duplicates("ticker")[["ticker", weight_col]]
        .rename(columns={weight_col: "composite_weight"})
    )
    # Current position values
    pf = portfolio_df.copy()
    if pf.empty or "ticker" not in pf.columns or "shares" not in pf.columns:
        pf_vals = pd.DataFrame(columns=["ticker","shares","price","current_value"])
    else:
        pf["ticker"] = pf["ticker"].astype(str).str.upper()
        pf["price"] = pf["ticker"].map(lambda t: float(price_map.get(t, 0.0) or 0.0))
        pf["current_value"] = pf["shares"].astype(float) * pf["price"].astype(float)
        pf_vals = pf[["ticker","shares","price","current_value"]]
    total_pos_val = float(pf_vals["current_value"].sum()) if not pf_vals.empty else 0.0
    equity_base = total_equity if total_equity > 0 else total_pos_val
    if equity_base <= 0:
        # nothing to size against
        comp["current_weight"] = 0.0
        comp["delta_weight"] = comp["composite_weight"]
        comp["price"] = comp["ticker"].map(lambda t: float(price_map.get(t, 0.0) or 0.0))
        comp["current_value"] = 0.0
        comp["target_value"] = comp["composite_weight"] * 0.0
        comp["value_delta"] = comp["target_value"]
        comp["shares_delta"] = 0.0
        return comp
    # Merge current values
    merged = comp.merge(pf_vals, on="ticker", how="left")
    merged["price"] = merged["price"].fillna(merged["ticker"].map(lambda t: float(price_map.get(t, 0.0) or 0.0)))
    merged["current_value"] = merged["current_value"].fillna(0.0)
    merged["current_weight"] = merged["current_value"] / equity_base
    merged["delta_weight"] = merged["composite_weight"] - merged["current_weight"]
    merged["target_value"] = merged["composite_weight"] * equity_base
    merged["value_delta"] = merged["target_value"] - merged["current_value"]
    def _shares(row):
        p = float(row.get("price") or 0.0)
        if p <= 0:
            return 0.0
        return row["value_delta"] / p
    merged["shares_delta"] = merged.apply(_shares, axis=1)
    return merged[[
        "ticker","composite_weight","current_weight","delta_weight","price","current_value","target_value","value_delta","shares_delta"
    ]].sort_values("delta_weight", ascending=False).reset_index(drop=True)


# ---------------- Risk Overlays -----------------
def cap_composite_weights(long_df: pd.DataFrame, max_weight: float | None) -> pd.DataFrame:
    """Apply a max per-ticker composite weight cap to long-form allocation df.

    Args:
        long_df: Output of combine_strategy_targets (long form with composite_weight).
        max_weight: Maximum allowed composite weight (0<max_weight<=1). If None or <=0, returns input.

    Returns a new long-form DataFrame with adjusted composite_weight values.
    Logic:
        1. Extract unique tickers & composite_weight.
        2. Clamp any weight > max_weight.
        3. Re-normalize positive weights to sum to 1 (if any positive) else abs sum.
        4. Merge back onto long form and return.
    """
    if long_df is None or long_df.empty or max_weight is None or max_weight <= 0:
        return long_df
    df = long_df.copy()
    base = df.drop_duplicates("ticker")[["ticker","composite_weight"]].copy()
    base["composite_weight"] = base["composite_weight"].astype(float)
    # Cap first without renorm then adjust remaining slack proportionally
    cap_val = float(max_weight)
    base["capped"] = base["composite_weight"].clip(upper=cap_val)
    # Compute total capped positives
    positives = base[base["capped"] > 0]
    if positives.empty:
        denom = base["capped"].abs().sum()
        if denom > 0:
            base["composite_weight"] = base["capped"] / denom
        else:
            base["composite_weight"] = base["capped"]
    else:
        fixed = positives[positives["composite_weight"] > cap_val]
        variable = positives[positives["composite_weight"] <= cap_val]
        fixed_sum = fixed["capped"].sum()
        variable_raw_sum = variable["capped"].sum()
        remaining = max(1.0 - fixed_sum, 0.0)
        if variable_raw_sum > 0 and remaining > 0:
            scale = remaining / variable_raw_sum
        else:
            scale = 0.0
        def _scaled(row):
            if row["composite_weight"] > cap_val:
                return cap_val
            return row["capped"] * scale
        base["composite_weight"] = base.apply(_scaled, axis=1)
        # final normalize guard (floating error)
        total = base["composite_weight"].sum()
        if total > 0:
            base["composite_weight"] = base["composite_weight"] / total
    base = base.drop(columns=["capped"])
    # Propagate back
    df = df.drop(columns=["composite_weight"]).merge(base, on="ticker", how="left")
    return df


def apply_sector_caps(
    long_df: pd.DataFrame,
    sector_map: dict[str, str] | None,
    sector_cap: float | None,
) -> pd.DataFrame:
    """Cap aggregate composite weight per sector.

    Args:
        long_df: Long-form allocation (must contain ticker & composite_weight).
        sector_map: mapping ticker->sector label.
        sector_cap: max allowed sum of composite weights per sector (0<cap<=1).

    Returns new long-form DataFrame with re-normalized weights if any sector breached.

    Strategy: if any sector sum > cap, clamp sector to cap distributing clamp proportionally
    across its members (keeping their relative proportions), then renormalize all positive
    weights to sum to 1. If sector_map missing entries they are treated as unique sectors.
    """
    if (
        long_df is None
        or long_df.empty
        or sector_map is None
        or not sector_map
        or sector_cap is None
        or sector_cap <= 0
    ):
        return long_df
    df = long_df.copy()
    uniq = df.drop_duplicates("ticker")[["ticker", "composite_weight"]].copy()
    uniq["sector"] = uniq["ticker"].map(lambda t: sector_map.get(str(t).upper(), f"{t}_SEC"))
    # Compute sector sums
    sec_sum = uniq.groupby("sector", as_index=False)["composite_weight"].sum()
    breaches = sec_sum[sec_sum["composite_weight"] > sector_cap]
    if breaches.empty:
        return long_df
    # Apply caps
    # For each breached sector scale its member weights so sector total = sector_cap
    for row in breaches.itertuples():
        sector = row.sector
        total = row.composite_weight
        if total <= 0:
            continue
        scale = sector_cap / total
        mask = uniq["sector"] == sector
        uniq.loc[mask, "composite_weight"] *= scale
    # Decide whether to renormalize: only if total positive weight > 1 (overflow redistributed)
    positives = uniq[uniq["composite_weight"] > 0]
    total_pos = positives["composite_weight"].sum() if not positives.empty else 0.0
    if total_pos > 1 + 1e-9:
        uniq["composite_weight"] = uniq["composite_weight"] / total_pos
    # Merge back
    out = df.drop(columns=["composite_weight"]).merge(uniq[["ticker", "composite_weight"]], on="ticker", how="left")
    return out


# ---------------- Persistence (SQLite) -----------------
_STRATEGY_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS strategy_registry (
  name TEXT PRIMARY KEY,
  type TEXT NOT NULL,
  params TEXT,
  active INTEGER NOT NULL,
  capital_weight REAL NOT NULL
);
"""


def _connect():  # pragma: no cover - trivial wrapper
    return sqlite3.connect(settings.paths.db_file)


def save_strategy_registry(capital_overrides: Optional[Dict[str, float]] = None) -> None:
    """Persist current registry state and (optionally) provided capital weights.

    Args:
        capital_overrides: mapping name->capital_weight to store (normalized externally).
    """
    try:
        conn = _connect()
        conn.execute(_STRATEGY_TABLE_SQL)
        for name, meta in _REGISTRY.items():
            obj = meta["obj"]
            active = 1 if meta.get("active") else 0
            cap = float(capital_overrides.get(name, 1.0) if capital_overrides else 1.0)
            # Identify type and params
            if isinstance(obj, EqualWeightStrategy):
                t = "equal_weight"; params = {}
            elif isinstance(obj, TopNPriceMomentumStrategy):
                t = "momentum"; params = {"top_n": obj.top_n}
            else:
                # generic fallback: skip unknown type
                continue
            conn.execute(
                "REPLACE INTO strategy_registry(name,type,params,active,capital_weight) VALUES (?,?,?,?,?)",
                (name, t, json.dumps(params), active, cap),
            )
        conn.commit(); conn.close()
    except Exception as e:  # pragma: no cover - defensive
        logger.error("strategy_persist_failed", extra={"error": str(e)})


def load_strategy_registry() -> Dict[str, float]:
    """Load registered strategies from store, registering them in-memory.

    Returns mapping name->capital_weight.
    """
    caps: Dict[str, float] = {}
    try:
        conn = _connect()
        conn.execute(_STRATEGY_TABLE_SQL)
        cur = conn.execute("SELECT name,type,params,active,capital_weight FROM strategy_registry")
        rows = cur.fetchall()
        conn.close()
    except Exception as e:  # pragma: no cover
        logger.error("strategy_load_failed", extra={"error": str(e)})
        return caps
    for name, t, params_json, active, cap in rows:
        try:
            params = json.loads(params_json) if params_json else {}
            if t == "equal_weight":
                register_strategy(EqualWeightStrategy(), active=bool(active), replace=True)
            elif t == "momentum":
                top_n = int(params.get("top_n", 5))
                register_strategy(TopNPriceMomentumStrategy(top_n=top_n, name=name), active=bool(active), replace=True)
            else:
                continue
            caps[name] = float(cap)
        except Exception as e:  # pragma: no cover
            logger.warning("strategy_restore_failed", extra={"name": name, "error": str(e)})
    return caps


# ---------------- Order generation -----------------
def generate_rebalance_orders(
    delta_df: pd.DataFrame,
    min_shares: int = 1,
    min_value: float = 0.0,
    weight_tolerance: float = 0.0,
    round_shares: bool = True,
) -> List[dict]:
    """Convert allocation deltas to order instructions.

    Filters out tiny adjustments based on tolerances.
    Returns list of dicts: {ticker, side, shares, est_price, value_delta, target_weight, current_weight}
    """
    orders: List[dict] = []
    if delta_df is None or delta_df.empty:
        return orders
    for r in delta_df.itertuples():
        dw = float(getattr(r, "delta_weight", 0.0))
        vd = float(getattr(r, "value_delta", 0.0))
        price = float(getattr(r, "price", 0.0) or 0.0)
        shares_delta = float(getattr(r, "shares_delta", 0.0))
        if abs(dw) < weight_tolerance:
            continue
        if abs(vd) < min_value:
            continue
        if abs(shares_delta) < float(min_shares):
            continue
        shares = shares_delta
        if round_shares:
            shares = int(round(shares_delta))
            if shares == 0:
                continue
        side = "BUY" if shares > 0 else "SELL"
        orders.append({
            "ticker": r.ticker,
            "side": side,
            "shares": abs(int(shares)) if round_shares else abs(shares),
            "est_price": price,
            "value_delta": vd,
            "target_weight": float(getattr(r, "composite_weight", 0.0)),
            "current_weight": float(getattr(r, "current_weight", 0.0)),
        })
    return orders
