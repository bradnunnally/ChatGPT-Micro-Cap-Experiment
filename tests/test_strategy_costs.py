import pandas as pd
from strategies.sma import SMACrossStrategy

def test_sma_strategy_transaction_costs_reduce_returns():
    prices = pd.Series([100,101,102,101,100,99,100,101,102,103])
    # Force more trades by choosing small windows
    strat_no_cost = SMACrossStrategy(fast=2, slow=3, slippage_bps=0.0, commission_bps=0.0)
    res_no = strat_no_cost.run(prices)
    strat_cost = SMACrossStrategy(fast=2, slow=3, slippage_bps=5.0, commission_bps=5.0)  # 10 bps per change
    res_cost = strat_cost.run(prices)
    assert res_cost.metrics['total_return_pct'] <= res_no.metrics['total_return_pct']
    assert res_cost.metrics['transaction_cost_bps_total'] > 0
