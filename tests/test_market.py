"""Tests for services/market.py module."""

import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.market import fetch_price, fetch_prices, get_day_high_low, get_current_price


class TestFetchPrice:
    """Test the fetch_price function."""

    @patch("yfinance.download")
    @patch("services.market.log_error")
    def test_fetch_price_success(self, mock_log_error, mock_yf_download):
        """Test successful price fetch."""
        # Mock yfinance data
        mock_data = pd.DataFrame({"Close": [150.50]})
        mock_yf_download.return_value = mock_data

        # Clear cache to ensure function runs
        fetch_price.clear()

        result = fetch_price("AAPL")

        assert result == 150.50
        mock_yf_download.assert_called_once_with("AAPL", period="1d", progress=False)
        mock_log_error.assert_not_called()

    @patch("yfinance.download")
    @patch("services.market.log_error")
    def test_fetch_price_empty_data(self, mock_log_error, mock_yf_download):
        """Test fetch_price with empty data."""
        # Mock empty DataFrame
        mock_yf_download.return_value = pd.DataFrame()

        fetch_price.clear()

        result = fetch_price("INVALID")

        assert result is None
        mock_log_error.assert_not_called()

    @patch("yfinance.download")
    @patch("services.market.log_error")
    def test_fetch_price_exception(self, mock_log_error, mock_yf_download):
        """Test fetch_price with exception."""
        # Mock exception
        mock_yf_download.side_effect = Exception("Network error")

        fetch_price.clear()

        result = fetch_price("AAPL")

        assert result is None
        mock_log_error.assert_called_once_with("Failed to fetch price for AAPL")


class TestFetchPrices:
    """Test the fetch_prices function."""

    @patch("yfinance.download")
    @patch("services.market.log_error")
    def test_fetch_prices_success(self, mock_log_error, mock_yf_download):
        """Test successful prices fetch for multiple tickers."""
        # Mock yfinance data
        mock_data = pd.DataFrame({("Close", "AAPL"): [150.50], ("Close", "MSFT"): [300.25]})
        mock_data.columns = pd.MultiIndex.from_tuples(mock_data.columns)
        mock_yf_download.return_value = mock_data

        fetch_prices.clear()

        result = fetch_prices(["AAPL", "MSFT"])

        assert not result.empty
        mock_yf_download.assert_called_once_with(["AAPL", "MSFT"], period="1d", progress=False)
        mock_log_error.assert_not_called()

    @patch("yfinance.download")
    @patch("services.market.log_error")
    def test_fetch_prices_empty_tickers(self, mock_log_error, mock_yf_download):
        """Test fetch_prices with empty ticker list."""
        fetch_prices.clear()

        result = fetch_prices([])

        assert result.empty
        mock_yf_download.assert_not_called()
        mock_log_error.assert_not_called()

    @patch("yfinance.download")
    @patch("services.market.log_error")
    def test_fetch_prices_exception(self, mock_log_error, mock_yf_download):
        """Test fetch_prices with exception."""
        # Mock exception
        mock_yf_download.side_effect = Exception("Network error")

        fetch_prices.clear()

        result = fetch_prices(["AAPL", "MSFT"])

        assert result.empty
        mock_log_error.assert_called_once_with("Failed to fetch prices for AAPL, MSFT")


class TestGetDayHighLow:
    """Test the get_day_high_low function."""

    @patch("yfinance.download")
    def test_get_day_high_low_success(self, mock_yf_download):
        """Test successful high/low fetch."""
        # Mock yfinance data
        mock_data = pd.DataFrame({"High": [155.00], "Low": [148.50]})
        mock_yf_download.return_value = mock_data

        high, low = get_day_high_low("AAPL")

        assert high == 155.00
        assert low == 148.50
        mock_yf_download.assert_called_once_with("AAPL", period="1d", progress=False)

    @patch("yfinance.download")
    def test_get_day_high_low_download_exception(self, mock_yf_download):
        """Test get_day_high_low with download exception."""
        # Mock exception
        mock_yf_download.side_effect = Exception("Network error")

        with pytest.raises(RuntimeError, match="Data download failed"):
            get_day_high_low("AAPL")

    @patch("yfinance.download")
    def test_get_day_high_low_empty_data(self, mock_yf_download):
        """Test get_day_high_low with empty data."""
        # Mock empty DataFrame
        mock_yf_download.return_value = pd.DataFrame()

        with pytest.raises(ValueError, match="No market data available"):
            get_day_high_low("AAPL")


class TestGetCurrentPrice:
    """Test the get_current_price function."""

    @patch("yfinance.download")
    def test_get_current_price_success(self, mock_yf_download):
        """Test successful current price fetch."""
        # Mock yfinance data
        mock_data = pd.DataFrame({"Close": [150.75]})
        mock_yf_download.return_value = mock_data

        result = get_current_price("AAPL")

        assert result == 150.75
        mock_yf_download.assert_called_once_with(
            "AAPL", period="1d", progress=False, auto_adjust=True
        )

    @patch("yfinance.download")
    def test_get_current_price_empty_data(self, mock_yf_download):
        """Test get_current_price with empty data."""
        # Mock empty DataFrame
        mock_yf_download.return_value = pd.DataFrame()

        result = get_current_price("INVALID")

        assert result is None

    @patch("yfinance.download")
    @patch("services.market.log_error")
    def test_get_current_price_exception(self, mock_log_error, mock_yf_download):
        """Test get_current_price with exception."""
        # Mock exception
        mock_yf_download.side_effect = Exception("Network error")

        result = get_current_price("AAPL")

        assert result is None
        mock_log_error.assert_called_once()

    @patch("yfinance.download")
    def test_get_current_price_with_multiple_rows(self, mock_yf_download):
        """Test get_current_price when data has multiple rows."""
        # Mock yfinance data with multiple rows
        mock_data = pd.DataFrame({"Close": [150.75, 151.25, 152.00]})
        mock_yf_download.return_value = mock_data

        result = get_current_price("AAPL")

        # Should return the first row's close price
        assert result == 150.75
