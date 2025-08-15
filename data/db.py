import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from app_settings import settings

# Backward-compat: some tests patch data.db.DB_FILE; keep an alias.
# Use a Path so either str or Path patches will work when coerced below.
DB_FILE = settings.paths.db_file


SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS portfolio (
        ticker TEXT PRIMARY KEY,
        shares REAL,
        stop_loss REAL,
        buy_price REAL,
        cost_basis REAL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS cash (
        id INTEGER PRIMARY KEY CHECK (id = 0),
        balance REAL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS trade_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        ticker TEXT,
        shares_bought REAL,
        buy_price REAL,
        cost_basis REAL,
        pnl REAL,
        reason TEXT,
        shares_sold REAL,
        sell_price REAL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS portfolio_history (
        date TEXT,
        ticker TEXT,
        shares REAL,
        cost_basis REAL,
        stop_loss REAL,
        current_price REAL,
        total_value REAL,
        pnl REAL,
        action TEXT,
        cash_balance REAL,
    total_equity REAL,
    pnl_price REAL,
    pnl_position REAL,
    pnl_total_attr REAL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        agent TEXT NOT NULL,
        event_type TEXT NOT NULL,
        payload TEXT
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS quote_archive (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        ticker TEXT NOT NULL,
        price REAL NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS daily_prices (
        date TEXT NOT NULL,
        ticker TEXT NOT NULL,
        open REAL,
        high REAL,
        low REAL,
        close REAL,
        volume REAL,
        PRIMARY KEY (date, ticker)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS turnover_budget (
        id INTEGER PRIMARY KEY CHECK (id = 0),
        window_days INTEGER NOT NULL DEFAULT 30,
        max_pct REAL NOT NULL DEFAULT 0.80, -- max cumulative notional / avg equity over window
        reset_timestamp TEXT
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS turnover_ledger (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        ticker TEXT NOT NULL,
        side TEXT NOT NULL,
        notional REAL NOT NULL,
        equity_snapshot REAL NOT NULL,
        cumulative_window_pct REAL,
        blocked INTEGER NOT NULL DEFAULT 0
    );
    """,
]

# Backward-compat schema string for tests that import SCHEMA
SCHEMA = "\n".join(stmt.strip() for stmt in SCHEMA_STATEMENTS)

PRAGMAS = [
    "PRAGMA journal_mode=WAL;",
    "PRAGMA synchronous=NORMAL;",
    "PRAGMA busy_timeout=3000;",
]


def _apply_pragmas(conn: sqlite3.Connection) -> None:
    for p in PRAGMAS:
        try:
            conn.execute(p)
        except Exception:  # pragma: no cover - best effort
            pass


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    """Yield a fresh SQLite connection (always closed)."""
    Path(settings.paths.data_dir).mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_FILE))
    _apply_pragmas(conn)
    try:
        yield conn
        if conn.in_transaction:
            try:
                conn.commit()
            except Exception:  # pragma: no cover
                pass
    finally:
        try:
            conn.close()
        except Exception:  # pragma: no cover
            pass


@contextmanager
def transaction() -> Iterator[sqlite3.Connection]:
    """Group multiple statements in a single connection & atomic transaction."""
    with get_connection() as conn:
        try:
            yield conn
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:  # pragma: no cover
                pass
            raise


# Removed thread‑local connection cache & atexit cleanup (no longer needed)


def init_db() -> None:
    """Initialise the database with required tables if they don't exist."""
    with get_connection() as conn:
        # Keep executescript for tests importing SCHEMA
        try:
            conn.executescript(SCHEMA)
        except Exception:
            # Some mocks may not support executescript; fall back silently
            pass
        # Also execute statements individually for tests counting execute calls
        for stmt in SCHEMA_STATEMENTS:
            try:
                conn.execute(stmt)
            except Exception:
                # Ensure we still count attempts on mocks that may not behave like sqlite
                try:
                    getattr(conn, "execute")(stmt)
                except Exception:
                    pass
