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
    # Fall back to a minimal, local SyntheticDataProvider implementation so the
    # package remains importable when legacy `data_providers.py` has been archived.
    # This is intentionally small and deterministic for tests.
    from dataclasses import dataclass
    import pandas as _pd
    import numpy as _np
    from datetime import date as _date

    @dataclass(slots=True)
    class SyntheticDataProvider:
        seed: int = 123

        def _rng(self, ticker: str) -> _np.random.Generator:
            derived = abs(hash((self.seed, ticker))) % (2**32 - 1)
            return _np.random.default_rng(derived)

        def get_history(self, ticker: str, start: _date, end: _date, *, force_refresh: bool = False):
            # Produce a deterministic small DataFrame suitable for tests.
            dates = _pd.bdate_range(start=start, end=end)
            if len(dates) == 0:
                return _pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume", "ticker"])
            rng = self._rng(ticker)
            n = len(dates)
            drift = 0.0005
            vol = 0.02
            rets = rng.normal(drift, vol, size=n)
            start_price = rng.uniform(40, 180)
            close_prices = start_price * (1 + rets).cumprod()
            open_prices = _np.empty_like(close_prices)
            open_prices[0] = close_prices[0]
            open_prices[1:] = close_prices[:-1]
            highs = _np.maximum(open_prices, close_prices) * (1 + 0.01)
            lows = _np.minimum(open_prices, close_prices) * (1 - 0.01)
            volumes = rng.integers(50_000, 500_000, size=n)
            df = _pd.DataFrame({
                "date": dates,
                "open": open_prices,
                "high": highs,
                "low": lows,
                "close": close_prices,
                "volume": volumes,
                "ticker": ticker,
            })
            return df

    def micro_get_provider(eff: Optional[str] = None):
        return SyntheticDataProvider(seed=123)

    def micro_resolve_env(override: Optional[str] = None) -> str:
        return DEFAULT_ENV
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
        # If micro_get_provider raises (e.g. missing FINNHUB_API_KEY), return
        # a local SyntheticDataProvider rather than attempting to import the
        # legacy `data_providers` module which may have been archived.
        from dataclasses import dataclass
        import pandas as _pd
        import numpy as _np
        from datetime import date as _date

        @dataclass(slots=True)
        class SyntheticDataProvider:
            seed: int = 123

            def _rng(self, ticker: str) -> _np.random.Generator:
                derived = abs(hash((self.seed, ticker))) % (2**32 - 1)
                return _np.random.default_rng(derived)

            def get_history(self, ticker: str, start: _date, end: _date, *, force_refresh: bool = False):
                dates = _pd.bdate_range(start=start, end=end)
                if len(dates) == 0:
                    return _pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume", "ticker"])
                rng = self._rng(ticker)
                n = len(dates)
                drift = 0.0005
                vol = 0.02
                rets = rng.normal(drift, vol, size=n)
                start_price = rng.uniform(40, 180)
                close_prices = start_price * (1 + rets).cumprod()
                open_prices = _np.empty_like(close_prices)
                open_prices[0] = close_prices[0]
                open_prices[1:] = close_prices[:-1]
                highs = _np.maximum(open_prices, close_prices) * (1 + 0.01)
                lows = _np.minimum(open_prices, close_prices) * (1 - 0.01)
                volumes = rng.integers(50_000, 500_000, size=n)
                df = _pd.DataFrame({
                    "date": dates,
                    "open": open_prices,
                    "high": highs,
                    "low": lows,
                    "close": close_prices,
                    "volume": volumes,
                    "ticker": ticker,
                })
                return df

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
