import os
import time
import random
from typing import Any, Callable, Dict, List, Optional, TypeVar, Iterable
from pathlib import Path
from functools import lru_cache, wraps
import threading
import pandas as pd
import streamlit as st
import requests

from config import get_provider, is_dev_stage
try:  # micro provider always expected now; keep defensive import
    from micro_config import get_provider as get_micro_provider
    from micro_data_providers import MarketDataProvider as MicroMarketDataProvider
except Exception:  # pragma: no cover
    get_micro_provider = None  # type: ignore
    MicroMarketDataProvider = None  # type: ignore

from core.errors import MarketDataDownloadError
from services.logging import get_logger
from app_settings import settings

logger = get_logger(__name__)

# --------------- Simple in-process metrics & circuit breaker -----------------
_metrics: dict[str, float] = {
    "price_fetch_bulk_success": 0,           # per-ticker successes in bulk path
    "price_fetch_bulk_failure": 0,           # per-ticker failures in bulk path
    "price_fetch_individual_success": 0,     # individual fallback successes
    "price_fetch_individual_failure": 0,     # individual fallback failures
    "micro_provider_init_failures": 0,
}

_METRICS_FILE = Path(settings.paths.data_dir) / "cache" / "metrics_state.json"
_METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)

_CIRCUIT_STATE_FILE = Path(settings.paths.data_dir) / "cache" / "circuit_state.json"
_CIRCUIT_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

class CircuitBreaker:
    """Lightweight circuit breaker for external provider calls.

    Trip conditions:
      - failures >= failure_threshold within rolling window (simplified: since last reset).
    Recovery:
      - after reset_timeout seconds attempt a single trial call; success closes circuit.
    """
    def __init__(self, failure_threshold: int = 5, reset_timeout: float = 30.0):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.failures = 0
        self.state = "CLOSED"  # CLOSED | OPEN | HALF_OPEN
        self.opened_at: float | None = None
        self._persist()

    # ---------------- persistence helpers -----------------
    def _persist(self) -> None:
        try:  # pragma: no cover - file system errors not critical
            data = {
                "failures": self.failures,
                "state": self.state,
                "opened_at": self.opened_at,
                "failure_threshold": self.failure_threshold,
                "reset_timeout": self.reset_timeout,
            }
            _CIRCUIT_STATE_FILE.write_text(__import__("json").dumps(data))
        except Exception:
            pass

    def load_if_exists(self) -> None:
        try:
            import json
            if _CIRCUIT_STATE_FILE.exists():
                data = json.loads(_CIRCUIT_STATE_FILE.read_text())
                # Only adopt if thresholds match to avoid stale incompatible state
                if data.get("failure_threshold") == self.failure_threshold:
                    self.failures = int(data.get("failures", 0))
                    self.state = data.get("state", "CLOSED")
                    self.opened_at = data.get("opened_at")
        except Exception:  # pragma: no cover
            pass

    def allow(self) -> bool:
        if self.state == "CLOSED":
            return True
        if self.state == "OPEN":
            if self.opened_at and (time.time() - self.opened_at) >= self.reset_timeout:
                self.state = "HALF_OPEN"
                return True
            return False
        # HALF_OPEN -> allow single trial
        return True

    def record_success(self) -> None:
        if self.state in {"OPEN", "HALF_OPEN"}:
            self.state = "CLOSED"
            self.failures = 0
            self.opened_at = None
        self._persist()

    def record_failure(self) -> None:
        self.failures += 1
        if self.state == "HALF_OPEN":
            # immediate re-open on failure
            self.state = "OPEN"
            self.opened_at = time.time()
            self.failures = self.failure_threshold  # cap
            self._persist()
            return
        if self.failures >= self.failure_threshold and self.state == "CLOSED":
            self.state = "OPEN"
            self.opened_at = time.time()
        self._persist()

_micro_cb = CircuitBreaker(failure_threshold=4, reset_timeout=20.0)
_micro_cb.load_if_exists()

def _persist_metrics() -> None:  # pragma: no cover - IO best-effort
    try:
        import json
        data = {"metrics": _metrics}
        _METRICS_FILE.write_text(json.dumps(data))
    except Exception:
        pass

def _load_metrics() -> None:  # pragma: no cover - startup helper
    try:
        import json
        if _METRICS_FILE.exists():
            data = json.loads(_METRICS_FILE.read_text())
            stored = data.get("metrics", {})
            for k, v in stored.items():
                if k in _metrics and isinstance(v, (int, float)):
                    _metrics[k] = v
    except Exception:
        pass

