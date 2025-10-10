from __future__ import annotations

"""Unified configuration for Portfolio Management System.

This module consolidates all configuration from:
- app_settings.py (paths and file settings)
- micro_config.py (provider and environment settings)
- config.py (legacy column names and constants)

Single source of truth for all application configuration.
"""

import os
from datetime import date
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _to_path(v: str | Path, base: Optional[Path] = None) -> Path:
    """Convert string to Path, resolving relative paths against base."""
    p = Path(v)
    if not p.is_absolute() and base:
        p = base / p
    return p


class Paths(BaseModel):
    """Container for all file paths used by the application."""
    base_dir: Path
    data_dir: Path
    db_file: Path
    portfolio_csv: Path
    trade_log_csv: Path
    watchlist_file: Path


class Settings(BaseSettings):
    """Unified application settings.
    
    Loads from environment variables with APP_ prefix and .env file.
    Provides single source of truth for all configuration.
    """
    
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8", 
        env_prefix="APP_", 
        extra="ignore"
    )

    # ========== Core Directories ==========
    base_dir: Path = Field(default_factory=lambda: Path(__file__).resolve().parent.parent)
    data_dir: Path | str = Field(default="data")

    # ========== File Paths ==========
    db_file: Path | str = Field(default="data/trading.db")
    portfolio_csv: Path | str = Field(default="data/chatgpt_portfolio_update.csv")
    trade_log_csv: Path | str = Field(default="data/chatgpt_trade_log.csv")
    watchlist_file: Path | str = Field(default="data/watchlist.json")

    # ========== Environment & Provider ==========
    environment: str = Field(default="dev_stage", description="dev_stage or production")
    finnhub_api_key: str = Field(default="", description="Finnhub API key (required in production)")
    cache_dir: str = Field(default="data/cache", description="Cache directory for market data")
    
    # ========== Cache & Performance ==========
    cache_ttl_seconds: int = Field(default=300, ge=0, description="Cache TTL in seconds")
    
    # ========== Trading Calendar ==========
    trading_holidays: List[str] = Field(
        default_factory=list, 
        description="List of YYYY-MM-DD holiday dates when market is closed"
    )
    
    # ========== DataFrame Column Names ==========
    # These are the standardized column names used throughout the application
    COL_TICKER: str = Field(default="Ticker")
    COL_SHARES: str = Field(default="Shares")
    COL_PRICE: str = Field(default="Price")
    COL_COST: str = Field(default="Cost Basis")
    COL_STOP: str = Field(default="Stop Loss")
    COL_CURRENT: str = Field(default="Current Value")
    COL_GAIN_LOSS: str = Field(default="Gain/Loss")
    COL_GAIN_LOSS_PCT: str = Field(default="Gain/Loss %")
    
    # ========== Display Formatting ==========
    currency_precision: int = Field(default=2, ge=0, le=4)
    percentage_precision: int = Field(default=2, ge=0, le=4)
    
    # ========== Date Constants ==========
    @property
    def TODAY(self) -> str:
        """Current date in YYYY-MM-DD format."""
        return date.today().strftime("%Y-%m-%d")

    # ========== Path Validation ==========
    @field_validator(
        "data_dir", "db_file", "portfolio_csv", "trade_log_csv", "watchlist_file", mode="after"
    )
    @classmethod
    def resolve_paths(cls, v: Path | str, info: ValidationInfo) -> Path:
        """Resolve all paths relative to base_dir."""
        base_dir: Path = info.data.get("base_dir")  # type: ignore[assignment]
        return _to_path(v, base=base_dir)

    @property
    def paths(self) -> Paths:
        """Get all resolved file paths."""
        return Paths(
            base_dir=self.base_dir,
            data_dir=Path(self.data_dir),
            db_file=Path(self.db_file),
            portfolio_csv=Path(self.portfolio_csv),
            trade_log_csv=Path(self.trade_log_csv),
            watchlist_file=Path(self.watchlist_file),
        )
    
    # ========== Helper Methods ==========
    
    def is_dev_stage(self) -> bool:
        """Check if running in development/synthetic mode."""
        return self.environment == "dev_stage"
    
    def is_production(self) -> bool:
        """Check if running in production mode with real data."""
        return self.environment == "production"
    
    def require_api_key(self) -> str:
        """Get API key, raising error if not set in production."""
        if self.is_production() and not self.finnhub_api_key:
            raise RuntimeError(
                "FINNHUB_API_KEY is required in production mode. "
                "Set APP_FINNHUB_API_KEY environment variable or add to .env file."
            )
        return self.finnhub_api_key


# ========== Singleton Instance ==========
# Load environment variables (except during pytest to avoid test interference)
if "PYTEST_CURRENT_TEST" not in os.environ:
    load_dotenv(override=False)

settings = Settings()


# ========== Legacy Compatibility Exports ==========
# These maintain backward compatibility with existing code
# TODO: Gradually migrate all code to use settings.COL_TICKER instead of COL_TICKER

COL_TICKER = settings.COL_TICKER
COL_SHARES = settings.COL_SHARES
COL_PRICE = settings.COL_PRICE
COL_COST = settings.COL_COST
COL_STOP = settings.COL_STOP
COL_CURRENT = settings.COL_CURRENT
COL_GAIN_LOSS = settings.COL_GAIN_LOSS
COL_GAIN_LOSS_PCT = settings.COL_GAIN_LOSS_PCT
TODAY = settings.TODAY


__all__ = [
    "settings",
    "Settings",
    "Paths",
    # Legacy exports for backward compatibility
    "COL_TICKER",
    "COL_SHARES",
    "COL_PRICE",
    "COL_COST",
    "COL_STOP",
    "COL_CURRENT",
    "COL_GAIN_LOSS",
    "COL_GAIN_LOSS_PCT",
    "TODAY",
]
