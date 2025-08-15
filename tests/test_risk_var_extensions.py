import pandas as pd
import numpy as np

from services.risk import compute_var_hit_ratio, compute_position_var_contributions


def test_var_hit_ratio_reasonable():
    # Create synthetic returns ~ normal(0,1%)
    rng = np.random.default_rng(42)
    rets = pd.Series(rng.normal(0, 0.01, size=300))
    hit = compute_var_hit_ratio(rets, level=0.95, window=100)
    # Expected exceedance approx 5% within tolerance 2%-8%
    assert 0.02 <= hit <= 0.08


def test_position_var_contributions_shape():
    # Build minimal history for two tickers + TOTAL
    dates = pd.date_range("2024-01-01", periods=120, freq="D")
    data = []
    base_val_a = 1000
    base_val_b = 1500
    rng = np.random.default_rng(0)
    val_a = base_val_a
    val_b = base_val_b
    for d in dates:
        # random walk
        val_a *= (1 + rng.normal(0, 0.01))
        val_b *= (1 + rng.normal(0, 0.012))
        total = val_a + val_b
        data.append({"date": d, "ticker": "A", "total_equity": None, "total_value": val_a})
        data.append({"date": d, "ticker": "B", "total_equity": None, "total_value": val_b})
        data.append({"date": d, "ticker": "TOTAL", "total_equity": total, "total_value": total})
    hist = pd.DataFrame(data)
    contrib = compute_position_var_contributions(hist, level=0.95, lookback=100)
    # Two tickers -> at least two rows
    assert not contrib.empty
    assert set(contrib['ticker']) == {"A","B"}
    # Contributions should be non-negative
    assert (contrib['contrib_var_pct'] >= 0).all()
