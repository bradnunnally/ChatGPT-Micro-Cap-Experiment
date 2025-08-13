from __future__ import annotations

"""Config for micro CLI app: provider selection and env handling.

APP_ENV: dev_stage | production (default production when missing)
FINNHUB_API_KEY required in production
CACHE_DIR optional (default data/cache)
"""

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

from micro_data_providers import (
    MarketDataProvider,
    SyntheticDataProviderExt,
    FinnhubDataProvider,
)


VALID_ENVS = {"dev_stage", "production"}
DEFAULT_ENV = "production"


@dataclass(slots=True)
class AppSettings:
    env: str
    api_key: str | None
    cache_dir: str


def resolve_env(cli_env: Optional[str] = None) -> str:
    # Intentionally does NOT call load_dotenv so tests can control environment
    env = (cli_env or os.getenv("APP_ENV") or DEFAULT_ENV).strip()
    if env not in VALID_ENVS:
        raise ValueError(f"Unknown APP_ENV '{env}'. Allowed: {sorted(VALID_ENVS)}")
    return env


def get_settings(cli_env: Optional[str] = None) -> AppSettings:
    # Load dotenv lazily except during pytest (so tests can monkeypatch/delenv reliably)
    if "PYTEST_CURRENT_TEST" not in os.environ:
        load_dotenv(override=False)
    env = resolve_env(cli_env)
    api_key = os.getenv("FINNHUB_API_KEY")
    cache_dir = os.getenv("CACHE_DIR", "data/cache")
    return AppSettings(env=env, api_key=api_key, cache_dir=cache_dir)


def get_provider(cli_env: Optional[str] = None) -> MarketDataProvider:
    s = get_settings(cli_env)
    if s.env == "dev_stage":
        return SyntheticDataProviderExt(seed=42)
    # production path
    if not s.api_key:
        raise RuntimeError("FINNHUB_API_KEY is required in production mode")
    return FinnhubDataProvider(api_key=s.api_key, cache_dir=s.cache_dir)


def print_mode(provider: MarketDataProvider) -> None:
    env = os.getenv("APP_ENV", DEFAULT_ENV)
    print(f"Mode: {env} | Provider: {provider.__class__.__name__}")


__all__ = [
    "AppSettings",
    "resolve_env",
    "get_settings",
    "get_provider",
    "print_mode",
]
