from __future__ import annotations

"""Environment selection & provider factory.

Reads APP_ENV from environment (optionally .env via python-dotenv) and creates the
appropriate DataProvider strategy.
"""

import os
from dataclasses import dataclass
from typing import Optional
from datetime import date

from dotenv import load_dotenv

from data_providers import SyntheticDataProvider, YFinanceDataProvider, DataProvider

VALID_ENVS = {"dev_stage", "production"}
DEFAULT_ENV = "production"


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


def get_provider(cli_env: Optional[str] = None) -> DataProvider:
    env = resolve_environment(cli_env)
    if env == "dev_stage":
        return SyntheticDataProvider(seed=123)
    return YFinanceDataProvider()


def bootstrap_defaults(provider: DataProvider, tickers: list[str], start: date, end: date) -> None:
    for t in tickers:
        try:
            provider.get_history(t, start, end)
        except Exception:
            pass


__all__ = ["get_provider", "resolve_environment", "bootstrap_defaults", "AppConfig"]
