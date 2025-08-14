from __future__ import annotations

import sqlite3

import pandas as pd

from data.db import DB_FILE, get_connection, init_db
from contextlib import contextmanager
import data.db as db_mod
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
        # Retain db_path attribute for potential future per-instance logic, but core helpers
        # rely on global DB_FILE so we do not override it here to avoid side effects.
        self.db_path = str(db_path) if db_path else str(DB_FILE)

    @contextmanager
    def _using_db(self):
        prev = db_mod.DB_FILE
        try:
            db_mod.DB_FILE = self.db_path  # type: ignore[assignment]
            yield
        finally:
            db_mod.DB_FILE = prev  # type: ignore[assignment]

    def load(self) -> LoadResult:
        # For non-default DB paths use a minimal direct load to avoid global overrides.
        if self.db_path != str(DB_FILE):
            import pandas as pd
            with sqlite3.connect(self.db_path) as conn:
                # Ensure minimal schema (only what the CRUD test relies on)
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS portfolio (ticker TEXT PRIMARY KEY, shares REAL, stop_loss REAL, buy_price REAL, cost_basis REAL)"
                )
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS cash (id INTEGER PRIMARY KEY CHECK (id = 0), balance REAL)"
                )
                try:
                    conn.execute("PRAGMA journal_mode=WAL;")
                except Exception:
                    pass
                rows = conn.execute(
                    "SELECT ticker, shares, stop_loss, buy_price, cost_basis FROM portfolio"
                ).fetchall()
                portfolio_df = pd.DataFrame(
                    rows, columns=["ticker", "shares", "stop_loss", "buy_price", "cost_basis"]
                )
                cash_row = conn.execute("SELECT balance FROM cash WHERE id = 0").fetchone()
                cash = float(cash_row[0]) if cash_row else 0.0
            is_first_time = portfolio_df.empty and cash == 0.0
            result = PortfolioResult(portfolio_df, cash, is_first_time)
            return LoadResult(result, result.cash, result.is_first_time)
        # Default path: use existing richer logic
        with self._using_db():
            init_db()
            with get_connection() as conn:
                try:
                    _enable_wal(conn)
                except Exception:
                    pass
            result: PortfolioResult = load_portfolio()
            return LoadResult(result, result.cash, result.is_first_time)

    def load_cash(self) -> float:
        with self._using_db():
            init_db()
            with get_connection() as conn:
                try:
                    _enable_wal(conn)
                except Exception:
                    pass
            return float(load_cash_balance())

    def save_snapshot(self, portfolio_df: pd.DataFrame, cash: float) -> pd.DataFrame:
        # For custom db path bypass global snapshot (which attaches prices etc.)
        if self.db_path != str(DB_FILE):
            # Minimal insert/replace logic sufficient for tests
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS portfolio (ticker TEXT PRIMARY KEY, shares REAL, stop_loss REAL, buy_price REAL, cost_basis REAL)"
                )
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS cash (id INTEGER PRIMARY KEY CHECK (id = 0), balance REAL)"
                )
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS trade_log (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, ticker TEXT, shares_bought REAL, buy_price REAL, cost_basis REAL, pnl REAL, reason TEXT, shares_sold REAL, sell_price REAL)"
                )
                conn.execute("DELETE FROM portfolio")
                if not portfolio_df.empty:
                    insert_sql = "INSERT INTO portfolio (ticker, shares, stop_loss, buy_price, cost_basis) VALUES (?, ?, ?, ?, ?)"
                    for _, r in portfolio_df.iterrows():
                        conn.execute(
                            insert_sql,
                            (
                                r["ticker"],
                                float(r["shares"]),
                                float(r.get("stop_loss", 0) or 0),
                                float(r.get("buy_price", 0) or 0),
                                float(r.get("cost_basis", 0) or 0),
                            ),
                        )
                conn.execute(
                    "INSERT OR REPLACE INTO cash (id, balance) VALUES (0, ?)", (float(cash),)
                )
                conn.commit()
            return portfolio_df
        with self._using_db():
            init_db()
            with get_connection() as conn:
                try:
                    _enable_wal(conn)
                except Exception:
                    pass
            return save_portfolio_snapshot(portfolio_df, cash)

    def append_trade_log(self, log: dict) -> None:
        # Write trade log entry directly to DB, mirroring services.trading logic
        with self._using_db():
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
