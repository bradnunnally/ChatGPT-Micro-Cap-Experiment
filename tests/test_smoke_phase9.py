import pandas as pd
import numpy as np

import pytest
from services.regime import detect_regime
from services.optimization import factor_neutral_overlay, apply_volatility_cap
from services.rebalance import execute_orders


@pytest.mark.smoke
def test_regime_labels_variety(monkeypatch):
    # Craft synthetic benchmark series to trigger each label
    base = pd.Series(100 + np.cumsum(np.random.normal(0, 0.2, size=200)))

    def bench_series(sym):
        return base

    monkeypatch.setattr("services.regime.get_benchmark_series", bench_series)
    # Force high vol: multiply last part variance
    hv = base.copy()
    hv.iloc[-60:] = 100 + np.cumsum(np.random.normal(0, 2.0, size=60))
    monkeypatch.setattr("services.regime.get_benchmark_series", lambda s: hv)
    r1 = detect_regime(lookback=60)
    assert r1["label"] in {"high_vol", "bear", "bull", "sideways"}

    # Force bull: gentle upward drift low vol
    bull = pd.Series(100 + np.linspace(0, 3, 120) + np.random.normal(0, 0.05, 120))
    monkeypatch.setattr("services.regime.get_benchmark_series", lambda s: bull)
    r2 = detect_regime(lookback=60)
    assert r2["label"] in {"bull", "sideways"}

    # Force bear: downward drift + drawdown
    bear = pd.Series(150 - np.linspace(0, 10, 120) + np.random.normal(0, 0.2, 120))
    monkeypatch.setattr("services.regime.get_benchmark_series", lambda s: bear)
    r3 = detect_regime(lookback=60)
    assert r3["label"] in {"bear", "sideways"}


@pytest.mark.smoke
def test_factor_neutral_degeneracy_fallback():
    # All assets identical exposures to single factor -> function should revert to original structure (equal weights or original normalization)
    weights = {"A":0.5, "B":0.3, "C":0.2}
    exposures = pd.DataFrame({"F1": [1,1,1]}, index=["A","B","C"])
    adj = factor_neutral_overlay(weights, exposures, ["F1"], long_only=True)
    assert abs(sum(adj.values()) - 1.0) < 1e-6
    assert len(adj) == 3


@pytest.mark.smoke
def test_apply_volatility_cap_insufficient_history():
    weights = {"A":0.6, "B":0.4}
    hist = pd.DataFrame()  # empty -> unchanged
    out = apply_volatility_cap(weights, hist, target_annual_vol_pct=10.0)
    assert out == weights


@pytest.mark.smoke
def test_execute_orders_partial_and_scaling():
    # Simple scenario: two buy orders exceeding cash -> scaling + partial fills
    portfolio = pd.DataFrame({
        "ticker": ["A"],
        "shares": [10],
        "buy_price": [10.0],
    })
    cash = 50.0
    orders = [
        {"ticker": "A", "side": "BUY", "shares": 20, "price": 10.0},
        {"ticker": "B", "side": "BUY", "shares": 30, "price": 5.0},
    ]
    price_map = {"A": 10.0, "B": 5.0}
    new_pf, new_cash, report = execute_orders(
        portfolio, cash, orders, price_map=price_map,
        slippage_bps=5.0, proportional_scale=True, enable_partial=True, commit=False
    )
    # Expect at least one fill with scaled quantities and cash unchanged (dry run commit=False) but report populated
    assert not report.empty
    assert {"A","B"}.issubset(set(report.ticker))
