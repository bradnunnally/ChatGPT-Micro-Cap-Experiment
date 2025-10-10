"""Unified configuration package.

This package provides centralized configuration for the Portfolio Management System.
All application settings, constants, and provider factories are exported from here.

Usage:
    from config import settings, get_provider, COL_TICKER
    
    # Access settings
    db_path = settings.db_file
    api_key = settings.finnhub_api_key
    
    # Get market data provider
    provider = get_provider()
    
    # Use column constants
    df[COL_TICKER] = tickers
"""

from __future__ import annotations

# Import and re-export everything from settings (includes legacy constants)
from .settings import (
    settings,
    Settings,
    Paths,
    # Column constants
    COL_TICKER,
    COL_SHARES,
    COL_PRICE,
    COL_COST,
    COL_STOP,
    COL_CURRENT,
    COL_GAIN_LOSS,
    COL_GAIN_LOSS_PCT,
    TODAY,
)

# Import and re-export provider functions
from .providers import (
    get_provider,
    is_dev_stage,
    resolve_environment,
    bootstrap_defaults,
    AppConfig,
    MarketDataProvider,
)

__all__ = [
    # Settings
    "settings",
    "Settings", 
    "Paths",
    # Column constants (for backward compatibility)
    "COL_TICKER",
    "COL_SHARES",
    "COL_PRICE",
    "COL_COST",
    "COL_STOP",
    "COL_CURRENT",
    "COL_GAIN_LOSS",
    "COL_GAIN_LOSS_PCT",
    "TODAY",
    # Provider functions
    "get_provider",
    "is_dev_stage",
    "resolve_environment",
    "bootstrap_defaults",
    "AppConfig",
    "MarketDataProvider",
]

# Keep settings submodule available via `from config.settings import settings`.
# No explicit import here to avoid import-time side effects; normal submodule
# import resolution will find `config/settings.py` when referenced.