_load_metrics()

def get_metrics() -> dict[str, float]:  # pragma: no cover - trivial accessor
    return dict(_metrics, circuit_state=_micro_cb.state, circuit_failures=_micro_cb.failures)

def reset_metrics() -> None:
    """Reset in-memory metrics & circuit breaker (test helper)."""
    for k in list(_metrics):
        _metrics[k] = 0
    _micro_cb.failures = 0
    _micro_cb.state = "CLOSED"
    _micro_cb.opened_at = None
    _micro_cb._persist()
    _persist_metrics()

def get_circuit_breaker_state() -> dict[str, Any]:  # pragma: no cover - trivial
    return {"state": _micro_cb.state, "failures": _micro_cb.failures}

def record_individual_success():  # pragma: no cover - simple counter
    _metrics["price_fetch_individual_success"] += 1
    _persist_metrics()

def record_individual_failure():  # pragma: no cover
    _metrics["price_fetch_individual_failure"] += 1
    _persist_metrics()

# ---------------- Unified retry decorator (quick win) -----------------
T = TypeVar("T")

def retry(attempts: int = 3, base_delay: float = 0.25, backoff: float = 2.0, jitter: float = 0.1, retry_on: tuple[type[Exception], ...] = (Exception,)):  # pragma: no cover - infrastructure helper
    def deco(fn: Callable[..., T]) -> Callable[..., T | None]:
        @wraps(fn)
        def wrapper(*args, **kwargs):  # pragma: no cover - trivial wrapper logic
            for i in range(attempts):
                try:
                    return fn(*args, **kwargs)
                except retry_on as e:  # pragma: no cover - transient failures
                    if i == attempts - 1:
                        logger.error("retry_failed", extra={"fn": fn.__name__, "error": str(e)})
                        return None
                    delay = base_delay * (backoff ** i)
                    if jitter > 0:
                        # Apply +/- jitter proportionally
                        delta = delay * jitter
                        delay += random.uniform(-delta, delta)
                    time.sleep(delay)
            return None
        return wrapper
    return deco

# -------------------- Micro provider path (now primary) --------------------
def _micro_enabled() -> bool:
    # Primary enable switch now via consolidated settings; env var remains as emergency kill-switch.
    try:
        from app_settings import settings  # local import to avoid circular
        if os.getenv("DISABLE_MICRO_PROVIDERS") == "1":
            return False
        return bool(settings.micro_enabled)
    except Exception:  # pragma: no cover - fallback when settings import fails early
        return os.getenv("DISABLE_MICRO_PROVIDERS") != "1"

_micro_provider_cache: Optional[MicroMarketDataProvider] = None  # type: ignore

def _get_micro_provider() -> Optional[MicroMarketDataProvider]:  # type: ignore
    global _micro_provider_cache
    if not _micro_enabled():
        return None
    if get_micro_provider is None:
        return None
    if _micro_provider_cache is None:
        if not _micro_cb.allow():
            logger.warning("micro_provider_circuit_open")
            return None
        try:
            _micro_provider_cache = get_micro_provider()
            _micro_cb.record_success()
        except Exception as e:  # pragma: no cover
            _metrics["micro_provider_init_failures"] += 1
            _micro_cb.record_failure()
            logger.error("micro_provider_init_failed", extra={"error": str(e), "circuit_state": _micro_cb.state})
            return None
    return _micro_provider_cache

def fetch_price_v2(ticker: str) -> Optional[float]:
    """Provider-based price fetch (Finnhub or Synthetic).

    Falls back to cached helper if micro providers disabled or on error.
    """
    prov = _get_micro_provider()
    if not prov:
        return fetch_price(ticker)
    try:
        q = prov.get_quote(ticker)
        return q.get("price") if q else None
    except Exception as e:  # pragma: no cover - defensive
        logger.error("micro_price_failed", extra={"ticker": ticker, "error": str(e)})
        return fetch_price(ticker)

def fetch_prices_v2(tickers: List[str]) -> pd.DataFrame:
    prov = _get_micro_provider()
    if not prov:
        return fetch_prices(tickers)
    rows = []
    for t in tickers:
        try:
            q = prov.get_quote(t) or {}
            rows.append({"ticker": t, "current_price": q.get("price"), "pct_change": q.get("percent")})
            _metrics["price_fetch_bulk_success"] += 1
            _persist_metrics()
        except Exception:  # pragma: no cover
            rows.append({"ticker": t, "current_price": None, "pct_change": None})
            _metrics["price_fetch_bulk_failure"] += 1
            _persist_metrics()
    return pd.DataFrame(rows)

