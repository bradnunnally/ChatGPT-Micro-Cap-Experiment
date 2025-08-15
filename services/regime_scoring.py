"""Phase 14 – Regime scoring & probability mapping.

Transforms engineered features (see `regime_features`) into a soft
probability distribution across canonical regimes: bull, bear, high_vol,
sideways. Design emphasises determinism, transparency, and testability –
no external data dependencies and pure functions.

Scoring Heuristics (initial defaults):
  * bull: positive trend flag, positive Sharpe proxy, shallow drawdown,
          low downside hit rate, moderate/contained volatility.
  * bear: negative/weak Sharpe, deep drawdown, high downside hit rate.
  * high_vol: short-term volatility ratios elevated vs medium/long.
  * sideways: low absolute Sharpe & low volatility & not deeply negative.

All raw scores are combined via softmax to derive probabilities.
Edge Cases: missing / empty features -> uniform distribution.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import exp
from typing import Dict, Tuple
import numpy as np

RegimeProbs = Dict[str, float]

REGIMES = ["bull", "bear", "high_vol", "sideways"]


@dataclass(slots=True)
class RegimeScoringConfig:
    # Threshold style knobs (tune later if desired)
    high_vol_ratio: float = 1.15   # short/med or med/long ratio above this -> high vol pressure
    high_vol_short_vs_med: float = 1.20
    sharpe_pos_floor: float = 0.0
    sharpe_neg_floor: float = -0.25
    drawdown_deep: float = -0.06    # deeper than -6% considered notable
    downside_hit_high: float = 0.55 # >55% negatives = pressure
    downside_hit_low: float = 0.45  # <45% negatives supportive for bull
    low_vol_quant: float = 0.6      # heuristic low vol factor for sideways scoring
    # Scaling weights
    w_trend: float = 2.0
    w_sharpe_bull: float = 1.5
    w_downside_penalty_bull: float = 1.0
    w_drawdown_penalty_bull: float = 0.8
    w_sharpe_bear: float = 1.2
    w_drawdown_bear: float = 2.2
    w_downside_bear: float = 1.2
    w_volratio_high: float = 1.5
    w_highvol_secondary: float = 1.0
    w_sideways_lowvol: float = 1.0
    w_sideways_lowsharpe: float = 1.0
    # Additional composite stress boost when all bear signals align
    w_bear_crisis: float = 3.0
    high_vol_drawdown_dampen: float = 0.35
    # Risk translation defaults
    target_vol_bull: float = 0.18   # 18% annualized
    target_vol_bear: float = 0.10
    target_vol_high_vol: float = 0.12
    target_vol_sideways: float = 0.14
    gross_max: float = 1.00
    gross_min: float = 0.55
    gross_bull: float = 1.00
    gross_bear: float = 0.60
    gross_high_vol: float = 0.70
    gross_sideways: float = 0.85

    def regime_target_vol_map(self) -> Dict[str, float]:  # helper (not exported)
        return {
            "bull": self.target_vol_bull,
            "bear": self.target_vol_bear,
            "high_vol": self.target_vol_high_vol,
            "sideways": self.target_vol_sideways,
        }

    def regime_gross_map(self) -> Dict[str, float]:
        return {
            "bull": self.gross_bull,
            "bear": self.gross_bear,
            "high_vol": self.gross_high_vol,
            "sideways": self.gross_sideways,
        }


def _softmax(scores: Dict[str, float]) -> RegimeProbs:
    if not scores:
        return {r: 1.0 / len(REGIMES) for r in REGIMES}
    # Numerical stability
    m = max(scores.values())
    exps = {k: exp(v - m) for k, v in scores.items()}
    denom = sum(exps.values())
    if denom <= 0:
        return {r: 1.0 / len(REGIMES) for r in REGIMES}
    return {k: v / denom for k, v in exps.items()}


def compute_regime_probabilities(features: Dict[str, float] | None, config: RegimeScoringConfig | None = None) -> Tuple[RegimeProbs, str]:
    """Map regime features -> probability distribution & primary label.

    If features missing/empty returns uniform distribution.
    """
    if not features:
        probs = {r: 1.0 / len(REGIMES) for r in REGIMES}
        return probs, "unknown"
    cfg = config or RegimeScoringConfig()

    # Extract with safe defaults
    vol_short = float(features.get("rf_vol_short", 0.0))
    vol_med = float(features.get("rf_vol_med", 0.0))
    vol_long = float(features.get("rf_vol_long", 0.0))
    vol_ratio_short = float(features.get("rf_vol_ratio_short", 1.0))
    vol_ratio_med = float(features.get("rf_vol_ratio_med", 1.0))
    mean_med = float(features.get("rf_mean_med", 0.0))
    drawdown = float(features.get("rf_dd", 0.0))  # negative
    trend_flag = float(features.get("rf_trend_flag", 0.0))
    downside_hit = float(features.get("rf_downside_hit_rate_short", 0.5))

    # Simple Sharpe proxy (mean / vol) over medium window
    sharpe_proxy = 0.0
    if vol_med > 0:
        sharpe_proxy = mean_med / (vol_med + 1e-12)
    # Clip extremes to prevent a single large mean dominating
    sharpe_proxy = float(np.clip(sharpe_proxy, -2.5, 2.5))

    # Bull scoring
    bull_score = 0.0
    bull_score += cfg.w_trend * trend_flag
    if sharpe_proxy > cfg.sharpe_pos_floor:
        bull_score += cfg.w_sharpe_bull * (sharpe_proxy - cfg.sharpe_pos_floor)
    # Penalize if high downside hit
    if downside_hit > cfg.downside_hit_low:
        bull_score -= cfg.w_downside_penalty_bull * (downside_hit - cfg.downside_hit_low)
    # Penalize deep drawdowns
    if drawdown < cfg.drawdown_deep:
        bull_score -= cfg.w_drawdown_penalty_bull * (abs(drawdown) - abs(cfg.drawdown_deep))

    # Bear scoring
    bear_score = 0.0
    if sharpe_proxy < cfg.sharpe_neg_floor:
        bear_score += cfg.w_sharpe_bear * (abs(sharpe_proxy - cfg.sharpe_neg_floor))
    if drawdown < cfg.drawdown_deep:
        bear_score += cfg.w_drawdown_bear * (abs(drawdown) - abs(cfg.drawdown_deep))
    if downside_hit > cfg.downside_hit_high:
        bear_score += cfg.w_downside_bear * (downside_hit - cfg.downside_hit_high)
    # Additional bear boost when deep drawdown coincides with short-term vol expansion
    if drawdown < cfg.drawdown_deep and vol_med > 0 and (vol_short / (vol_med + 1e-12)) > 1.2:
        bear_score += 0.6 * ((vol_short / (vol_med + 1e-12)) - 1.2)
    # Composite crisis condition (deep drawdown + high downside hit + negative sharpe)
    if (
        drawdown < cfg.drawdown_deep
        and downside_hit > cfg.downside_hit_high
        and sharpe_proxy < 0.0  # relaxed crisis trigger
    ):
        bear_score += cfg.w_bear_crisis

    # High vol scoring
    high_vol_score = 0.0
    if vol_ratio_short > cfg.high_vol_ratio:
        high_vol_score += cfg.w_volratio_high * (vol_ratio_short - cfg.high_vol_ratio)
    if vol_ratio_med > cfg.high_vol_ratio:
        high_vol_score += cfg.w_highvol_secondary * (vol_ratio_med - cfg.high_vol_ratio)
    if vol_short > cfg.high_vol_short_vs_med * (vol_med + 1e-12):
        high_vol_score += cfg.w_highvol_secondary * (vol_short / (vol_med + 1e-12) - cfg.high_vol_short_vs_med)
    # If in a deep drawdown, dampen pure high_vol classification to favor bear regime
    if drawdown < cfg.drawdown_deep and high_vol_score > 0:
        high_vol_score *= cfg.high_vol_drawdown_dampen

    # Sideways scoring – prefer low absolute Sharpe & relatively low vol & shallow drawdown
    sideways_score = 0.0
    if abs(sharpe_proxy) < 0.3:
        sideways_score += cfg.w_sideways_lowsharpe * (0.3 - abs(sharpe_proxy))
    # Use vol_med vs long as a proxy for stable environment
    if vol_ratio_med < 1.05:
        sideways_score += cfg.w_sideways_lowvol * (1.05 - vol_ratio_med)
    if drawdown > cfg.drawdown_deep:  # not deep yet
        sideways_score += 0.3  # mild boost
    else:
        # suppress sideways if in a deep drawdown
        sideways_score *= 0.4

    scores = {
        "bull": bull_score,
        "bear": bear_score,
        "high_vol": high_vol_score,
        "sideways": sideways_score,
    }
    probs = _softmax(scores)
    primary = max(probs.items(), key=lambda kv: kv[1])[0]
    return probs, primary


def translate_regime_risk(probs: RegimeProbs, config: RegimeScoringConfig | None = None) -> Dict[str, float]:
    """Convert regime probabilities into blended risk targets.

    Returns dict with keys: target_vol, gross_exposure, regime_contrib (per regime component of vol target)
    """
    if not probs:
        return {"target_vol": 0.15, "gross_exposure": 1.0, "regime_contrib": {}}
    cfg = config or RegimeScoringConfig()
    tv_map = cfg.regime_target_vol_map()
    g_map = cfg.regime_gross_map()
    # Weighted averages
    target_vol = float(sum(probs[r] * tv_map.get(r, 0.15) for r in REGIMES))
    gross = float(sum(probs[r] * g_map.get(r, 1.0) for r in REGIMES))
    gross = min(cfg.gross_max, max(cfg.gross_min, gross))
    return {
        "target_vol": target_vol,
        "gross_exposure": gross,
        "regime_contrib": {r: probs[r] * tv_map.get(r, 0.0) for r in probs},
    }


__all__ = [
    "RegimeScoringConfig",
    "compute_regime_probabilities",
    "translate_regime_risk",
]
