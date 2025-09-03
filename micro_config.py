from __future__ import annotations

"""Config for micro CLI app: provider selection and env handling.

APP_ENV: dev_stage | production (default production when missing)
FINNHUB_API_KEY required in production
CACHE_DIR optional (default data/cache)
"""

import os
from dataclasses import dataclass
from typing import Optional, Any
import pandas as pd

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
    # Build a chained provider: Finnhub -> yfinance -> stooq
    finnhub = FinnhubDataProvider(api_key=s.api_key, cache_dir=s.cache_dir)

    class YFinanceProvider:
        """Lightweight yfinance fallback with lazy import."""

        def __init__(self):
            self._yf = None

        def _ensure(self):
            if self._yf is None:
                import yfinance as yf  # type: ignore
                self._yf = yf

        def get_daily_candles(self, ticker, start, end):
            self._ensure()
            tk = self._yf.Ticker(ticker)
            df = tk.history(start=start, end=end)
            if df is None or df.empty:
                return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
            df = df.reset_index()
            df = df.rename(columns={"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume", "Date": "date"})
            if "Date" in df.columns:
                df["date"] = pd.to_datetime(df["Date"])  # pragma: no cover
            return df[["date", "open", "high", "low", "close", "volume"]]

        def get_quote(self, ticker):
            self._ensure()
            tk = self._yf.Ticker(ticker)
            info = tk.info if hasattr(tk, "info") else {}
            price = info.get("regularMarketPrice") or info.get("previousClose")
            prev = info.get("previousClose")
            change = (price - prev) if (price is not None and prev is not None) else None
            percent = (change / prev * 100.0) if (change is not None and prev) else None
            return {"price": price, "change": change, "percent": percent}

        def get_company_profile(self, ticker):
            self._ensure()
            tk = self._yf.Ticker(ticker)
            info = tk.info if hasattr(tk, "info") else {}
            return {"ticker": ticker.upper(), "exchange": info.get("exchange"), "sector": info.get("sector"), "marketCap": info.get("marketCap")}

        def get_bid_ask(self, ticker):
            q = self.get_quote(ticker)
            price = q.get("price")
            if not price:
                return (None, None)
            spread = 0.01 * price
            return (round(price - spread, 4), round(price + spread, 4))

        def get_company_news(self, ticker, start, end):
            return []

        def get_earnings_calendar(self, ticker, start, end):
            return []

    class StooqProvider:
        """Lightweight pandas-datareader stooq fallback with lazy import."""

        def __init__(self):
            self._pdr = None

        def _ensure(self):
            if self._pdr is None:
                from pandas_datareader import data as pdr  # type: ignore
                self._pdr = pdr

        def get_daily_candles(self, ticker, start, end):
            self._ensure()
            try:
                df = self._pdr.DataReader(ticker, "stooq", start, end)
            except Exception:
                return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
            df = df.reset_index()
            df = df.rename(columns={"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume", "Date": "date"})
            df["date"] = pd.to_datetime(df["Date"]).dt.tz_localize("UTC") if "Date" in df.columns else pd.to_datetime(df["date"])  # pragma: no cover
            return df[["date", "open", "high", "low", "close", "volume"]]

        def get_quote(self, ticker):
            df = self.get_daily_candles(ticker, pd.Timestamp.utcnow().date() - pd.Timedelta(days=5), pd.Timestamp.utcnow().date())
            if df.empty:
                return {"price": None, "change": None, "percent": None}
            last = float(df["close"].iloc[-1])
            prev = float(df["close"].iloc[-2]) if len(df) > 1 else last
            change = last - prev
            percent = (change / prev * 100.0) if prev else 0.0
            return {"price": last, "change": change, "percent": percent}

        def get_company_profile(self, ticker):
            return {"ticker": ticker.upper(), "exchange": None, "sector": None, "marketCap": None}

        def get_bid_ask(self, ticker):
            q = self.get_quote(ticker)
            price = q.get("price")
            if not price:
                return (None, None)
            spread = 0.01 * price
            return (round(price - spread, 4), round(price + spread, 4))

        def get_company_news(self, ticker, start, end):
            return []

        def get_earnings_calendar(self, ticker, start, end):
            return []

    class ChainedProvider:
        """Try a sequence of providers until one succeeds for each method.

        Each method calls providers in order and returns the first successful
        non-empty result. Exceptions are caught and logged by callers.
        """

        def __init__(self, providers):
            self.providers = providers

        def _call(self, method_name, *args, **kwargs):
            last_exc = None
            for p in self.providers:
                try:
                    meth = getattr(p, method_name)
                    res = meth(*args, **kwargs)
                    # Treat empty DataFrame or None as failure for data methods
                    if isinstance(res, pd.DataFrame) and res.empty:
                        last_exc = None
                        continue
                    if res is None:
                        continue
                    return res
                except Exception as e:
                    last_exc = e
                    continue
            if last_exc:
                raise last_exc
            return None

        def get_daily_candles(self, ticker, start, end):
            res = self._call("get_daily_candles", ticker, start, end)
            if isinstance(res, pd.DataFrame):
                return res
            return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])

        def get_quote(self, ticker):
            return self._call("get_quote", ticker) or {"price": None, "change": None, "percent": None}

        def get_company_profile(self, ticker):
            return self._call("get_company_profile", ticker) or {"ticker": ticker.upper()}

        def get_bid_ask(self, ticker):
            return self._call("get_bid_ask", ticker) or (None, None)

        def get_company_news(self, ticker, start, end):
            return self._call("get_company_news", ticker, start, end) or []

        def get_earnings_calendar(self, ticker, start, end):
            return self._call("get_earnings_calendar", ticker, start, end) or []

    # Instantiate fallbacks lazily
    yfin = YFinanceProvider()
    stooq = StooqProvider()
    chained = ChainedProvider([finnhub, yfin, stooq])
    return chained


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