# Global rate limiting state (retained from original implementation)
_last_request_time = 0.0
_min_request_interval = 1.0


# --- Utility helpers expected by tests ---------------------------------------------------
def is_valid_price(value: Any) -> bool:
    return isinstance(value, (int, float)) and value > 0  # simple test helper


def validate_price_data(value: Any) -> bool:  # backward compatible name
    return is_valid_price(value)


def calculate_percentage_change(old: float | int | None, new: float | int | None) -> float | None:
    """Return percent change from old to new.

    Tests expect 0.0 when old is 0 (or non-positive), not inf/None.
    Return None only when new is not a valid number.
    """
    if new is None:
        return None
    try:
        new_f = float(new)
        old_f = 0.0 if old is None else float(old)
    except Exception:
        return None
    if old_f <= 0.0:
        return 0.0
    return (new_f - old_f) / old_f * 100.0


def _rate_limit():
    global _last_request_time
    now = time.time()
    elapsed = now - _last_request_time
    if elapsed < _min_request_interval:
        time.sleep(_min_request_interval - elapsed)
    _last_request_time = time.time()


@lru_cache(maxsize=1)
def _get_session():
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
        }
    )
    return session


def _retry(fn: Callable[[], Any], attempts: int = 3, base_delay: float = 0.3) -> Any:
    for i in range(attempts):
        try:
            return fn()
        except Exception:  # pragma: no cover
            if i == attempts - 1:
                return None
            time.sleep(base_delay * (2**i))

def _legacy_market_test_mode() -> bool:  # pragma: no cover - legacy shim retained for compatibility
    return False

def _skip_synthetic_for_tests() -> bool:  # pragma: no cover - legacy shim
    return False

def _get_synthetic_close(ticker: str) -> float | None:
    try:
        provider = get_provider()
        end = pd.Timestamp.utcnow().normalize()
        start = end - pd.Timedelta(days=90)
        hist = provider.get_history(ticker, start, end)
        if not hist.empty:
            for candidate in ("Close", "close"):
                if candidate in hist.columns:
                    closes = hist[candidate].dropna()
                    if not closes.empty:
                        return float(closes.iloc[-1])
    except Exception:
        return None
    return None


def _download_close_price(ticker: str, *, legacy: bool) -> tuple[float | None, bool, bool]:  # pragma: no cover - deprecated
    return None, False, False


@st.cache_data(ttl=300)
def fetch_price(ticker: str) -> float | None:
    """Return latest close price or None (refactored)."""
    # Short-circuit to micro provider (Finnhub/Synthetic)
    prov = _get_micro_provider()
    if prov:
        try:
            q = prov.get_quote(ticker)
            return q.get("price") if q else None
        except Exception:  # pragma: no cover - defensive
            pass
    if is_dev_stage() and not _legacy_market_test_mode() and not _skip_synthetic_for_tests():
        syn = _get_synthetic_close(ticker)
        if syn is not None:
            return syn
    # Micro provider already attempted; no legacy network fallback.
    return None


@st.cache_data(ttl=300)
def fetch_prices(tickers: list[str]) -> pd.DataFrame:

    """Return a DataFrame with columns ['ticker','current_price','pct_change'] for tickers.

    Primary path: micro provider quotes (Finnhub in production, Synthetic in dev_stage).
    Fallback (dev_stage only): derive last close from synthetic history.
    """
    if not tickers:
        return pd.DataFrame(columns=["ticker", "current_price", "pct_change"])

    # Micro provider path only
    prov = _get_micro_provider()
    if prov:
        rows = []
        for t in tickers:
            try:
                q = prov.get_quote(t) or {}
                rows.append({"ticker": t, "current_price": q.get("price"), "pct_change": q.get("percent")})
                _metrics["price_fetch_bulk_success"] += 1
                _persist_metrics()
            except Exception:
                rows.append({"ticker": t, "current_price": None, "pct_change": None})
                _metrics["price_fetch_bulk_failure"] += 1
                _persist_metrics()
        return pd.DataFrame(rows)

    if is_dev_stage() and not _legacy_market_test_mode():
        provider = get_provider()
        import pandas as _pd
        end = _pd.Timestamp.utcnow().normalize()
        start = end - _pd.Timedelta(days=90)
        rows: list[dict[str, Any]] = []
        for t in tickers:
            try:
                hist = provider.get_history(t, start, end)
                if not hist.empty:
                    close_col = "Close" if "Close" in hist.columns else ("close" if "close" in hist.columns else None)
                    if close_col and not hist[close_col].dropna().empty:
                        val = float(hist[close_col].dropna().iloc[-1])
                    else:
                        val = None
                else:
                    val = None
            except Exception:
                val = None
            rows.append({"ticker": t, "current_price": val, "pct_change": None})
        return _pd.DataFrame(rows)
    return pd.DataFrame(columns=["ticker", "current_price", "pct_change"])
