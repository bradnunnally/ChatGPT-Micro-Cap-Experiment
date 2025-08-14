from typing import List, Callable
from pathlib import Path
import json
import pandas as pd
from app_settings import settings

# ---------------------------------------------------------------------------
# Portfolio schema and helpers
# ---------------------------------------------------------------------------

PORTFOLIO_COLUMNS: List[str] = [
    "ticker",
    "shares",
    "stop_loss",
    "buy_price",
    "cost_basis",
]
PORTFOLIO_STATE_FILE = Path("data/portfolio.json")
# Increment when the on-disk JSON portfolio state structure changes.
SCHEMA_VERSION = 1

# Migration registry: mapping from old_version -> function that mutates/returns new state dict.
_MIGRATIONS: dict[int, Callable[[dict], dict]] = {}


def register_migration(version: int):  # pragma: no cover - tiny decorator
    def _wrap(fn: Callable[[dict], dict]):
        _MIGRATIONS[version] = fn
        return fn
    return _wrap


@register_migration(0)
def _migrate_0_to_1(state: dict) -> dict:
    """Initial migration (adds schema_version key if missing).

    Version 0 only stored '{"tickers": [...]}'. For v1 we formalize the schema_version field.
    Future keys (e.g. position metadata) can be added here with sensible defaults.
    """
    state.setdefault("tickers", [])
    state["schema_version"] = 1
    return state
DEFAULT_DEV_TICKERS = ["AAPL", "MSFT", "NVDA"]


def ensure_schema(df: pd.DataFrame) -> pd.DataFrame:
    """Return ``df`` with all expected portfolio columns present."""

    for col in PORTFOLIO_COLUMNS:
        if col not in df.columns:
            df[col] = 0.0 if col != "ticker" else ""
    return df[PORTFOLIO_COLUMNS].copy()


def _load_state_raw() -> dict:
    if not PORTFOLIO_STATE_FILE.exists():
        return {"tickers": [], "schema_version": SCHEMA_VERSION}
    try:
        raw = json.loads(PORTFOLIO_STATE_FILE.read_text())
    except Exception:  # pragma: no cover - corrupted file fallback
        return {"tickers": [], "schema_version": SCHEMA_VERSION}
    return _maybe_migrate(raw)


def _save_state_raw(state: dict) -> None:
    # Always persist with current schema version for forward simplicity
    state = dict(state)
    state["schema_version"] = SCHEMA_VERSION
    PORTFOLIO_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    PORTFOLIO_STATE_FILE.write_text(json.dumps(state, indent=2))


def _maybe_migrate(state: dict) -> dict:
    """Apply in-order migrations until state['schema_version'] == SCHEMA_VERSION.

    Safe & idempotent: unknown future versions return early (user upgraded code then downgraded).
    """
    version = int(state.get("schema_version", 0))
    if version > SCHEMA_VERSION:  # Newer file than code understands; leave untouched.
        return state
    while version < SCHEMA_VERSION:
        migrate_fn = _MIGRATIONS.get(version)
        if not migrate_fn:
            # Missing migration function; best-effort upgrade by stamping current version.
            state["schema_version"] = SCHEMA_VERSION
            return state
        state = migrate_fn(state)
        version = int(state.get("schema_version", version + 1))
    return state


def load_portfolio_state() -> list[str]:
    return list(dict.fromkeys(_load_state_raw().get("tickers", [])))


def save_portfolio_state(tickers: list[str]) -> None:
    _save_state_raw({"tickers": sorted(set(tickers))})


def add_ticker(ticker: str) -> list[str]:
    tickers = load_portfolio_state()
    up = ticker.upper()
    if up not in tickers:
        tickers.append(up)
        save_portfolio_state(tickers)
    return tickers


def remove_ticker(ticker: str) -> list[str]:
    tickers = [t for t in load_portfolio_state() if t != ticker.upper()]
    save_portfolio_state(tickers)
    return tickers


def ensure_dev_defaults(env: str) -> list[str]:
    tickers = load_portfolio_state()
    # Centralized flag (NO_DEV_SEED) now pulled from settings instead of raw os.getenv in call sites
    if env == "dev_stage" and not tickers and not getattr(settings, "no_dev_seed", False):
        tickers = DEFAULT_DEV_TICKERS.copy()
        save_portfolio_state(tickers)
    return tickers


__all__ = [
    "ensure_schema",
    "load_portfolio_state",
    "save_portfolio_state",
    "add_ticker",
    "remove_ticker",
    "ensure_dev_defaults",
    "SCHEMA_VERSION",
]
