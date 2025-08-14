import pandas as pd
from services.risk import compute_rolling_beta_series, compute_rolling_betas


def test_compute_rolling_beta_series_basic():
    bench_prices = pd.Series(100 + (pd.Series(range(120)) * 0.5))
    # Linear relation w/out noise => beta should be near constant scale ~1.0 due to identical shape of returns
    port_prices = bench_prices * 1.0
    beta_60 = compute_rolling_beta_series(port_prices, bench_prices, window=60)
    assert not beta_60.empty
    approx = float(beta_60.tail(10).mean())
    assert 0.95 < approx < 1.05


def test_compute_rolling_betas_multiple_windows():
    # Deterministic patterned returns
    pattern = [0.001, -0.0005, 0.002, -0.0015, 0.0008]
    bench_rets = pattern * 24  # 120 points
    bench_prices = [100.0]
    for r in bench_rets:
        bench_prices.append(bench_prices[-1] * (1 + r))
    bench_series = pd.Series(bench_prices[1:])
    # Portfolio scaled returns (beta target ~0.8)
    port_prices = [100.0]
    for r in bench_rets:
        port_prices.append(port_prices[-1] * (1 + r * 0.8))
    port_series = pd.Series(port_prices[1:])
    out = compute_rolling_betas(port_series, bench_series, windows=[30, 60, 90])
    assert set(out.keys()).issubset({30, 60, 90})
    for s in out.values():
        assert not s.empty
    # Combine last segments and average
    last_avg = float(pd.concat(out.values()).tail(20).mean())
    assert 0.7 < last_avg < 0.9
