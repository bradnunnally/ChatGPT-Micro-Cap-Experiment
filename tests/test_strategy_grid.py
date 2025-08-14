import pandas as pd
from strategies.grid import run_sma_grid, summarize_results


def test_run_sma_grid_and_summarize():
    prices = pd.Series([100 + i for i in range(60)])
    results = run_sma_grid(prices, fast_values=[3,5], slow_values=[10,15])
    assert results, "Expected some results"
    summary = summarize_results(results)
    assert not summary.empty
    # Ensure ranking and metrics columns
    for col in ["strategy", "fast", "slow", "total_return_pct", "max_drawdown_pct", "sharpe_like", "rank", "train_total_return_pct", "test_total_return_pct"]:
        assert col in summary.columns
    # Fast < slow rule enforced
    for _, row in summary.iterrows():
        assert row["fast"] < row["slow"]
