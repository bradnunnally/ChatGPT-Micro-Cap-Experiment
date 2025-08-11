
import pytest
import pandas as pd
from services.trading import manual_buy, manual_sell
from data.portfolio import save_portfolio_snapshot
from data.db import init_db, get_connection
from unittest.mock import patch

def test_buy_sell_snapshot_integration():
    init_db()
    df = pd.DataFrame(columns=["ticker", "shares", "stop_loss", "price", "cost_basis"])
    cash = 1000.0
    with patch("services.trading.get_day_high_low", return_value=(200, 50)):
        ok, msg, df2, cash2 = manual_buy("AAPL", 2, 100, 90, portfolio_df=df, cash=cash)
        assert ok is True
        ok, msg, df3, cash3 = manual_sell("AAPL", 2, 120, portfolio_df=df2, cash=cash2)
        assert ok is True
        snap = save_portfolio_snapshot(df3, cash3)
        assert not snap.empty
        with get_connection() as conn:
            rows = conn.execute("SELECT * FROM portfolio_history WHERE ticker='TOTAL'").fetchall()
            assert rows
