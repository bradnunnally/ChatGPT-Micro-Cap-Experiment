from __future__ import annotations
"""Deprecated legacy provider selection (will be removed).

Now superseded by :mod:`micro_config` which provides Finnhub (production) and
Synthetic (dev_stage) providers. This module is kept so existing imports do not
break immediately; all functions now delegate to micro_config.
"""
from dataclasses import dataclass
import os
from typing import Optional

try:  # pragma: no cover
    from micro_config import get_provider as micro_get_provider, resolve_env as micro_resolve_env
    from micro_data_providers import MarketDataProvider as DataProvider  # type: ignore
except Exception:  # pragma: no cover
    from data_providers import SyntheticDataProvider as DataProvider  # type: ignore
from .settings import settings

VALID_ENVS = {"dev_stage", "production"}
# In dev_stage we default to synthetic data (deterministic, offline).
DEFAULT_ENV = "production"


@dataclass(slots=True)
class AppConfig:
    env: str


def _validate(env: str) -> str:
    if env not in VALID_ENVS:
        raise ValueError(f"Unknown APP_ENV '{env}'. Allowed: {sorted(VALID_ENVS)}")
    return env


def resolve_environment(override: Optional[str] = None) -> str:
    """Return effective environment.

    Precedence: explicit override arg > APP_ENV env var > settings.environment > DEFAULT_ENV.
    """
    if override:
        return _validate(override)
    env = os.getenv("APP_ENV") or getattr(settings, "environment", DEFAULT_ENV) or DEFAULT_ENV
    if env == "development":  # legacy mapping
        env = DEFAULT_ENV
    return _validate(env)


def get_provider(override: Optional[str] = None, cli_env: Optional[str] = None):  # type: ignore[override]
    eff = override or cli_env
    try:
        return micro_get_provider(eff)  # type: ignore[misc]
    except Exception:  # pragma: no cover
        from data_providers import SyntheticDataProvider  # type: ignore
        return SyntheticDataProvider(seed=123)


def bootstrap_defaults(provider: DataProvider, tickers: list[str], start, end) -> None:  # type: ignore[override]
    for t in tickers:
        try:  # pragma: no cover - best effort warm path
            provider.get_history(t, start, end)
        except Exception:
            pass


__all__ = [
    "AppConfig",
    "resolve_environment",
    "get_provider",
    "bootstrap_defaults",
]


def is_dev_stage(env: str | None = None) -> bool:
    if env is None:
        try:
            return micro_resolve_env(None) == "dev_stage"  # type: ignore[misc]
        except Exception:
            env = resolve_environment()
    return env == "dev_stage"

__all__.append("is_dev_stage")
