import pandas as pd
from services.strategy import compute_allocation_deltas, generate_rebalance_orders
from services.regime import detect_regime


def test_generate_rebalance_orders_basic():
    portfolio = pd.DataFrame({"ticker": ["AAA"], "shares": [10], "price": [10.0]})
    combined = pd.DataFrame({"ticker": ["AAA","BBB"], "composite_weight": [0.4, 0.6]})
    price_map = {"AAA": 10.0, "BBB": 5.0}
    total_equity = 10*10.0  # 100
    delta = compute_allocation_deltas(portfolio, combined, price_map, total_equity)
    assert not delta.empty
    orders = generate_rebalance_orders(delta, min_shares=1, min_value=1.0)
    # Should include order for BBB (new) and maybe adjust AAA
    tickers = {o['ticker'] for o in orders}
    assert "BBB" in tickers


def test_detect_regime_handles_missing():
    # Without benchmark data this should safely return unknown
    reg = detect_regime(lookback=10)
    assert 'label' in reg
