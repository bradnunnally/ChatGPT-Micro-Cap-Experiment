import math
from services.regime_scoring import (
    compute_regime_probabilities,
    RegimeScoringConfig,
    translate_regime_risk,
)


def test_uniform_when_missing_features():
    probs, label = compute_regime_probabilities(None)
    assert set(probs.keys()) == {"bull", "bear", "high_vol", "sideways"}
    assert all(abs(v - 0.25) < 1e-9 for v in probs.values())
    assert label == "unknown"


def test_probabilities_sum_to_one():
    feats = {
        "rf_vol_short": 0.02,
        "rf_vol_med": 0.015,
        "rf_vol_long": 0.012,
        "rf_vol_ratio_short": 1.3,  # elevated short term
        "rf_vol_ratio_med": 1.1,
        "rf_mean_med": 0.0005,
        "rf_dd": -0.02,
        "rf_trend_flag": 1.0,
        "rf_downside_hit_rate_short": 0.40,
    }
    probs, label = compute_regime_probabilities(feats)
    assert math.isclose(sum(probs.values()), 1.0, rel_tol=1e-9)
    assert label in probs
    # Expect bull or high_vol to dominate here (positive trend and high short vol)
    assert probs[label] == max(probs.values())


def test_bearish_conditions():
    feats = {
        "rf_vol_short": 0.03,
        "rf_vol_med": 0.02,
        "rf_vol_long": 0.018,
        "rf_vol_ratio_short": 1.1,
        "rf_vol_ratio_med": 1.05,
        "rf_mean_med": -0.001,
        "rf_dd": -0.10,  # deep drawdown
        "rf_trend_flag": 0.0,
        "rf_downside_hit_rate_short": 0.65,
    }
    probs, label = compute_regime_probabilities(feats)
    assert label == max(probs, key=probs.get)
    # Bear probability should be highest in this configuration
    assert label == "bear"
    assert probs[label] > 0.4  # reasonably dominant


def test_sideways_conditions():
    feats = {
        "rf_vol_short": 0.012,
        "rf_vol_med": 0.012,
        "rf_vol_long": 0.011,
        "rf_vol_ratio_short": 1.0,
        "rf_vol_ratio_med": 1.0,
        "rf_mean_med": 0.0,
        "rf_dd": -0.01,
        "rf_trend_flag": 0.0,
        "rf_downside_hit_rate_short": 0.48,
    }
    probs, label = compute_regime_probabilities(feats)
    assert label == max(probs, key=probs.get)
    assert label == "sideways"


def test_config_tuning_effect():
    feats = {
        "rf_vol_short": 0.02,
        "rf_vol_med": 0.015,
        "rf_vol_long": 0.013,
        "rf_vol_ratio_short": 1.25,
        "rf_vol_ratio_med": 1.12,
        "rf_mean_med": 0.0003,
        "rf_dd": -0.03,
        "rf_trend_flag": 1.0,
        "rf_downside_hit_rate_short": 0.42,
    }
    base_probs, _ = compute_regime_probabilities(feats)
    # Increase weight for vol ratio to bias toward high_vol
    cfg = RegimeScoringConfig(w_volratio_high=3.0)
    new_probs, _ = compute_regime_probabilities(feats, cfg)
    assert new_probs["high_vol"] > base_probs["high_vol"]


def test_translate_regime_risk_basic():
    probs = {"bull": 0.5, "bear": 0.2, "high_vol": 0.2, "sideways": 0.1}
    out = translate_regime_risk(probs)
    assert 0.0 < out["target_vol"] < 0.25
    assert 0.55 <= out["gross_exposure"] <= 1.0
    assert math.isclose(sum(out["regime_contrib"].values()), out["target_vol"], rel_tol=1e-9)


def test_translate_regime_risk_edge_uniform():
    out = translate_regime_risk({r: 0.25 for r in ["bull", "bear", "high_vol", "sideways"]})
    # Weighted average must lie within min/max config
    assert 0.10 <= out["target_vol"] <= 0.18
    assert 0.55 <= out["gross_exposure"] <= 1.0
