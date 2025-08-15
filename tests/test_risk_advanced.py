import pandas as pd
from services.risk import historical_var, historical_es, compute_correlation_matrix, compute_ticker_return_matrix

def test_historical_var_es_basic():
    # Simulate returns with known negative tail
    returns = pd.Series([0.01, 0.02, -0.03, 0.005, -0.015, 0.007, -0.025, 0.004, 0.003, -0.02])
    var95 = historical_var(returns, 0.95)
    es95 = historical_es(returns, 0.95)
    assert var95 >= 0
    assert es95 >= 0
    # ES should be >= VaR (average of tail losses typically larger magnitude)
    assert es95 >= var95 or abs(es95 - var95) < 1e-6


def test_correlation_matrix_shapes():
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    data = []
    for t in ["A", "B", "C"]:
        base = 100 + (pd.Series(range(10)) * (1 if t == 'A' else 2 if t=='B' else 3)).values
        data.extend([{ 'date': d, 'ticker': t, 'total_value': float(base[i]), 'total_equity': float(base[i]) } for i,d in enumerate(dates)])
    df = pd.DataFrame(data)
    ret_mat = compute_ticker_return_matrix(df)
    corr = compute_correlation_matrix(df)
    assert not ret_mat.empty
    assert corr.shape == (3,3)
    assert all(corr.columns == ["A","B","C"])  # order by ticker
