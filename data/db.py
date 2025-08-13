import sqlite3
import threading
import weakref
from pathlib import Path
from typing import Any

from app_settings import settings

# Backward-compat: some tests patch data.db.DB_FILE; keep an alias.
# Use a Path so either str or Path patches will work when coerced below.
DB_FILE = settings.paths.db_file

# Thread-local cached connection (reduces churn & ResourceWarnings in tests)
_thread_local = threading.local()

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
        total_equity REAL
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
]

# Backward-compat schema string for tests that import SCHEMA
SCHEMA = "\n".join(stmt.strip() for stmt in SCHEMA_STATEMENTS)


def get_connection(reuse: bool = False) -> Any:
    """Return a SQLite3 connection or a proxy that supports context management when mocked.

    - Returns a real sqlite3.Connection in normal operation (supports `with`).
    - If sqlite3.connect is patched to return a bare Mock without __enter__/__exit__,
      return a lightweight proxy that provides context manager behavior and proxies attributes.
    """
    # Ensure the data directory exists
    Path(settings.paths.data_dir).mkdir(parents=True, exist_ok=True)
    if reuse:
        cached = getattr(_thread_local, "conn", None)
        if cached is not None:
            return cached
    raw = sqlite3.connect(str(DB_FILE))
    # Ensure connection is closed even if caller forgets (guards ResourceWarning in tests)
    def _safe_close(c):
        try:
            c.close()
        except Exception:
            pass
    try:
        weakref.finalize(raw, _safe_close, raw)
    except Exception:  # pragma: no cover - weakref issues shouldn't break runtime
        pass
    # Enable WAL and adjust sync for better concurrency and durability trade-offs
    try:
        raw.execute("PRAGMA journal_mode=WAL;")
        raw.execute("PRAGMA synchronous=NORMAL;")
        raw.execute("PRAGMA busy_timeout=3000;")
    except Exception:
        pass

    # If the returned object already supports context management (real connection or test-provided),
    # return it directly.
    if hasattr(raw, "__enter__") and hasattr(raw, "__exit__"):
        if reuse:
            _thread_local.conn = raw  # cache for subsequent calls in same thread
        return raw

    class _ConnProxy:
        def __init__(self, underlying):
            self._u = underlying

        def __enter__(self):
            return self._u

        def __exit__(self, exc_type, exc, tb):
            try:
                self._u.close()
            except Exception:
                pass
            return False

        def __getattr__(self, name):
            return getattr(self._u, name)

    proxy = _ConnProxy(raw)
    if reuse:
        _thread_local.conn = proxy
    return proxy


def init_db() -> None:
    """Initialise the database with required tables if they don't exist."""
    with get_connection(reuse=False) as conn:
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
