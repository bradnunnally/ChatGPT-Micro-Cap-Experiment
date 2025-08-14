import pandas as pd
from services.backtest import run_backtest, simple_moving_average_strategy

def test_backtest_runs():
    prices = pd.Series([100 + i for i in range(60)])
    res = run_backtest(prices)
    assert res.equity_curve.iloc[-1] > 0
    assert "total_return_pct" in res.metrics

def test_sma_strategy_signals():
    prices = pd.Series([100] * 10 + [110] * 30 + [90] * 20)
    res = simple_moving_average_strategy(prices)
    assert not res.trades.empty
    assert res.metrics["max_drawdown_pct"] <= 0
