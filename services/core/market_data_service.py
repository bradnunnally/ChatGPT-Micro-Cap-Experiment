from __future__ import annotations

import json
import os
import random
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import yfinance as yf

from config.settings import settings
from core.errors import (
    MarketDataDownloadError,
    NoMarketDataError,
    ValidationError,
)
from infra.logging import get_logger
from services.core.validation import validate_ticker


@dataclass
class CircuitState:
    failures: int = 0
    opened_at: float = 0.0


class MarketDataService:
    """Resilient price lookup service with cache, retries, rate limit, and circuit breaker.

    Contract:
    - get_price(ticker: str) -> Optional[float]
      * Raises ValidationError on invalid ticker
      * Returns cached price when available (within TTL)
      * Applies rate limit and jittered backoff on retries
      * Uses a per-ticker circuit breaker to avoid repeated failing calls
    """

    def __init__(
        self,
        ttl_seconds: int | None = None,
        min_interval: float = 0.25,
        max_retries: int = 3,
        backoff_base: float = 0.3,
        circuit_fail_threshold: int = 3,
        circuit_cooldown: float = 60.0,
    ) -> None:
        self._logger = get_logger(__name__)
        self._ttl = ttl_seconds if ttl_seconds is not None else int(settings.cache_ttl_seconds)
        self._min_interval = float(min_interval)
        self._max_retries = int(max_retries)
        self._backoff_base = float(backoff_base)
        self._fail_threshold = int(circuit_fail_threshold)
        self._cooldown = float(circuit_cooldown)

        self._cache: dict[str, tuple[float, float]] = {}
        self._circuit: dict[str, CircuitState] = {}
        self._last_call_ts: float = 0.0

        # Optional on-disk cache per day
        self._disk_cache_dir = Path(settings.paths.data_dir) / "price_cache"
        self._disk_cache_dir.mkdir(parents=True, exist_ok=True)
        self._disk_cache_day = datetime.utcnow().strftime("%Y-%m-%d")
        self._disk_cache_path = self._disk_cache_dir / f"{self._disk_cache_day}.json"
        self._daily_disk_cache: dict[str, float] = self._load_disk_cache(self._disk_cache_path)

    def _load_disk_cache(self, path: Path) -> dict[str, float]:
        try:
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return {str(k): float(v) for k, v in data.items()}
        except Exception:
            pass
        return {}

    def _save_disk_cache(self) -> None:
        try:
            tmp = self._disk_cache_path.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._daily_disk_cache, f, separators=(",", ":"))
            os.replace(tmp, self._disk_cache_path)
        except Exception:
            pass

    def _now(self) -> float:
        return time.time()

    def _rate_limit(self) -> None:
        now = self._now()
        elapsed = now - self._last_call_ts
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_call_ts = self._now()

    def _circuit_open(self, ticker: str) -> bool:
        state = self._circuit.get(ticker)
        if not state:
            return False
        if state.failures < self._fail_threshold:
            return False
        # Open if within cooldown
        if (self._now() - state.opened_at) < self._cooldown:
            return True
        # Cooldown elapsed -> half-open; reset failures and allow a try
        self._circuit[ticker] = CircuitState(failures=0, opened_at=0.0)
        return False

    def _record_failure(self, ticker: str) -> None:
        state = self._circuit.get(ticker) or CircuitState()
        state.failures += 1
        if state.failures >= self._fail_threshold:
            state.opened_at = self._now()
            self._logger.error(
                "circuit open",
                extra={"event": "market_circuit_open", "ticker": ticker, "failures": state.failures},
            )
        self._circuit[ticker] = state

    def _record_success(self, ticker: str, price: float) -> None:
        # Reset breaker on success
        self._circuit[ticker] = CircuitState()
        # Update disk cache daily map
        self._daily_disk_cache[ticker] = float(price)
        self._save_disk_cache()

    def get_price(self, ticker: str) -> Optional[float]:
        # Validate ticker first
        validate_ticker(ticker)
        symbol = ticker.strip().upper()

        # Check in-memory cache
        now = self._now()
        cached = self._cache.get(symbol)
        if cached and (now - cached[1]) < self._ttl:
            return cached[0]

        # Refresh on-disk cache day rollover
        day_now = datetime.utcnow().strftime("%Y-%m-%d")
        if day_now != self._disk_cache_day:
            self._disk_cache_day = day_now
            self._disk_cache_path = self._disk_cache_dir / f"{self._disk_cache_day}.json"
            self._daily_disk_cache = self._load_disk_cache(self._disk_cache_path)

        # Check daily disk cache (acts as a gentle fallback)
        if symbol in self._daily_disk_cache:
            price = float(self._daily_disk_cache[symbol])
            self._cache[symbol] = (price, now)
            return price

        # Circuit breaker
        if self._circuit_open(symbol):
            self._logger.error(
                "circuit blocked",
                extra={"event": "market_circuit_block", "ticker": symbol},
            )
            return None

        # Rate limit before network
        self._rate_limit()

        # Retry with jittered exponential backoff
        attempt = 0
        last_exc: Exception | None = None
        while attempt < self._max_retries:
            try:
                data = yf.download(symbol, period="1d", progress=False, auto_adjust=True)
                if data is None or data.empty or "Close" not in data.columns:
                    # Try Ticker().history() as a fallback
                    t = yf.Ticker(symbol)
                    hist = t.history(period="5d")
                    if hist is None or hist.empty or "Close" not in hist.columns:
                        raise NoMarketDataError("No market data available.")
                    close = hist["Close"].dropna()
                    if close.empty:
                        raise NoMarketDataError("No market data available.")
                    price = float(close.iloc[-1])
                else:
                    # Respect DatetimeIndex behavior like services.market
                    if isinstance(data.index, pd.DatetimeIndex):
                        price = float(data["Close"].iloc[-1])
                    else:
                        price = float(data["Close"].iloc[0])

                # Cache and return
                self._cache[symbol] = (price, self._now())
                self._record_success(symbol, price)
                return price

            except NoMarketDataError as e:
                last_exc = e
                self._record_failure(symbol)
                # No point retrying if market data not available
                break
            except Exception as e:
                last_exc = e
                self._record_failure(symbol)
                # Backoff with jitter
                delay = self._backoff_base * (2 ** attempt)
                delay *= 1 + random.uniform(-0.2, 0.2)
                time.sleep(max(0.0, delay))
                attempt += 1

        # If we get here, all retries failed
        if isinstance(last_exc, NoMarketDataError):
            return None
        if last_exc is not None:
            raise MarketDataDownloadError(str(last_exc))
        return None
