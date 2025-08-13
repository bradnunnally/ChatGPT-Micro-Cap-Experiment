from __future__ import annotations

"""Pluggable market data history providers.

Two implementations:
 - SyntheticDataProvider: deterministic OHLCV generation for dev_stage
 - YFinanceDataProvider: real data via yfinance with per‑ticker on-disk cache

The interface intentionally stays minimal for easy testability.
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


@dataclass(slots=True)
class YFinanceDataProvider:
    """Real data provider backed by yfinance with per‑ticker parquet cache."""

    cache_dir: str | Path = Path("data/cache")

    def __post_init__(self):
        self.cache_dir = Path(self.cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_file(self, ticker: str) -> Path:
        return self.cache_dir / f"{ticker.upper()}_history.parquet"

    def get_history(self, ticker: str, start: date, end: date, *, force_refresh: bool = False) -> pd.DataFrame:  # noqa: D401
        # Lazy import to avoid network dependencies at module import time
        import yfinance as yf  # type: ignore

        cache_file = self._cache_file(ticker)
        if cache_file.exists() and not force_refresh:
            try:
                cached = pd.read_parquet(cache_file)
                if (
                    not cached.empty
                    and cached["date"].min() <= pd.Timestamp(start)
                    and cached["date"].max() >= pd.Timestamp(end)
                ):
                    return cached[(cached["date"] >= pd.Timestamp(start)) & (cached["date"] <= pd.Timestamp(end))].reset_index(drop=True)
            except Exception:  # pragma: no cover - corrupted cache
                pass

        dl_start = start
        if cache_file.exists() and not force_refresh:
            try:
                cached = pd.read_parquet(cache_file)
                if not cached.empty:
                    dl_start = min(start, cached["date"].min().date())
            except Exception:
                pass

        df = yf.download(
            ticker,
            start=dl_start,
            end=end + pd.Timedelta(days=1),
            auto_adjust=True,
            progress=False,
        )
        if df.empty:
            return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])  # pragma: no cover

        df = df.reset_index().rename(
            columns={
                df.columns[0]: "date",
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Adj Close": "close",
                "Volume": "volume",
            }
        )
        # Defensive: ensure we have a 'date' column (some edge mocks may keep original name)
        if "date" not in df.columns:
            for candidate in ("Date", "datetime", "index"):
                if candidate in df.columns:
                    df = df.rename(columns={candidate: "date"})
                    break
        # Normalize dtype
        if "date" in df.columns:
            try:
                df["date"] = pd.to_datetime(df["date"])
            except Exception:  # pragma: no cover
                pass
        if "Volume" in df.columns and "volume" not in df.columns:
            df = df.rename(columns={"Volume": "volume"})
        df["ticker"] = ticker.upper()
        df = df.sort_values("date")

        try:
            if cache_file.exists() and not force_refresh:
                try:
                    existing = pd.read_parquet(cache_file)
                    combined = (
                        pd.concat([existing, df], ignore_index=True)
                        .drop_duplicates(subset=["date"], keep="last")
                        .sort_values("date")
                    )
                    combined.to_parquet(cache_file, index=False)
                    full = combined
                except Exception:
                    df.to_parquet(cache_file, index=False)
                    full = df
            else:
                df.to_parquet(cache_file, index=False)
                full = df
        except Exception:  # pragma: no cover - cache write failure
            full = df

        return full[(full["date"] >= pd.Timestamp(start)) & (full["date"] <= pd.Timestamp(end))].reset_index(drop=True)


__all__ = ["DataProvider", "SyntheticDataProvider", "YFinanceDataProvider"]
