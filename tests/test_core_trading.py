import pytest
import pandas as pd
from services.trading import manual_buy, manual_sell
from unittest.mock import patch


def test_manual_buy_and_sell():
    df = pd.DataFrame(columns=["ticker", "shares", "stop_loss", "price", "cost_basis"])
    cash = 1000.0
    with patch("services.trading.get_day_high_low", return_value=(200, 50)):
        ok, msg, df2, cash2 = manual_buy("AAPL", 2, 100, 90, portfolio_df=df, cash=cash)
        assert ok is True
        assert "Bought" in msg
        assert cash2 == 800.0
        ok, msg, df3, cash3 = manual_sell("AAPL", 1, 120, portfolio_df=df2, cash=cash2)
        assert ok is True
        assert "Sold" in msg
        assert cash3 == 920.0
