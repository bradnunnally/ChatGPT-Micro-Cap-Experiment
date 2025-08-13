from __future__ import annotations

"""Legacy provider factory (deprecated).

This module now delegates to :mod:`micro_config` so the application uses the
Finnhub/Synthetic provider system exclusively. Legacy yfinance paths removed.
retained only for backward compatible tests and will be removed.
"""

import os
from dataclasses import dataclass
from typing import Optional
from datetime import date

from dotenv import load_dotenv
try:  # pragma: no cover
    from micro_config import get_provider as micro_get_provider
    from micro_data_providers import MarketDataProvider as DataProvider  # type: ignore
except Exception:  # Fallback for tests expecting DataProvider symbol
    from data_providers import SyntheticDataProvider as DataProvider  # type: ignore

VALID_ENVS = {"dev_stage", "production"}
DEFAULT_ENV = "dev_stage"  # default to synthetic/offline mode for safety


@dataclass
class AppConfig:
    env: str


def _read_env_var(raw: Optional[str]) -> str:
    if not raw:
        return DEFAULT_ENV
    if raw not in VALID_ENVS:
        raise ValueError(f"Unknown APP_ENV '{raw}'. Allowed: {sorted(VALID_ENVS)}")
    return raw


def resolve_environment(cli_env: Optional[str] = None) -> str:
    load_dotenv(override=False)
    if cli_env:
        return _read_env_var(cli_env)
    return _read_env_var(os.environ.get("APP_ENV"))


def get_provider(cli_env: Optional[str] = None):  # type: ignore[override]
    """Return micro provider (Synthetic in dev_stage, Finnhub in production).

    Falls back to synthetic only if micro modules unavailable.
    """
    try:
        return micro_get_provider(cli_env)  # type: ignore[misc]
    except Exception:  # pragma: no cover - degraded path
        # Late import fallback to avoid circulars
        from data_providers import SyntheticDataProvider  # type: ignore
        return SyntheticDataProvider(seed=123)


def bootstrap_defaults(provider: DataProvider, tickers: list[str], start: date, end: date) -> None:
    for t in tickers:
        try:
            provider.get_history(t, start, end)
        except Exception:
            pass


def is_dev_stage(env: Optional[str] = None) -> bool:
    if env is None:
        try:
            from micro_config import resolve_env as _resolve_env  # type: ignore
            return _resolve_env(None) == "dev_stage"
        except Exception:
            env = resolve_environment()
    return env == "dev_stage"

__all__ = ["get_provider", "resolve_environment", "bootstrap_defaults", "AppConfig", "is_dev_stage"]
