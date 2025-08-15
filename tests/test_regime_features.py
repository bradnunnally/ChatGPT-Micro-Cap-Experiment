import pandas as pd
import numpy as np
from services.regime_features import compute_regime_features, RegimeFeaturesConfig


def test_regime_features_basic():
    rng = np.random.default_rng(0)
    rets = pd.Series(rng.normal(0.0005, 0.01, size=150))
    feats = compute_regime_features(rets)
    assert feats
    required = {"rf_vol_short","rf_vol_med","rf_vol_long","rf_mean_short","rf_dd","rf_trend_flag"}
    assert required.issubset(feats.keys())
    assert feats["rf_vol_short"] >= 0 and feats["rf_vol_med"] >= 0
    assert -1.0 <= feats["rf_dd"] <= 0.0


def test_regime_features_insufficient_history():
    rets = pd.Series([0.01, -0.005, 0.002])
    feats = compute_regime_features(rets)
    assert feats == {}


def test_regime_features_trend_flag_behavior():
    drift = np.linspace(0, 0.02, 160)
    noise = np.random.default_rng(1).normal(0,0.002,160)
    rets = pd.Series(drift + noise)
    feats = compute_regime_features(rets, RegimeFeaturesConfig(short=20, medium=60, long=120))
    assert feats
    assert feats["rf_trend_flag"] in (0.0,1.0)