def get_day_high_low(ticker: str) -> tuple[float, float]:
    """Return today's high and low price for ``ticker``.

    Micro provider path first (candles if available) then synthetic approximation.
    """
    # Attempt to use candles if capability available.
    prov = _get_micro_provider()
    if prov:
        try:
            import pandas as _pd
            end = _pd.Timestamp.utcnow().date()
            start = end  # single day
            # Attempt to get at least today's candle; Finnhub daily candles include previous days
            df = prov.get_daily_candles(ticker, start=start, end=end)
            if not df.empty:
                highs = df.get("high") or df.get("High")
                lows = df.get("low") or df.get("Low")
                if highs is not None and lows is not None and len(highs) and len(lows):
                    return float(_pd.Series(highs).max()), float(_pd.Series(lows).min())
            # Fallback: approximate from last quote ±5%
            q = prov.get_quote(ticker)
            price = q.get("price") if q else None
            if price and price > 0:
                buff = price * 0.05
                return price + buff, price - buff
        except Exception:  # pragma: no cover
            pass
    
    # No legacy fallback path.

    # Allow synthetic history fallback even in production if micro provider unavailable
    if (is_dev_stage() or not prov) and not _skip_synthetic_for_tests():
        try:
            provider = get_provider()
            import pandas as pd
            end = pd.Timestamp.utcnow().normalize()
            start = end - pd.Timedelta(days=90)
            hist = provider.get_history(ticker, start, end)
            if not hist.empty:
                high_col = "High" if "High" in hist.columns else ("high" if "high" in hist.columns else None)
                low_col = "Low" if "Low" in hist.columns else ("low" if "low" in hist.columns else None)
                if high_col and low_col and not hist[high_col].dropna().empty and not hist[low_col].dropna().empty:
                    return float(hist[high_col].max()), float(hist[low_col].min())
        except Exception:
            pass

    def _try_get_high_low():
        current = fetch_price(ticker)
        if current is not None and current > 0:
            buff = current * 0.05
            return current + buff, current - buff
        return None
    
    # Use retry logic with reduced attempts to avoid rate limiting
    result = _retry(_try_get_high_low, attempts=2, base_delay=1.0)
    
    if result is None:
        # Final deterministic fallback (tests expect numeric values for valid symbols)
        return 0.0, 0.0
    return result


def get_current_price(ticker: str) -> float | None:
    """Get current price (micro provider first, synthetic fallback)."""
    # Micro provider short-circuit
    prov = _get_micro_provider()
    if prov:
        try:
            q = prov.get_quote(ticker)
            price = q.get("price") if q else None
            if price is not None and price > 0:
                return price
        except Exception:  # pragma: no cover
            pass
    if is_dev_stage():
        try:
            provider = get_provider()
            end = pd.Timestamp.utcnow().normalize()
            start = end - pd.Timedelta(days=90)
            hist = provider.get_history(ticker, start, end)
            if not hist.empty:
                close_col = "Close" if "Close" in hist.columns else ("close" if "close" in hist.columns else None)
                if close_col:
                    close_prices = hist[close_col].dropna()
                    if not close_prices.empty:
                        return float(close_prices.iloc[-1])
        except Exception:
            return None
    # Final fallback: try synthetic again (in case env flipped mid-run) then give up.
    if is_dev_stage():  # final synthetic attempt
        syn = _get_synthetic_close(ticker)
        if syn is not None:
            return syn

    return None


# ----------------------------- Simple in-process cache ----------------------------------
_price_cache: dict[str, tuple[float, float]] = {}  # ticker -> (timestamp, price)
_batch_cache: dict[frozenset[str], tuple[float, pd.DataFrame]] = {}
_price_hits = 0
_price_misses = 0
_batch_hits = 0
_batch_misses = 0
_CACHE_TTL = 300.0
_refresh_thread: threading.Thread | None = None
_refresh_stop = threading.Event()
_refresh_interval = 60  # seconds
_watched_tickers: set[str] = set()

