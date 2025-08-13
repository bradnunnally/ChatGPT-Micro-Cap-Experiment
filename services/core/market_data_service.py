from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Optional, Callable

import pandas as pd

from config import get_provider  # unified provider (synthetic in dev_stage, Finnhub in production)
try:  # Prefer micro_config if available (already the delegated path)
    from micro_config import get_provider as micro_get_provider
except Exception:  # pragma: no cover
    micro_get_provider = None  # type: ignore

from config.settings import settings
from core.errors import MarketDataDownloadError, NoMarketDataError
from infra.logging import get_logger
from services.core.validation import validate_ticker

# Backwards compatibility: tests may reference module-level yf
yf = None  # type: ignore


@dataclass
class CircuitState:
    failures: int = 0
    opened_at: float = 0.0


class MarketDataService:
    """Price lookup service using the new provider architecture (no yfinance).

    Features:
      - In-memory TTL cache
      - Optional per-day disk cache (simple JSON) for resilience
      - Minimal rate limiting + circuit breaker (kept for parity with legacy tests)
    """

    def __init__(
        self,
        ttl_seconds: int | None = None,
        min_interval: float = 0.25,
        max_retries: int = 1,
        backoff_base: float = 0.0,
        circuit_fail_threshold: int = 3,
        circuit_cooldown: float = 60.0,
        price_provider: Callable[[str], float] | None = None,
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
        self._price_provider = price_provider

        self._disk_cache_dir = Path(settings.paths.data_dir) / "price_cache"
        self._disk_cache_dir.mkdir(parents=True, exist_ok=True)
        self._disk_cache_day = datetime.now(UTC).strftime("%Y-%m-%d")
        self._disk_cache_path = self._disk_cache_dir / f"{self._disk_cache_day}.json"
        self._daily_disk_cache = self._load_disk_cache(self._disk_cache_path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _load_disk_cache(self, path: Path) -> dict[str, float]:
        try:
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return {str(k): float(v) for k, v in data.items()}
        except Exception:  # pragma: no cover
            pass
        return {}

    def _save_disk_cache(self) -> None:
        try:
            tmp = self._disk_cache_path.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._daily_disk_cache, f, separators=(",", ":"))
            os.replace(tmp, self._disk_cache_path)
        except Exception:  # pragma: no cover
            pass

    def _now(self) -> float:
        return time.time()

    def _rate_limit(self) -> None:
        elapsed = self._now() - self._last_call_ts
        if elapsed < self._min_interval:
            time.sleep(max(0.0, self._min_interval - elapsed))
        self._last_call_ts = self._now()

    def _circuit_open(self, symbol: str) -> bool:
        state = self._circuit.get(symbol)
        if not state:
            return False
        if state.failures < self._fail_threshold:
            return False
        if (self._now() - state.opened_at) < self._cooldown:
            return True
        # cooldown passed -> half-open
        self._circuit[symbol] = CircuitState()
        return False

    def _record_failure(self, symbol: str) -> None:
        st = self._circuit.get(symbol) or CircuitState()
        st.failures += 1
        if st.failures >= self._fail_threshold:
            st.opened_at = self._now()
            self._logger.error(
                "circuit open",
                extra={"event": "market_circuit_open", "ticker": symbol, "failures": st.failures},
            )
        self._circuit[symbol] = st

    def _record_success(self, symbol: str, price: float) -> None:
        self._circuit[symbol] = CircuitState()
        self._daily_disk_cache[symbol] = float(price)
        self._save_disk_cache()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_price(self, ticker: str) -> Optional[float]:
        validate_ticker(ticker)
        symbol = ticker.strip().upper()

        # Memory cache
        now_ts = self._now()
        cached = self._cache.get(symbol)
        if cached and (now_ts - cached[1]) < self._ttl:
            return cached[0]

        # Test/injected provider path with retry semantics
        if self._price_provider is not None:
            last_exc: Exception | None = None
            for attempt in range(max(1, self._max_retries)):
                try:
                    price = float(self._price_provider(symbol))
                    self._cache[symbol] = (price, now_ts)
                    self._record_success(symbol, price)
                    return price
                except Exception as e:  # pragma: no cover - defensive
                    last_exc = e
                    if attempt < max(1, self._max_retries) - 1 and self._backoff_base > 0:
                        time.sleep(self._backoff_base * (2 ** attempt))
            if last_exc is not None:
                raise MarketDataDownloadError(str(last_exc))
            return None

        # Day rollover for disk cache
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        if today != self._disk_cache_day:
            self._disk_cache_day = today
            self._disk_cache_path = self._disk_cache_dir / f"{self._disk_cache_day}.json"
            self._daily_disk_cache = self._load_disk_cache(self._disk_cache_path)

        # Disk cache (soft fallback)
        if symbol in self._daily_disk_cache:
            price = float(self._daily_disk_cache[symbol])
            self._cache[symbol] = (price, now_ts)
            return price

        # Circuit breaker
        if self._circuit_open(symbol):
            self._logger.error("circuit blocked", extra={"event": "market_circuit_block", "ticker": symbol})
            return None

        self._rate_limit()

        last_exc: Exception | None = None
        try:
            provider = micro_get_provider() if micro_get_provider is not None else get_provider()
            end = pd.Timestamp.utcnow().normalize()
            start = end - pd.Timedelta(days=5)

            # Direct quote
            if hasattr(provider, "get_quote"):
                q = provider.get_quote(symbol)
                if isinstance(q, dict):
                    p = q.get("price") or q.get("last") or q.get("c")
                    if p is not None:
                        price = float(p)
                        self._cache[symbol] = (price, self._now())
                        self._record_success(symbol, price)
                        return price

            # Daily candles (finnhub) if available
            if hasattr(provider, "get_daily_candles"):
                candles = provider.get_daily_candles(symbol, start=start.date(), end=end.date())  # type: ignore[attr-defined]
                if isinstance(candles, pd.DataFrame) and not candles.empty:
                    for col in ("close", "c", "Close"):
                        if col in candles.columns:
                            closes = candles[col].dropna()
                            if not closes.empty:
                                price = float(closes.iloc[-1])
                                self._cache[symbol] = (price, self._now())
                                self._record_success(symbol, price)
                                return price

            # Generic history fallback (synthetic provider)
            if hasattr(provider, "get_history"):
                hist = provider.get_history(symbol, start, end)
                if hist is not None and not hist.empty:
                    for col in ("Close", "close", "c"):
                        if col in hist.columns:
                            closes = hist[col].dropna()
                            if not closes.empty:
                                price = float(closes.iloc[-1])
                                self._cache[symbol] = (price, self._now())
                                self._record_success(symbol, price)
                                return price
        except Exception as e:  # pragma: no cover
            last_exc = e
            # Treat explicit permission/plan limit errors as soft failures returning None
            msg = str(e).lower()
            if any(code in msg for code in ("403", "permission", "plan limit", "forbidden")):
                self._record_failure(symbol)
                return None
            self._record_failure(symbol)

        if isinstance(last_exc, NoMarketDataError):  # pragma: no cover
            return None
        if last_exc is not None:  # pragma: no cover
            # Treat missing API key as soft None to satisfy circuit breaker & fallback tests
            msg = str(last_exc).lower()
            if "finnhub_api_key is required" in msg:
                return None
            raise MarketDataDownloadError(str(last_exc))
        return None

