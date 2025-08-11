"""Domain-specific exception hierarchy for consistent error handling."""

from __future__ import annotations


class AppError(Exception):
    """Base application error (do not raise directly)."""


class ValidationError(AppError, ValueError):
    """Invalid user or model input."""


class MarketDataError(AppError):
    """Problems fetching or interpreting market data (base class)."""


class MarketDataDownloadError(MarketDataError, RuntimeError):
    """Failed while downloading market data."""


class NoMarketDataError(MarketDataError, ValueError):
    """No market data available for request."""


class NotFoundError(AppError):
    """Requested entity or resource not found."""


class RepositoryError(AppError, RuntimeError):
    """Database/repository operation failed or is unavailable."""


class ConfigError(AppError):
    """Configuration missing/invalid."""


class PermissionError(AppError):
    """Operation not permitted for current context/user."""
