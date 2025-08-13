from __future__ import annotations

"""Pluggable market data history providers (post‑migration).

Current implementations:
 - SyntheticDataProvider: deterministic OHLCV generation for dev_stage / tests.

Legacy yfinance provider removed after Finnhub migration. Tests and codepaths
should rely on micro_config + micro_data_providers for real data.
"""

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Protocol

import pandas as pd
import numpy as np


class DataProvider(Protocol):
    """Strategy interface for obtaining historical OHLCV data.

    Implementations must return a DataFrame with at least columns:
    ['date','open','high','low','close','volume'] sorted by date ascending.
    """

    def get_history(  # pragma: no cover - interface
        self, ticker: str, start: date, end: date, *, force_refresh: bool = False
    ) -> pd.DataFrame: ...


@dataclass(slots=True)
class SyntheticDataProvider:
    """Deterministic synthetic OHLCV generator for offline development."""

    seed: int = 42
    calendar: str = "B"  # pandas frequency for business days

    def _rng(self, ticker: str) -> np.random.Generator:
        # Derive a stable per‑ticker seed (bounded to uint32 range)
        derived = abs(hash((self.seed, ticker))) % (2**32 - 1)
        return np.random.default_rng(derived)

    def get_history(self, ticker: str, start: date, end: date, *, force_refresh: bool = False) -> pd.DataFrame:  # noqa: D401
        dates = pd.bdate_range(start=start, end=end, freq=self.calendar)
        if len(dates) == 0:
            return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])  # pragma: no cover

        rng = self._rng(ticker)
        n = len(dates)
        drift = 0.0005  # small positive drift
        vol = 0.02      # daily volatility 2%
        rets = rng.normal(drift, vol, size=n)
        start_price = rng.uniform(40, 180)  # plausible starting price
        close_prices = start_price * (1 + rets).cumprod()

        open_prices = np.empty_like(close_prices)
        open_prices[0] = close_prices[0] * (1 + rng.normal(0, 0.002))
        open_prices[1:] = close_prices[:-1] * (1 + rng.normal(0, 0.002, size=n - 1))

        daily_spread = np.abs(rng.normal(0.01, 0.004, size=n))
        highs = np.maximum(open_prices, close_prices) * (1 + daily_spread)
        lows = np.minimum(open_prices, close_prices) * (1 - daily_spread)
        volumes = rng.integers(50_000, 500_000, size=n)

        df = pd.DataFrame(
            {
                "date": dates,
                "open": open_prices,
                "high": highs,
                "low": lows,
                "close": close_prices,
                "volume": volumes,
                "ticker": ticker,
            }
        )
        return df


__all__ = ["DataProvider", "SyntheticDataProvider"]