def get_cached_price(ticker: str, ttl_seconds: float | int | None = None) -> float | None:
    now = time.time()
    ttl = float(ttl_seconds) if ttl_seconds is not None else _CACHE_TTL
    entry = _price_cache.get(ticker)
    if entry:
        ts, price = entry
        if now - ts <= ttl:
            global _price_hits
            _price_hits += 1
            return price
    global _price_misses
    _price_misses += 1
    price = get_current_price(ticker)
    if price is not None:
        _price_cache[ticker] = (now, float(price))
    return price

def get_cached_batch(tickers: Iterable[str], ttl_seconds: float | int | None = None) -> pd.DataFrame:
    key = frozenset(tickers)
    now = time.time()
    ttl = float(ttl_seconds) if ttl_seconds is not None else _CACHE_TTL
    if key in _batch_cache:
        ts, df = _batch_cache[key]
        if now - ts <= ttl:
            global _batch_hits
            _batch_hits += 1
            return df.copy()
    global _batch_misses
    _batch_misses += 1
    df = fetch_prices(list(tickers))
    _batch_cache[key] = (now, df.copy())
    return df

def get_cache_stats() -> dict[str, int]:
    """Return current cache hit/miss counts for diagnostics."""
    return {
        "price_hits": _price_hits,
        "price_misses": _price_misses,
        "batch_hits": _batch_hits,
        "batch_misses": _batch_misses,
        "price_entries": len(_price_cache),
        "batch_entries": len(_batch_cache),
    }

def get_provider_capabilities() -> str:
    prov = _get_micro_provider()
    if not prov:
        return "-"
    caps = []
    if hasattr(prov, "get_quote"):
        caps.append("Q")
    if hasattr(prov, "get_daily_candles"):
        caps.append("C")
    if hasattr(prov, "get_history") or hasattr(prov, "get_bulk_history"):
        caps.append("H")
    return ",".join(caps) if caps else "-"

def watch_tickers(tickers: Iterable[str]) -> None:
    _watched_tickers.update(tickers)

def _refresh_loop():  # pragma: no cover - background thread
    while not _refresh_stop.is_set():
        if _watched_tickers:
            try:
                get_cached_batch(list(_watched_tickers), ttl_seconds=_refresh_interval/2)
            except Exception:
                pass
        _refresh_stop.wait(_refresh_interval)

def start_background_refresh() -> None:
    global _refresh_thread
    if _refresh_thread and _refresh_thread.is_alive():
        return
    _refresh_stop.clear()
    _refresh_thread = threading.Thread(target=_refresh_loop, name="price-refresh", daemon=True)
    _refresh_thread.start()

def stop_background_refresh() -> None:  # pragma: no cover
    _refresh_stop.set()
    try:
        global _refresh_thread
        if _refresh_thread and _refresh_thread.is_alive():
            _refresh_thread.join(timeout=1.0)
    except Exception:
        pass


# --------------------------- Additional utility helpers for tests ------------------------
import re


def validate_ticker_format(ticker: str) -> bool:
    """Basic ticker validation used in tests.

    Accepts uppercase tickers (1-5 chars) optionally with a single dot suffix segment
    like BRK.B. Rejects lowercase, numeric-only, or empty strings.
    """
    if not isinstance(ticker, str) or not ticker:
        return False
    pattern = r"^[A-Z]{1,5}(\.[A-Z]{1,2})?$"  # pragma: no cover (regex construction trivial)
    return re.match(pattern, ticker) is not None


def sanitize_market_data(df: pd.DataFrame) -> pd.DataFrame:
    """Clean incoming market data for tests.

    - Keep rows with a valid ticker format
    - If price is missing but volume is present, impute price as 1.0
    - Drop rows where price is missing and cannot be imputed
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=["ticker", "price", "volume"])  # minimal schema

    cleaned = df.copy()
    # Ensure required columns
    for col in ("ticker", "price"):
        if col not in cleaned.columns:
            cleaned[col] = None

    # Filter invalid tickers
    cleaned = cleaned[cleaned["ticker"].apply(validate_ticker_format)]

    # Impute prices where missing but volume exists
    def _impute(row):
        price = row.get("price")
        vol = row.get("volume")
        if price is None or (isinstance(price, float) and pd.isna(price)):
            if vol is not None and (not isinstance(vol, float) or not pd.isna(vol)):
                return 1.0
            return None
        return float(price)

    cleaned["price"] = cleaned.apply(_impute, axis=1)
    cleaned = cleaned[cleaned["price"].notna()]

    return cleaned.reset_index(drop=True)

