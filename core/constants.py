"""Centralized constants for the trading application.

This module provides shared constants to eliminate duplication and ensure
consistency across the application.
"""

from __future__ import annotations

from typing import Final

# ===============================
# Database Table Names
# ===============================

TABLE_PORTFOLIO: Final[str] = "portfolio"
TABLE_CASH: Final[str] = "cash"
TABLE_TRADE_LOG: Final[str] = "trade_log"
TABLE_PORTFOLIO_HISTORY: Final[str] = "portfolio_history"
TABLE_EVENTS: Final[str] = "events"
TABLE_MARKET_HISTORY: Final[str] = "market_history"

# All main tables for operations like clearing, backup, etc.
ALL_MAIN_TABLES: Final[list[str]] = [
    TABLE_PORTFOLIO,
    TABLE_CASH,
    TABLE_TRADE_LOG,
    TABLE_PORTFOLIO_HISTORY,
]

# All tables including auxiliary ones
ALL_TABLES: Final[list[str]] = [
    TABLE_PORTFOLIO,
    TABLE_CASH,
    TABLE_TRADE_LOG,
    TABLE_PORTFOLIO_HISTORY,
    TABLE_EVENTS,
    TABLE_MARKET_HISTORY,
]

# ===============================
# Database Column Names
# ===============================

# Portfolio table columns
PORTFOLIO_COLS = {
    "TICKER": "ticker",
    "SHARES": "shares",
    "STOP_LOSS": "stop_loss",
    "BUY_PRICE": "buy_price",
    "COST_BASIS": "cost_basis",
}

# Cash table columns
CASH_COLS = {
    "ID": "id",
    "BALANCE": "balance",
}

# Trade log columns
TRADE_LOG_COLS = {
    "ID": "id",
    "DATE": "date",
    "TICKER": "ticker",
    "SHARES_BOUGHT": "shares_bought",
    "BUY_PRICE": "buy_price",
    "COST_BASIS": "cost_basis",
    "PNL": "pnl",
    "REASON": "reason",
    "SHARES_SOLD": "shares_sold",
    "SELL_PRICE": "sell_price",
}

# Portfolio history columns
PORTFOLIO_HISTORY_COLS = {
    "DATE": "date",
    "TICKER": "ticker",
    "SHARES": "shares",
    "COST_BASIS": "cost_basis",
    "STOP_LOSS": "stop_loss",
    "CURRENT_PRICE": "current_price",
    "TOTAL_VALUE": "total_value",
    "PNL": "pnl",
    "ACTION": "action",
    "CASH_BALANCE": "cash_balance",
    "TOTAL_EQUITY": "total_equity",
}

# ===============================
# Price Data Column Names
# ===============================

# Common price column names in various data sources
PRICE_COLUMN_NAMES: Final[list[str]] = ["price", "last", "c", "close", "Close", "current_price"]
CLOSE_COLUMN_NAMES: Final[list[str]] = ["Close", "close", "price", "last"]
PCT_CHANGE_COLUMN_NAMES: Final[list[str]] = ["percent", "pct_change", "change_percent", "dp", "percentage"]

# Standard DataFrame columns for price data
PRICE_DATA_COLUMNS: Final[list[str]] = ["ticker", "current_price", "pct_change"]

# ===============================
# Configuration Constants
# ===============================

# Cash table ID constraint (always 0 for single cash balance)
CASH_ID: Final[int] = 0

# Default cache TTL values (in seconds)
PRICE_CACHE_TTL: Final[int] = 300  # 5 minutes
DEFAULT_CACHE_TTL: Final[float] = 300.0

# Retry configuration defaults
DEFAULT_RETRY_ATTEMPTS: Final[int] = 3
DEFAULT_RETRY_BASE_DELAY: Final[float] = 0.3
DEFAULT_RETRY_MAX_DELAY: Final[float] = 60.0
DEFAULT_RETRY_JITTER_RANGE: Final[float] = 0.2

# ===============================
# Validation Constants
# ===============================

# Maximum values for validation
MAX_SHARES: Final[int] = 1_000_000
MAX_PRICE: Final[float] = 10_000.0
MAX_TICKER_LENGTH: Final[int] = 10

# Minimum values
MIN_SHARES: Final[int] = 1
MIN_PRICE: Final[float] = 0.01

# ===============================
# File and Path Constants
# ===============================

# File extensions
DB_FILE_EXTENSION: Final[str] = ".db"
CSV_FILE_EXTENSION: Final[str] = ".csv"
JSON_FILE_EXTENSION: Final[str] = ".json"

# Default file names
DEFAULT_DB_NAME: Final[str] = "trading.db"
DEFAULT_WATCHLIST_NAME: Final[str] = "watchlist.json"

# ===============================
# Environment and Feature Flags
# ===============================

# Environment variable names
ENV_NO_DEV_SEED: Final[str] = "NO_DEV_SEED"
ENV_DISABLE_CACHE: Final[str] = "DISABLE_CACHE"
ENV_TEST_MODE: Final[str] = "TEST_MODE"

# ===============================
# Error Messages
# ===============================

# Common error message templates
ERROR_MESSAGES = {
    "INVALID_TICKER": "Invalid ticker format.",
    "INVALID_SHARES": "Shares must be a positive integer.",
    "INVALID_PRICE": "Price must be a positive number.",
    "TICKER_TOO_LONG": f"Ticker symbol too long (max {MAX_TICKER_LENGTH} characters).",
    "SHARES_TOO_LARGE": f"Share quantity too large (max {MAX_SHARES:,}).",
    "PRICE_TOO_HIGH": f"Price seems unrealistic (max ${MAX_PRICE:,.2f}).",
    "EMPTY_TICKER": "Ticker symbol cannot be empty.",
    "SHARES_NOT_INTEGER": "Shares must be a whole number.",
    "PRICE_NOT_NUMERIC": "Price must be a valid number.",
}