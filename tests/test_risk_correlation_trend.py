import pandas as pd
import numpy as np

from services.risk import (
    compute_average_pairwise_correlation,
    compute_rolling_historical_var,
    compute_var_hit_ratio,
    compute_position_var_contributions,
)


def _build_history(num_days: int = 90, tickers: list[str] | None = None) -> pd.DataFrame:
    if tickers is None:
        tickers = ["A","B","C"]
    dates = pd.date_range("2024-01-01", periods=num_days, freq="D")
    rng = np.random.default_rng(123)
    rows: list[dict] = []
    base_vals = {t: 100 + i*10 for i,t in enumerate(tickers)}
    for d in dates:
        total = 0.0
        for t in tickers:
            base = base_vals[t]
            base *= (1 + rng.normal(0, 0.01))
            base_vals[t] = base
            rows.append({"date": d, "ticker": t, "total_value": base, "total_equity": None})
            total += base
        rows.append({"date": d, "ticker": "TOTAL", "total_value": total, "total_equity": total})
    return pd.DataFrame(rows)


def test_average_pairwise_correlation_trend_basic():
    hist = _build_history()
    series = compute_average_pairwise_correlation(hist, window=30)
    # Expect length roughly num_days - window + 1
    assert not series.empty
    assert series.index.is_monotonic_increasing
    assert series.name == "avg_corr_30d"
    # Values should lie within [-1,1]
    assert ((series >= -1) & (series <= 1)).all()


def test_average_pairwise_correlation_requires_two_tickers():
    hist = _build_history(tickers=["ONLY"], num_days=60)
    series = compute_average_pairwise_correlation(hist, window=30)
    assert series.empty


def test_rolling_historical_var_and_hit_ratio_edges():
    # Insufficient length -> hit ratio 0
    rets_short = pd.Series([0.001, -0.002, 0.0005])
    hr = compute_var_hit_ratio(rets_short, level=0.95, window=5)
    assert hr == 0.0
    # Sufficient length random series
    rng = np.random.default_rng(0)
    rets = pd.Series(rng.normal(0, 0.01, size=150))
    rolling_var = compute_rolling_historical_var(rets, window=50)
    # First window-1 entries NaN, rest >=0
    assert rolling_var.iloc[:49].isna().all()
    assert (rolling_var.dropna() >= 0).all()


def test_position_var_contributions_empty_history():
    empty = pd.DataFrame(columns=["date","ticker","total_value","total_equity"])
    contrib = compute_position_var_contributions(empty)
    assert contrib.empty
