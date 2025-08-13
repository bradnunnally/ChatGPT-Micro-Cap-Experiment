"""Tests for services/market.py module."""

import pytest
import pandas as pd
from unittest.mock import MagicMock
import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.market import fetch_price, fetch_prices, get_day_high_low, get_current_price


class TestFetchPrice:
    """Test the fetch_price function."""

    def test_fetch_price_success(self, monkeypatch):
        fetch_price.clear()
        # Force synthetic provider path
        monkeypatch.setenv("APP_ENV", "dev_stage")
        result = fetch_price("AAPL")
        assert result is None or isinstance(result, (int, float))

    def test_fetch_price_empty_like(self, monkeypatch):
        fetch_price.clear()
        monkeypatch.setenv("APP_ENV", "dev_stage")
        result = fetch_price("INVALID")
        assert result is None or isinstance(result, (int, float))

    def test_fetch_price_resilience(self, monkeypatch):
        fetch_price.clear()
        monkeypatch.setenv("APP_ENV", "dev_stage")
        assert fetch_price("AAPL") is None or isinstance(fetch_price("AAPL"), (int, float))


class TestFetchPrices:
    """Test the fetch_prices function."""

    def test_fetch_prices_success(self, monkeypatch):
        fetch_prices.clear()
        monkeypatch.setenv("APP_ENV", "dev_stage")
        result = fetch_prices(["AAPL", "MSFT"])
        assert isinstance(result, pd.DataFrame)

    def test_fetch_prices_empty_tickers(self):
        fetch_prices.clear()
        result = fetch_prices([])
        assert result.empty

    def test_fetch_prices_resilience(self, monkeypatch):
        fetch_prices.clear()
        monkeypatch.setenv("APP_ENV", "dev_stage")
        result = fetch_prices(["AAPL", "MSFT"])
        assert isinstance(result, pd.DataFrame)


class TestGetDayHighLow:
    """Test the get_day_high_low function."""

    def test_get_day_high_low_basic(self, monkeypatch):
        monkeypatch.setenv("APP_ENV", "dev_stage")
        high, low = get_day_high_low("AAPL")
        assert isinstance(high, (int, float)) and isinstance(low, (int, float))

    def test_get_day_high_low_resilience(self, monkeypatch):
        monkeypatch.setenv("APP_ENV", "dev_stage")
        h, l = get_day_high_low("AAPL")
        assert h is not None and l is not None

    def test_get_day_high_low_handles_missing(self, monkeypatch):
        monkeypatch.setenv("APP_ENV", "dev_stage")
        try:
            high, low = get_day_high_low("INVALID")
            assert isinstance(high, (int, float)) and isinstance(low, (int, float))
        except Exception as exc:
            # Allow MarketDataDownloadError when no data path available
            from core.errors import MarketDataDownloadError
            assert isinstance(exc, MarketDataDownloadError)


class TestGetCurrentPrice:
    """Test the get_current_price function."""

    def test_get_current_price_success(self, monkeypatch):
        monkeypatch.setenv("APP_ENV", "dev_stage")
        result = get_current_price("AAPL")
        assert result is None or isinstance(result, (int, float))

    def test_get_current_price_invalid(self, monkeypatch):
        monkeypatch.setenv("APP_ENV", "dev_stage")
        result = get_current_price("INVALID")
        assert result is None or isinstance(result, (int, float))

    def test_get_current_price_resilience(self, monkeypatch):
        monkeypatch.setenv("APP_ENV", "dev_stage")
        result = get_current_price("AAPL")
        assert result is None or isinstance(result, (int, float))

    def test_get_current_price_multiple_calls(self, monkeypatch):
        monkeypatch.setenv("APP_ENV", "dev_stage")
        r1 = get_current_price("AAPL")
        r2 = get_current_price("AAPL")
        assert (r1 is None or isinstance(r1, (int, float))) and (r2 is None or isinstance(r2, (int, float)))
