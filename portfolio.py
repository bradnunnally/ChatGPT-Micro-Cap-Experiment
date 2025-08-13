from typing import List
from pathlib import Path
import json
import pandas as pd

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
DEFAULT_DEV_TICKERS = ["AAPL", "MSFT", "NVDA"]


def ensure_schema(df: pd.DataFrame) -> pd.DataFrame:
    """Return ``df`` with all expected portfolio columns present."""

    for col in PORTFOLIO_COLUMNS:
        if col not in df.columns:
            df[col] = 0.0 if col != "ticker" else ""
    return df[PORTFOLIO_COLUMNS].copy()


def _load_state_raw() -> dict:
    if not PORTFOLIO_STATE_FILE.exists():
        return {"tickers": []}
    try:
        return json.loads(PORTFOLIO_STATE_FILE.read_text())
    except Exception:  # pragma: no cover
        return {"tickers": []}


def _save_state_raw(state: dict) -> None:
    PORTFOLIO_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    PORTFOLIO_STATE_FILE.write_text(json.dumps(state, indent=2))


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
    if env == "dev_stage" and not tickers:
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
]
