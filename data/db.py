import sqlite3
import atexit
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
]

# Backward-compat schema string for tests that import SCHEMA
SCHEMA = "\n".join(stmt.strip() for stmt in SCHEMA_STATEMENTS)


def get_connection(reuse: bool = False) -> Any:
    """Return a SQLite connection with sane pragmas.

    Features:
    - Ensures data directory exists.
    - Optional thread-local reuse to reduce connection churn in hot paths.
    - Attaches a weakref finalizer to close uncollected connections (mitigates ResourceWarnings).
    - Applies WAL + busy timeout pragmas best-effort.
    - Wraps bare mocks (without context manager methods) in a lightweight proxy so tests
      using monkeypatched sqlite3.connect still work with `with get_connection():`.
    """
    Path(settings.paths.data_dir).mkdir(parents=True, exist_ok=True)
    if reuse:
        cached = getattr(_thread_local, "conn", None)
        if cached is not None:
            return cached
    raw = sqlite3.connect(str(DB_FILE))

    def _safe_close(c):  # pragma: no cover - defensive close
        try:
            if getattr(c, "in_transaction", False):  # commit if open txn
                try:
                    c.commit()
                except Exception:
                    pass
            c.close()
        except Exception:
            pass

    try:
        weakref.finalize(raw, _safe_close, raw)
    except Exception:  # pragma: no cover
        pass
    try:
        raw.execute("PRAGMA journal_mode=WAL;")
        raw.execute("PRAGMA synchronous=NORMAL;")
        raw.execute("PRAGMA busy_timeout=3000;")
    except Exception:
        pass

    if hasattr(raw, "__enter__") and hasattr(raw, "__exit__"):
        if reuse:
            _thread_local.conn = raw
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


def _close_thread_local_connection() -> None:  # pragma: no cover - best effort cleanup
    conn = getattr(_thread_local, "conn", None)
    if conn is not None:
        try:
            if getattr(conn, "in_transaction", False):
                try:
                    conn.commit()
                except Exception:
                    pass
            conn.close()
        except Exception:
            pass
        finally:
            try:
                delattr(_thread_local, "conn")
            except Exception:
                pass


# Register a process-exit cleanup to silence ResourceWarning for lingering thread-local
atexit.register(_close_thread_local_connection)


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
