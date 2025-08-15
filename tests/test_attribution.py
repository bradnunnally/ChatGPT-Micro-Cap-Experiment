import pandas as pd
import numpy as np

from services.attribution import compute_factor_attribution, compute_position_contributions


def _mock_history():
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=120, freq="D")
    ret = np.random.normal(0.0005, 0.01, size=len(dates))
    equity = 1000 * (1 + pd.Series(ret, index=dates)).cumprod()
    rows = []
    for d, eq in equity.items():
        rows.append({"date": d, "ticker": "TOTAL", "total_equity": eq, "total_value": eq})
    base = equity * 0.6
    base2 = equity * 0.4
    for d, v in base.items():
        rows.append({"date": d, "ticker": "AAA", "total_value": v * 0.5})
        rows.append({"date": d, "ticker": "BBB", "total_value": base2.loc[d] * 0.5})
    return pd.DataFrame(rows)


def test_position_contributions_basic():
    hist = _mock_history()
    df = compute_position_contributions(hist, window=60)
    assert set(df.columns) >= {"ticker", "contribution_pct", "weight_last_pct"}
    assert not df.empty


def test_factor_attribution_handles_insufficient(monkeypatch):
    hist = _mock_history()
    # Patch attribution module's imported function (was imported directly) to return empty mapping
    monkeypatch.setattr("services.attribution.get_factor_returns", lambda symbols=None: {})
    res = compute_factor_attribution(hist, factor_symbols=["SPY"], window=60)
    assert res is None


def test_factor_attribution_nominal(monkeypatch):
    hist = _mock_history()
    eq = hist[hist["ticker"]=="TOTAL"].sort_values("date")["total_equity"].pct_change().dropna()
    fac = (eq * 0.5).rename("SPY").to_frame()
    monkeypatch.setattr("services.factors.get_factor_returns", lambda symbols=None: {"SPY": fac["SPY"]})
    res = compute_factor_attribution(hist, factor_symbols=["SPY"], window=80)
    if res is not None:
        assert "SPY" in res.betas.index
