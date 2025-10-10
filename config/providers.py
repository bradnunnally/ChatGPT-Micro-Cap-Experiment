from __future__ import annotations

"""Market data provider factory.

Consolidated provider logic from micro_config.py and legacy config.py.
Provides get_provider() that returns the appropriate market data provider
based on environment settings (dev_stage vs production).
"""

import os
from dataclasses import dataclass
from typing import Optional

from config.settings import settings

# Import provider from micro_config for backward compatibility
try:
    from micro_config import get_provider as micro_get_provider, resolve_env as micro_resolve_env
    from services.providers.finnhub import MarketDataProvider
except Exception:  # pragma: no cover
    # Fallback imports for tests when micro_config unavailable
    from services.providers.finnhub import MarketDataProvider, SyntheticDataProviderExt
    
    def micro_get_provider(env: Optional[str] = None) -> MarketDataProvider:  # type: ignore
        return SyntheticDataProviderExt(seed=42)
    
    def micro_resolve_env(env: Optional[str] = None) -> str:  # type: ignore
        return "dev_stage"


VALID_ENVS = {"dev_stage", "production"}
DEFAULT_ENV = "production"


@dataclass(slots=True)
class AppConfig:
    """Legacy app configuration (deprecated - use settings instead)."""
    env: str


def _validate(env: str) -> str:
    """Validate environment string."""
    if env not in VALID_ENVS:
        raise ValueError(f"Unknown APP_ENV '{env}'. Allowed: {sorted(VALID_ENVS)}")
    return env


def resolve_environment(override: Optional[str] = None) -> str:
    """Resolve the effective environment.

    Precedence: override arg > APP_ENV env var > settings.environment > DEFAULT_ENV
    """
    if override:
        return _validate(override)
    env = os.getenv("APP_ENV") or settings.environment or DEFAULT_ENV
    # Legacy mapping
    if env == "development":
        env = "dev_stage"
    return _validate(env)


def get_provider(override: Optional[str] = None, cli_env: Optional[str] = None) -> MarketDataProvider:
    """Get market data provider for current environment.
    
    Args:
        override: Optional environment override
        cli_env: Optional CLI environment override (alias for override)
        
    Returns:
        MarketDataProvider instance (Synthetic for dev_stage, Finnhub for production)
    """
    eff = override or cli_env
    return micro_get_provider(eff)


def bootstrap_defaults(provider: MarketDataProvider, tickers: list[str], start, end) -> None:
    """Pre-warm provider cache with ticker history (best effort).
    
    Args:
        provider: Market data provider instance
        tickers: List of ticker symbols to warm
        start: Start date for history
        end: End date for history
    """
    for t in tickers:
        try:  # pragma: no cover
            provider.get_history(t, start, end)  # type: ignore
        except Exception:
            pass


def is_dev_stage(env: Optional[str] = None) -> bool:
    """Check if running in development/synthetic mode.
    
    Args:
        env: Optional environment override
        
    Returns:
        True if dev_stage, False if production
    """
    if env is None:
        try:
            return micro_resolve_env(None) == "dev_stage"
        except Exception:
            env = resolve_environment()
    return env == "dev_stage"


__all__ = [
    "AppConfig",
    "resolve_environment",
    "get_provider",
    "bootstrap_defaults",
    "is_dev_stage",
    "MarketDataProvider",
]
