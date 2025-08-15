"""Phase 9 – Advanced portfolio optimization utilities & strategy classes.

Lightweight, dependency-minimal implementations to plug into existing
multi-strategy framework without introducing heavy numeric solvers.

Provided components:
  - estimate_returns: simple expected return estimator (mean / EMA)
  - estimate_covariance: sample covariance with optional Ledoit-Wolf style
    shrinkage toward the identity (scalar multiple of trace/n * I)
  - MeanVarianceStrategy: closed-form (Σ^{-1} μ) heuristic, long-only clamp
  - RiskParityStrategy: inverse volatility (or exact volatility parity approximation)
  - factor_neutral_overlay: remove exposure to one or more factors via
    orthogonal projection; long-only clamp & renormalize optional.
  - apply_turnover_penalty: soft-threshold (L1) shrink on target vs current

These are intentionally approximate but deterministic & testable.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Sequence
import pandas as pd
import numpy as np

from services.strategy import StrategyContext, Strategy, register_strategy  # noqa: F401

# ---------- Estimators ----------


def estimate_returns(returns: pd.DataFrame, method: str = "mean", span: int = 20) -> pd.Series:
    """Estimate expected returns per column of returns matrix (rows=time)."""
    if returns is None or returns.empty:
        return pd.Series(dtype=float)
    r = returns.dropna(how="all")
    if r.empty:
        return pd.Series(dtype=float)
    if method == "ema":
        out = r.ewm(span=span, adjust=False).mean().iloc[-1]
    else:
        out = r.mean()
    return out.replace([np.inf, -np.inf], 0.0).fillna(0.0)


def estimate_covariance(returns: pd.DataFrame, shrink: bool = True) -> pd.DataFrame:
    """Sample covariance with optional simple Ledoit-Wolf style shrinkage.

    Shrinkage: S_hat = (1 - λ) * S + λ * F, where F = (trace(S)/n) * I
    λ heuristic: higher when sample shorter relative to number of assets.
    """
    if returns is None or returns.empty:
        return pd.DataFrame()
    S = returns.cov()
    S = S.replace([np.inf, -np.inf], 0.0).fillna(0.0)
    if not shrink:
        return S
    n = S.shape[0]
    if n == 0:
        return S
    trace = float(np.trace(S.values))
    if trace <= 0:
        return S
    F = (trace / n) * np.eye(n)
    t = returns.shape[0]
    if t < n * 3:
        lam = 0.5
    elif t < n * 6:
        lam = 0.25
    else:
        lam = 0.1
    S_hat = (1 - lam) * S.values + lam * F
    return pd.DataFrame(S_hat, index=S.index, columns=S.columns)


# ---------- Strategies ----------


@dataclass(slots=True)
class MeanVarianceStrategy:
    """Approximate mean-variance optimizer using Σ^{-1} μ heuristic."""

    name: str = "mean_variance"
    returns_window: int = 60
    shrink: bool = True
    long_only: bool = True
    min_weight: float = 0.0
    risk_aversion: float = 1.0
    exp_ret_method: str = "mean"  # or 'ema'

    def target_weights(self, ctx: StrategyContext) -> Dict[str, float]:  # type: ignore[override]
        prices = ctx.prices
        if prices is None or prices.empty or "ticker" not in prices.columns or "pct_change" not in prices.columns:
            return {}
        hist: pd.DataFrame | None = ctx.extra.get("returns_history") if ctx.extra else None
        if hist is None or hist.empty:
            tmp = prices.set_index("ticker")["pct_change"].astype(float)
            hist = pd.DataFrame([tmp.values], columns=tmp.index)
        use = hist.tail(self.returns_window)
        mu = estimate_returns(use, method=self.exp_ret_method)
        cov = estimate_covariance(use, shrink=self.shrink)
        if cov.empty or mu.empty:
            return {}
        tickers = list(mu.index)
        try:
            inv = np.linalg.pinv(cov.values)
            raw = inv.dot(mu.values)
        except Exception:
            return {}
        w = pd.Series(raw, index=tickers)
        # If all expected returns are non-positive the classical solution collapses.
        # Fallback: treat absolute values (risk parity tilt) to retain diversification.
        if (w <= 0).all():
            alt = (1 / np.sqrt(np.diag(cov.values)))  # inverse vol heuristic
            w = pd.Series(alt, index=tickers)
        if self.long_only:
            w = w.clip(lower=self.min_weight)
        w = w.replace([np.inf, -np.inf], 0.0)
        total = w.sum()
        if total <= 0:
            return {}
        w = w / total
        return {t: float(v) for t, v in w.items() if v > 0}


@dataclass(slots=True)
class RiskParityStrategy:
    """Inverse volatility (risk parity approximation)."""

    name: str = "risk_parity"
    window: int = 60
    long_only: bool = True
    min_weight: float = 0.0

    def target_weights(self, ctx: StrategyContext) -> Dict[str, float]:  # type: ignore[override]
        hist: pd.DataFrame | None = ctx.extra.get("returns_history") if ctx.extra else None
        if hist is None or hist.empty:
            return {}
        use = hist.tail(self.window).dropna(how="all")
        if use.empty:
            return {}
        vol = use.std(ddof=0).replace(0, pd.NA)
        inv_vol = 1 / vol
        inv_vol = inv_vol.replace([np.inf, -np.inf], 0).fillna(0)
        if inv_vol.sum() <= 0:
            return {}
        w = inv_vol / inv_vol.sum()
        if self.long_only:
            w = w.clip(lower=self.min_weight)
        total = w.sum()
        if total <= 0:
            return {}
        w = w / total
        return {t: float(v) for t, v in w.items() if v > 0}


@dataclass(slots=True)
class MinVarianceStrategy:
    name: str = "min_variance"
    window: int = 60
    shrink: bool = True
    long_only: bool = True
    min_weight: float = 0.0

    def target_weights(self, ctx: StrategyContext) -> Dict[str, float]:  # type: ignore[override]
        hist: pd.DataFrame | None = ctx.extra.get("returns_history") if ctx.extra else None
        if hist is None or hist.empty:
            return {}
        use = hist.tail(self.window)
        cov = estimate_covariance(use, shrink=self.shrink)
        if cov.empty:
            return {}
        ones = np.ones(cov.shape[0])
        try:
            inv = np.linalg.pinv(cov.values)
            raw = inv.dot(ones)
        except Exception:
            return {}
        w = pd.Series(raw, index=cov.columns)
        if self.long_only:
            w = w.clip(lower=self.min_weight)
        w = w.replace([np.inf, -np.inf], 0.0)
        s = w.sum()
        if s <= 0:
            return {}
        w = w / s
        return {t: float(v) for t, v in w.items() if v > 0}


@dataclass(slots=True)
class ConstrainedRiskParityStrategy:
    name: str = "constrained_risk_parity"
    window: int = 60
    max_weight: float = 0.25
    iterations: int = 25
    tol: float = 0.10

    def target_weights(self, ctx: StrategyContext) -> Dict[str, float]:  # type: ignore[override]
        hist: pd.DataFrame | None = ctx.extra.get("returns_history") if ctx.extra else None
        if hist is None or hist.empty:
            return {}
        use = hist.tail(self.window).dropna(how="all")
        if use.empty:
            return {}
        cov = use.cov().fillna(0.0)
        vols = np.sqrt(np.diag(cov.values))
        vols = np.where(vols == 0, 1e-6, vols)
        w = 1 / vols
        w = np.maximum(w, 0)
        w = w / w.sum()
        n = len(w)
        target_rc = 1.0 / n
        for _ in range(self.iterations):
            port_var = float(w @ cov.values @ w)
            if port_var <= 0:
                break
            mrc = (cov.values @ w)
            rc = w * mrc / np.sqrt(port_var)
            if rc.sum() > 0:
                rc = rc / rc.sum()
            if rc.std() / (rc.mean() + 1e-12) < self.tol:
                break
            adjust = target_rc / (rc + 1e-12)
            w = w * adjust
            if self.max_weight is not None:
                w = np.minimum(w, self.max_weight)
            w = np.maximum(w, 0)
            s = w.sum()
            if s <= 0:
                return {}
            w = w / s
        return {t: float(v) for t, v in zip(cov.columns, w) if v > 0}


# ---------- Factor Neutral Overlay ----------


def factor_neutral_overlay(
    weights: Dict[str, float],
    exposures: pd.DataFrame,
    factors: Sequence[str],
    long_only: bool = True,
) -> Dict[str, float]:
    """Return adjusted weights with specified factor exposures suppressed."""
    if not weights or exposures is None or exposures.empty:
        return weights
    w = pd.Series(weights).astype(float)
    w = w.reindex(exposures.index).fillna(0.0)
    X = exposures[factors].fillna(0.0).astype(float)
    for col in X.columns:
        x = X[col]
        # If exposure column constant, skipping projection avoids degeneracy collapsing weights.
        if x.nunique(dropna=True) <= 1:
            continue
        denom = float((x * x).sum())
        if denom <= 0:
            continue
        proj_coeff = float((x * w).sum() / denom)
        w = w - proj_coeff * x
    # Degeneracy: if projection zeroed everything (or near) revert to equal over original support
    if (w.abs() < 1e-12).all():
        # All projected out; fall back to original weights (normalized) to retain diversification
        orig = pd.Series(weights).clip(lower=0)
        tot = orig.sum()
        if tot > 0:
            orig = orig / tot
            return {t: float(v) for t, v in orig.items() if v > 0}
    if long_only:
        w = w.clip(lower=0)
    total = w.sum()
    if total <= 0:
        return weights
    w = w / total
    return {t: float(v) for t, v in w.items() if v > 0}


# ---------- Turnover / Transaction Cost Penalty ----------


def apply_turnover_penalty(
    current: Dict[str, float],
    target: Dict[str, float],
    cost_bps: float = 10.0,
    penalty: float = 0.0,
    long_only: bool = True,
) -> Dict[str, float]:
    """Shrink target changes toward current weights using L1 soft threshold."""
    if penalty <= 0:
        return target
    all_ticks = set(current) | set(target)
    cur = pd.Series(current).reindex(all_ticks).fillna(0.0)
    tgt = pd.Series(target).reindex(all_ticks).fillna(0.0)
    delta = tgt - cur
    lam = penalty * (cost_bps / 10000.0)
    adj = delta.apply(lambda d: np.sign(d) * max(abs(d) - lam, 0.0))
    w_new = cur + adj
    if long_only:
        w_new = w_new.clip(lower=0)
    s = w_new.sum()
    if s <= 0:
        return target
    w_new = w_new / s
    return {t: float(v) for t, v in w_new.items() if v > 0}


__all__ = [
    "estimate_returns",
    "estimate_covariance",
    "MeanVarianceStrategy",
    "RiskParityStrategy",
    "MinVarianceStrategy",
    "ConstrainedRiskParityStrategy",
    "factor_neutral_overlay",
    "apply_turnover_penalty",
    "register_strategy",
    "register_phase9_strategies",
    "apply_volatility_cap",
    "apply_volatility_target",
    "compute_factor_exposures",
    "regime_risk_overlay",
    "profile_optimization_pipeline",
]


def register_phase9_strategies() -> None:  # type: ignore[override]
    """Convenience helper to register the Phase 9 optimization strategies.

    Idempotent: re-registers (replace=True default in register_strategy).
    """
    try:
        register_strategy(MeanVarianceStrategy())
        register_strategy(RiskParityStrategy())
        register_strategy(MinVarianceStrategy())
        register_strategy(ConstrainedRiskParityStrategy())
    except Exception:
        pass


def apply_volatility_cap(
    weights: dict[str, float],
    returns_history: pd.DataFrame | None,
    target_annual_vol_pct: float | None,
    window: int = 60,
) -> dict[str, float]:
    """Scale weights down uniformly to respect a maximum annualized volatility.

    If current annualized volatility <= target (or inputs invalid) returns weights unchanged.
    Scaling introduces an implicit cash buffer (weights will sum < 1) which downstream
    cleaning logic must preserve (do not renormalize) to retain the volatility effect.
    """
    if not weights or target_annual_vol_pct is None or target_annual_vol_pct <= 0:
        return weights
    if returns_history is None or returns_history.empty:
        return weights
    use = returns_history.tail(window)
    # Align columns
    cols = [c for c in use.columns if c in weights]
    if len(cols) < 2:
        return weights
    sub = use[cols].dropna(how="all")
    if sub.empty:
        return weights
    cov = sub.cov().fillna(0.0)
    w = pd.Series({k: float(v) for k, v in weights.items() if k in cov.columns})
    if w.empty:
        return weights
    # Normalize current active portion (ignore any implicit cash already present)
    active_sum = w.sum()
    if active_sum <= 0:
        return weights
    w_norm = w / active_sum
    # Portfolio daily variance
    var_daily = float(w_norm.values @ cov.loc[w_norm.index, w_norm.index].values @ w_norm.values)
    if var_daily < 0:
        return weights
    import math
    vol_annual = math.sqrt(var_daily) * math.sqrt(252)
    if vol_annual <= target_annual_vol_pct / 100.0:
        return weights
    scale = (target_annual_vol_pct / 100.0) / vol_annual
    # Scale active weights (not cash) then return; implicit cash = 1 - sum(scaled)
    scaled_active = (w_norm * scale).to_dict()
    return scaled_active


def apply_volatility_target(
    weights: dict[str, float],
    returns_history: pd.DataFrame | None,
    target_annual_vol: float | None,
    window: int = 60,
    floor_scale: float = 0.2,
) -> dict[str, float]:
    """Scale weights (up or down) toward a target annualized volatility.

    Unlike the cap (which only scales down), this attempts to adjust exposure up if
    realized vol is far below target (subject to a max scale that preserves sign and
    avoids extreme leverage). If current gross < 1 we allow proportional increase
    but never exceed scale factor implied by target / current or inverse of floor_scale.
    Returns new weights dict (may sum != 1 representing implicit cash or leverage placeholder).
    """
    if not weights or target_annual_vol is None or target_annual_vol <= 0:
        return weights
    if returns_history is None or returns_history.empty:
        return weights
    use = returns_history.tail(window)
    cols = [c for c in use.columns if c in weights]
    if len(cols) < 2:
        return weights
    sub = use[cols].dropna(how="all")
    if sub.empty:
        return weights
    cov = sub.cov().fillna(0.0)
    w = pd.Series({k: float(v) for k, v in weights.items() if k in cov.columns})
    if w.empty:
        return weights
    active_sum = w.sum()
    if active_sum <= 0:
        return weights
    w_norm = w / active_sum
    var_daily = float(w_norm.values @ cov.loc[w_norm.index, w_norm.index].values @ w_norm.values)
    if var_daily <= 0:
        return weights
    import math
    vol_ann = math.sqrt(var_daily) * math.sqrt(252)
    target = target_annual_vol
    if abs(vol_ann - target) / target < 0.05:  # within 5% band; no change
        return weights
    scale = target / vol_ann
    # Bound scale to avoid extreme leverage or collapse
    scale = float(np.clip(scale, floor_scale, 1.5))
    return {k: v * scale for k, v in weights.items()}


# ---------- Factor Exposure Estimation (Rolling Betas) ----------

def compute_factor_exposures(
    asset_returns: pd.DataFrame,
    factor_returns: pd.DataFrame,
    min_obs: int = 30,
) -> pd.DataFrame:
    """Compute simple OLS (no-intercept) betas of each asset vs provided factor returns.

    Parameters:
        asset_returns: DataFrame (rows=time, cols=tickers)
        factor_returns: DataFrame (rows=time, cols=factors) – already aligned or longer
        min_obs: minimum overlapping observations required to estimate betas

    Returns:
        DataFrame of exposures (index=tickers, columns=factors). Missing /
        insufficient data rows yield 0 exposures for that asset.
    """
    if asset_returns is None or asset_returns.empty:
        return pd.DataFrame()
    if factor_returns is None or factor_returns.empty:
        return pd.DataFrame()
    # Align on common index (drop rows with any NaNs across factors for stability)
    df = asset_returns.join(factor_returns, how="inner", rsuffix="_f")
    if df.empty:
        return pd.DataFrame()
    # Split back
    asset_cols = [c for c in asset_returns.columns if c in df.columns]
    factor_cols = [c for c in factor_returns.columns if c in df.columns]
    X = df[factor_cols].dropna(how="any")
    if X.empty:
        return pd.DataFrame()
    out = {}
    XtX = X.T.dot(X)
    try:
        XtX_inv = np.linalg.pinv(XtX.values)
    except Exception:
        return pd.DataFrame()
    Xt = X.T
    for col in asset_cols:
        y = df[col].loc[X.index]  # align to X index
        y = y.replace([np.inf, -np.inf], np.nan).dropna()
        common = y.index.intersection(X.index)
        if len(common) < min_obs or len(common) < len(factor_cols) + 2:
            # Not enough data; set zeros
            out[col] = [0.0] * len(factor_cols)
            continue
        y_vec = y.loc[common].values
        X_sub = X.loc[common].values
        # Recompute local (handles any NaN pruning differences) for stability
        try:
            betas = np.linalg.pinv(X_sub).dot(y_vec)
        except Exception:
            try:
                betas = XtX_inv.dot(Xt.dot(y.loc[X.index].fillna(0).values))
            except Exception:
                betas = np.zeros(len(factor_cols))
        # Clean
        betas = np.nan_to_num(betas, nan=0.0, posinf=0.0, neginf=0.0)
        out[col] = betas.tolist()
    exposures = pd.DataFrame(out, index=factor_cols).T
    return exposures


def regime_risk_overlay(weights: dict[str, float], regime_label: str | None, regime_probs: dict[str, float] | None = None, gross_target: float | None = None) -> dict[str, float]:
    """Scale weights based on regime.

    If regime_probs & gross_target provided (Phase 14 adaptive layer), use gross_target directly.
    Else fall back to static map by regime_label.
    """
    if not weights:
        return weights
    if gross_target is not None and gross_target > 0:
        current_gross = sum(abs(v) for v in weights.values())
        if current_gross <= 0:
            return weights
        scale = gross_target / current_gross
        if abs(scale - 1.0) < 1e-6:
            return weights
        return {k: v * scale for k, v in weights.items()}
    scale_map = {"high_vol": 0.7, "bear": 0.6, "sideways": 0.9, "bull": 1.0}
    s = scale_map.get(regime_label or "", 1.0)
    if abs(s - 1.0) < 1e-6:
        return weights
    return {k: v * s for k, v in weights.items()}


def profile_optimization_pipeline(returns_history: pd.DataFrame, strategies: list[Strategy], ctx: StrategyContext, overlays: bool = False) -> dict:
    import time
    out: dict[str, float] = {}
    start = time.perf_counter()
    hist_tail = returns_history.tail(120) if returns_history is not None else pd.DataFrame()
    _ = estimate_returns(hist_tail, method="mean")
    out["returns_estimation_ms"] = (time.perf_counter() - start) * 1000
    t2 = time.perf_counter()
    _ = estimate_covariance(hist_tail, shrink=True)
    out["covariance_estimation_ms"] = (time.perf_counter() - t2) * 1000
    t3 = time.perf_counter()
    for strat in strategies:
        try:
            strat.target_weights(ctx)
        except Exception:
            pass
    out["strategies_eval_ms"] = (time.perf_counter() - t3) * 1000
    if overlays:
        t4 = time.perf_counter()
        dummy_weights = {c: 1/len(hist_tail.columns) for c in hist_tail.columns} if hist_tail is not None and not hist_tail.empty else {}
        if dummy_weights:
            apply_volatility_cap(dummy_weights, returns_history, target_annual_vol_pct=15.0)
        out["overlays_ms"] = (time.perf_counter() - t4) * 1000
    out["total_ms"] = sum(v for k, v in out.items() if k.endswith("_ms"))
    return out
