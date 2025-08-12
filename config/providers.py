from __future__ import annotations
"""Data provider environment resolution and factory.

Centralizes logic for choosing between synthetic (offline) and yfinance-backed
data providers. Only this module should know how APP_ENV maps to a provider.
"""
from dataclasses import dataclass
import os
from typing import Optional

from data_providers import SyntheticDataProvider, YFinanceDataProvider
from data_providers import DataProvider  # type: ignore
from .settings import settings

VALID_ENVS = {"dev_stage", "production"}
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


def get_provider(override: Optional[str] = None, cli_env: Optional[str] = None) -> DataProvider:  # type: ignore[override]
    # Support legacy parameter name cli_env for tests/backward compatibility.
    eff = override or cli_env
    env = resolve_environment(eff)
    if env == "dev_stage":
        return SyntheticDataProvider(seed=123)
    return YFinanceDataProvider()


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
    """Return True if effective environment is dev_stage.

    Accepts optional env override to avoid recomputing.
    """
    if env is None:
        env = resolve_environment()
    return env == "dev_stage"

__all__.append("is_dev_stage")
