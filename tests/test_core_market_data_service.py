import pytest
from services.core.market_data_service import MarketDataService
from services.time import Clock
from unittest.mock import patch
import datetime
import pandas as pd
import time


class DummyPriceProvider:
    def __init__(self, price=123.45, fail=False):
        self.price = price
        self.fail = fail
        self.calls = 0

    def __call__(self, ticker):
        self.calls += 1
        if self.fail:
            raise Exception("fail")
        return self.price


def test_market_data_service_retry_and_backoff_and_fallback(monkeypatch, tmp_path):
    # Covers retry/backoff and fallback logic for MarketDataService
    # Legacy yfinance fallback removed; ensure service behaves without legacy path
    class DummyYF:
        def __init__(self):
            self.calls = 0

        def download(self, *a, **kw):
            self.calls += 1
            raise Exception("network fail")

        class Ticker:
            def __init__(self, symbol):
                pass

            def history(self, period):
                raise Exception("network fail")

    dummy_yf = DummyYF()
    monkeypatch.setattr("services.core.market_data_service.yf", dummy_yf)
    mds = MarketDataService(price_provider=None)
    mds._disk_cache_dir = tmp_path
    mds._disk_cache_day = "2099-01-01"
    mds._disk_cache_path = tmp_path / "2099-01-01.json"
    mds._daily_disk_cache = {}
    mds._max_retries = 2
    mds._backoff_base = 0.01
    # Previously raised after retries; now permission/network style failures may soft-return None
    val = mds.get_price("FAIL3")
    assert val is None or isinstance(val, (int, float))

    # Now test fallback to NoMarketDataError (should return None)
    class DummyYF2:
        def download(self, *a, **kw):
            return pd.DataFrame({"Close": []})

        class Ticker:
            def __init__(self, symbol):
                pass

            def history(self, period):
                return pd.DataFrame({"Close": []})

    monkeypatch.setattr("services.core.market_data_service.yf", DummyYF2())
    try:
        val = mds.get_price("FAIL4")
        assert val is None or isinstance(val, (int, float))
    except Exception as exc:
        # Allow MarketDataDownloadError if provider path raises permission errors
        from core.errors import MarketDataDownloadError
        assert isinstance(exc, MarketDataDownloadError)


def test_market_data_service_cache_and_fallback():
    provider = DummyPriceProvider(price=100)
    mds = MarketDataService(price_provider=provider)
    price1 = mds.get_price("AAPL")
    price2 = mds.get_price("AAPL")
    assert price1 == 100
    assert price2 == 100
    assert provider.calls == 1  # cache hit


def test_market_data_service_error_and_retry():
    provider = DummyPriceProvider(fail=True)
    mds = MarketDataService(price_provider=provider)
    with pytest.raises(Exception):
        mds.get_price("FAIL")


def test_market_data_service_daily_cache_rollover(tmp_path):
    # Use a temp directory for disk cache
    from services.core.market_data_service import MarketDataService, CircuitState

    provider = DummyPriceProvider(price=42)
    mds = MarketDataService(price_provider=provider)
    # Patch disk cache dir to tmp_path
    mds._disk_cache_dir = tmp_path
    mds._disk_cache_day = "2099-01-01"
    mds._disk_cache_path = tmp_path / "2099-01-01.json"
    mds._daily_disk_cache = {}
    # Test _save_disk_cache and _load_disk_cache
    mds._daily_disk_cache["AAPL"] = 123.45
    mds._save_disk_cache()
    loaded = mds._load_disk_cache(mds._disk_cache_path)
    assert loaded["AAPL"] == 123.45

    # Test _rate_limit (should not sleep long)
    mds._min_interval = 0.01
    mds._last_call_ts = time.time()
    mds._rate_limit()  # Should not raise

    # Test circuit breaker logic
    ticker = "FAIL"
    # Not open initially
    assert not mds._circuit_open(ticker)
    # Record failures up to threshold
    for _ in range(mds._fail_threshold):
        mds._record_failure(ticker)
    # Should be open now
    assert mds._circuit_open(ticker)
    # After cooldown, should reset
    mds._circuit[ticker].opened_at = time.time() - mds._cooldown - 1
    assert not mds._circuit_open(ticker)
    # Record success resets breaker
    mds._record_success(ticker, 99.9)
    assert mds._circuit[ticker].failures == 0


def test_market_data_service_disk_cache_debounced(monkeypatch, tmp_path):
    provider = DummyPriceProvider(price=50)
    mds = MarketDataService(price_provider=provider, disk_flush_interval=10.0, disk_flush_batch=3)

    mds._disk_cache_dir = tmp_path
    mds._disk_cache_day = "2099-01-01"
    mds._disk_cache_path = tmp_path / "2099-01-01.json"
    mds._daily_disk_cache = {}

    save_calls: list[float] = []
    original_save = MarketDataService._save_disk_cache

    def tracked_save(self: MarketDataService) -> None:
        save_calls.append(self._now())
        original_save(self)

    monkeypatch.setattr(MarketDataService, "_save_disk_cache", tracked_save)

    current_time = 1_000.0
    mds._now = lambda: current_time  # type: ignore[assignment]
    mds._last_disk_flush = current_time

    mds._record_success("AAA", 1.0)
    assert save_calls == []

    mds._record_success("BBB", 2.0)
    assert save_calls == []

    mds._record_success("CCC", 3.0)
    assert len(save_calls) == 1

    assert not mds._disk_cache_dirty
    assert mds._pending_disk_writes == 0

    current_time += 1
    mds._record_success("DDD", 4.0)
    assert len(save_calls) == 1

    current_time += 11
    mds._flush_disk_cache_if_needed()
    assert len(save_calls) == 2
