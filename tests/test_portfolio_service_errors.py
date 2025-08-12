import pandas as pd
import pytest
from services.core.portfolio_service import apply_sell, apply_buy


def test_apply_sell_missing_required_columns():
    df = pd.DataFrame({"ticker": ["AAPL"], "shares": [10]})  # missing buy_price, cost_basis
    with pytest.raises(ValueError):
        apply_sell(df, "AAPL", shares=5, price=150.0)


def test_apply_sell_ticker_not_found():
    df = pd.DataFrame({
        "ticker": ["AAPL"],
        "shares": [10],
        "buy_price": [100.0],
        "cost_basis": [1000.0],
    })
    with pytest.raises(ValueError):
        apply_sell(df, "MSFT", shares=1, price=200.0)


def test_apply_sell_insufficient_shares():
    df = pd.DataFrame({
        "ticker": ["AAPL"],
        "shares": [2],
        "buy_price": [100.0],
        "cost_basis": [200.0],
    })
    with pytest.raises(ValueError):
        apply_sell(df, "AAPL", shares=5, price=150.0)


def test_apply_buy_updates_stop_loss():
    df = pd.DataFrame(columns=["ticker", "shares", "buy_price", "cost_basis", "stop_loss"])
    out = apply_buy(df, "AAPL", shares=1, price=10.0, stop_loss=8.0)
    # Update with new stop loss
    out2 = apply_buy(out, "AAPL", shares=1, price=20.0, stop_loss=15.0)
    assert out2.iloc[0]["stop_loss"] == 15.0
