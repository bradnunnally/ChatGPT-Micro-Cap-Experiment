import pytest
import pandas as pd
from services.core.sqlite_repository import SqlitePortfolioRepository
from data.db import init_db


def test_sqlite_repository_crud(tmp_path):
    db_file = tmp_path / "test.db"
    repo = SqlitePortfolioRepository(str(db_file))
    init_db()
    # Save and load
    df = pd.DataFrame(
        {
            "ticker": ["AAPL"],
            "shares": [10],
            "stop_loss": [0],
            "buy_price": [100],
            "cost_basis": [1000],
        }
    )
    repo.save_snapshot(df, 5000)
    result = repo.load()
    assert not result.portfolio.empty
    assert result.cash == 5000
    # Append trade log
    repo.append_trade_log(
        {
            "date": "2025-08-11",
            "ticker": "AAPL",
            "shares_bought": 10,
            "buy_price": 100,
            "cost_basis": 1000,
            "pnl": 0,
            "reason": "test",
            "shares_sold": 0,
            "sell_price": 0,
        }
    )
