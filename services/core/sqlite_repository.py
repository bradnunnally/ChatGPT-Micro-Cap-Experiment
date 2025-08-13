from __future__ import annotations

import sqlite3

import pandas as pd

from data.db import DB_FILE, get_connection, init_db
from data.portfolio import (
    PortfolioResult,
    load_cash_balance,
    load_portfolio,
    save_portfolio_snapshot,
)
from services.core.repository import LoadResult, PortfolioRepository


def _enable_wal(conn: sqlite3.Connection) -> None:
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=3000;")
    except Exception:
        pass


class SqlitePortfolioRepository(PortfolioRepository):
    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = str(db_path) if db_path else str(DB_FILE)

    def load(self) -> LoadResult:
        init_db()
        with get_connection() as conn:
            try:
                _enable_wal(conn)
            except Exception:
                pass
        result: PortfolioResult = load_portfolio()
        return LoadResult(result, result.cash, result.is_first_time)

    def load_cash(self) -> float:
        init_db()
        with get_connection() as conn:
            try:
                _enable_wal(conn)
            except Exception:
                pass
        return float(load_cash_balance())

    def save_snapshot(self, portfolio_df: pd.DataFrame, cash: float) -> pd.DataFrame:
        init_db()
        with get_connection() as conn:
            try:
                _enable_wal(conn)
            except Exception:
                pass
        return save_portfolio_snapshot(portfolio_df, cash)

    def append_trade_log(self, log: dict) -> None:
        # Write trade log entry directly to DB, mirroring services.trading logic
        init_db()
        with get_connection() as conn:
            df = pd.DataFrame([log])
            df = df.rename(
                columns={
                    "Date": "date",
                    "Ticker": "ticker",
                    "Shares Bought": "shares_bought",
                    "Buy Price": "buy_price",
                    "Cost Basis": "cost_basis",
                    "PnL": "pnl",
                    "Reason": "reason",
                    "Shares Sold": "shares_sold",
                    "Sell Price": "sell_price",
                }
            )
            df.to_sql("trade_log", conn, if_exists="append", index=False)
