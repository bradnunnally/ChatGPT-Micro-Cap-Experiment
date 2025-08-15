"""Phase 14 – Adaptive regime feature extraction.

Lightweight, deterministic feature engineering over a univariate return
series to drive probabilistic regime classification in later steps.

Only pure calculations here (no side effects / I/O) so they are
trivially unit testable. Future steps will map these features into
probabilities and dynamic risk targets.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict
import pandas as pd
import numpy as np

MIN_OBS = 40  # minimum observations to compute the full feature set


@dataclass(slots=True)
class RegimeFeaturesConfig:
    short: int = 20
    medium: int = 60
    long: int = 120


def _safe_std(s: pd.Series) -> float:
    s = s.dropna()
    if s.empty:
        return 0.0
    return float(s.std(ddof=0))


def _cumulative_drawdown(returns: pd.Series) -> float:
    """Return max drawdown (negative) over the provided returns series."""
    if returns is None or returns.empty:
        return 0.0
    curve = (1 + returns.fillna(0)).cumprod()
    peak = curve.cummax()
    dd = curve / peak - 1.0
    return float(dd.min())


def compute_regime_features(returns: pd.Series | None, config: RegimeFeaturesConfig | None = None) -> Dict[str, float]:
    """Compute a dictionary of regime features from a daily returns series.

    Features (prefix rf_):
      rf_vol_short / rf_vol_med / rf_vol_long
      rf_vol_ratio_short (vol_short / vol_med)
      rf_vol_ratio_med (vol_med / vol_long)
      rf_mean_short / rf_mean_med
      rf_dd (max drawdown, negative)
      rf_trend_flag (1 if synthetic price > SMA_med else 0)
      rf_downside_hit_rate_short (% negative returns last short window)

    Edge cases:
      - If insufficient observations (< MIN_OBS) returns {} so callers can fallback.
      - All NaNs -> {}.
    """
    if returns is None:
        return {}
    r = pd.Series(returns).dropna()
    if r.shape[0] < MIN_OBS:
        return {}
    cfg = config or RegimeFeaturesConfig()
    short = min(cfg.short, r.shape[0])
    med = min(cfg.medium, r.shape[0])
    long = min(cfg.long, r.shape[0])
    tail_short = r.tail(short)
    tail_med = r.tail(med)
    tail_long = r.tail(long)
    vol_short = _safe_std(tail_short)
    vol_med = _safe_std(tail_med)
    vol_long = _safe_std(tail_long)
    mean_short = float(tail_short.mean()) if not tail_short.empty else 0.0
    mean_med = float(tail_med.mean()) if not tail_med.empty else 0.0
    vol_ratio_short = vol_short / (vol_med + 1e-12)
    vol_ratio_med = vol_med / (vol_long + 1e-12)
    dd = _cumulative_drawdown(tail_long)
    price_path = (1 + tail_long).cumprod()
    sma_med = price_path.rolling(med).mean().iloc[-1]
    trend_flag = 1.0 if price_path.iloc[-1] > (sma_med if not np.isnan(sma_med) else price_path.iloc[-1]) else 0.0
    downside_hit_rate_short = float((tail_short < 0).mean()) if not tail_short.empty else 0.0
    feats = {
        "rf_vol_short": vol_short,
        "rf_vol_med": vol_med,
        "rf_vol_long": vol_long,
        "rf_vol_ratio_short": vol_ratio_short,
        "rf_vol_ratio_med": vol_ratio_med,
        "rf_mean_short": mean_short,
        "rf_mean_med": mean_med,
        "rf_dd": dd,
        "rf_trend_flag": trend_flag,
        "rf_downside_hit_rate_short": downside_hit_rate_short,
    }
    cleaned = {k: (0.0 if (np.isnan(v) or np.isinf(v)) else float(v)) for k, v in feats.items()}
    return cleaned


__all__ = [
    "RegimeFeaturesConfig",
    "compute_regime_features",
]
