import pandas as pd
from services.rebalance import execute_orders
from services.strategy import cap_composite_weights, apply_sector_caps


def test_execute_orders_buy_and_sell_flow():
    pf = pd.DataFrame({
        'ticker': ['AAA'],
        'shares': [10],
        'buy_price': [10.0],
        'cost_basis': [100.0],
        'stop_loss': [0.0]
    })
    cash = 100.0
    orders = [
        {'ticker': 'BBB', 'side': 'BUY', 'shares': 5, 'est_price': 10.0},  # cost 50
        {'ticker': 'AAA', 'side': 'SELL', 'shares': 4, 'est_price': 10.0},  # proceeds 40
    ]
    new_pf, new_cash, report = execute_orders(pf, cash, orders)
    assert 'BBB' in new_pf['ticker'].values
    # cash: 100 - 50 + 40 = 90
    assert abs(new_cash - 90.0) < 1e-6
    assert (report['status'] == 'filled').all()


def test_execute_orders_dry_run_and_partial():
    pf = pd.DataFrame({
        'ticker': ['AAA'],
        'shares': [2],
        'buy_price': [10.0],
        'cost_basis': [20.0],
        'stop_loss': [0.0]
    })
    cash = 5.0
    orders = [
        {'ticker': 'AAA', 'side': 'SELL', 'shares': 5, 'est_price': 10.0},  # exceeds holdings -> partial
        {'ticker': 'BBB', 'side': 'BUY', 'shares': 2, 'est_price': 10.0},   # exceeds cash -> scaled/partial
    ]
    new_pf, new_cash, report = execute_orders(pf, cash, orders, commit=False, enable_partial=True, proportional_scale=True)
    # Dry run -> cash unchanged
    assert abs(new_cash - cash) < 1e-9
    # Expect partial_filled status present
    assert 'partial_filled' in set(report['status'])


def test_cap_composite_weights():
    import pandas as pd
    df = pd.DataFrame({
        'strategy': ['s1','s1','s2','s2'],
        'ticker': ['A','B','A','B'],
        'raw_weight': [0.6,0.4,0.6,0.4],
        'strategy_capital': [0.5,0.5,0.5,0.5],
        'weighted_contribution': [0.3,0.2,0.3,0.2],
        'composite_weight': [0.6,0.4,0.6,0.4]
    })
    capped = cap_composite_weights(df, max_weight=0.5)
    # After capping A from 0.6->0.5 weights renormalize so A < 0.6
    comp = capped.drop_duplicates('ticker')[['ticker','composite_weight']]
    a_weight = float(comp[comp.ticker=='A']['composite_weight'])
    assert a_weight <= 0.5 + 1e-9


def test_apply_sector_caps():
    df = pd.DataFrame({
        'strategy': ['s1','s1','s2','s2'],
        'ticker': ['A','B','A','B'],
        'raw_weight': [0.6,0.4,0.6,0.4],
        'strategy_capital': [0.5,0.5,0.5,0.5],
        'weighted_contribution': [0.3,0.2,0.3,0.2],
        'composite_weight': [0.6,0.4,0.6,0.4]
    })
    sector_map = {'A':'TECH','B':'TECH'}
    capped = apply_sector_caps(df, sector_map, sector_cap=0.7)
    comp = capped.drop_duplicates('ticker')[['ticker','composite_weight']]
    tech_sum = comp['composite_weight'].sum()
    assert tech_sum <= 0.7000001


def test_slippage_cost_in_report():
    pf = pd.DataFrame({'ticker':['AAA'],'shares':[5],'buy_price':[10.0],'cost_basis':[50.0],'stop_loss':[0.0]})
    cash = 100.0
    orders = [
        {'ticker':'BBB','side':'BUY','shares':5,'est_price':10.0},
        {'ticker':'AAA','side':'SELL','shares':2,'est_price':10.0},
    ]
    new_pf, new_cash, report = execute_orders(pf, cash, orders, slippage_bps=10)  # 1% bps
    assert 'slippage_cost' in report.columns
    # Aggregate slippage should be finite
    assert report['slippage_cost'].abs().sum() >= 0
