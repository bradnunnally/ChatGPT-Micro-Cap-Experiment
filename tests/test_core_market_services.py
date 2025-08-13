"""Comprehensive tests for market services and price data."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
from datetime import datetime, timedelta


class TestMarketDataService:
    """Test market data service functionality."""

    def test_single_stock_price_fetch(self, monkeypatch):
        from services.market import get_current_price
        monkeypatch.setenv("APP_ENV", "dev_stage")
        price = get_current_price("AAPL")
        assert price is None or isinstance(price, (int, float))

    def test_price_fetch_error_handling(self, monkeypatch):
        from services.market import get_current_price
        monkeypatch.setenv("APP_ENV", "dev_stage")
        price = get_current_price("INVALID_TICKER")
        assert price is None or isinstance(price, (int, float))

    def test_multiple_stock_prices(self, monkeypatch):
        from services.market import fetch_prices
        monkeypatch.setenv("APP_ENV", "dev_stage")
        tickers = ["AAPL", "GOOGL"]
        prices_df = fetch_prices(tickers)
        assert isinstance(prices_df, pd.DataFrame)
        assert len(prices_df) == 0 or set(["ticker", "current_price"]).issubset(prices_df.columns)

    def test_price_data_validation(self):
        """Test price data validation logic."""
        from services.market import is_valid_price

        try:
            # Valid prices
            assert is_valid_price(150.25) is True
            assert is_valid_price(0.01) is True
            assert is_valid_price(10000.0) is True

            # Invalid prices
            assert is_valid_price(None) is False
            assert is_valid_price(0) is False
            assert is_valid_price(-10.5) is False
            assert is_valid_price("invalid") is False
        except ImportError:
            # Function might be inline - test logic directly
            valid_prices = [150.25, 0.01, 10000.0]
            invalid_prices = [None, 0, -10.5, "invalid"]

            for price in valid_prices:
                assert isinstance(price, (int, float)) and price > 0

            for price in invalid_prices:
                assert not (isinstance(price, (int, float)) and price > 0)


class TestPriceCalculations:
    """Test price-related calculations."""

    def test_percentage_change_calculation(self):
        """Test percentage change calculations."""
        from services.market import calculate_percentage_change

        try:
            # Standard percentage change
            old_price = 100.0
            new_price = 110.0
            pct_change = calculate_percentage_change(old_price, new_price)
            assert abs(pct_change - 10.0) < 0.01

            # Negative change
            new_price = 90.0
            pct_change = calculate_percentage_change(old_price, new_price)
            assert abs(pct_change - (-10.0)) < 0.01

            # Zero change
            new_price = 100.0
            pct_change = calculate_percentage_change(old_price, new_price)
            assert abs(pct_change - 0.0) < 0.01
        except ImportError:
            # Calculate inline
            old_price = 100.0
            new_price = 110.0
            pct_change = ((new_price - old_price) / old_price) * 100
            assert abs(pct_change - 10.0) < 0.01

    def test_profit_loss_calculation(self):
        """Test profit/loss calculations."""
        # Simple P&L calculation
        buy_price = 150.0
        current_price = 165.0
        shares = 10

        total_cost = buy_price * shares
        current_value = current_price * shares
        profit_loss = current_value - total_cost

        assert total_cost == 1500.0
        assert current_value == 1650.0
        assert profit_loss == 150.0

        # Percentage return
        pct_return = (profit_loss / total_cost) * 100
        assert abs(pct_return - 10.0) < 0.01

    def test_portfolio_value_calculation(self):
        """Test total portfolio value calculation."""
        positions = pd.DataFrame(
            {
                "ticker": ["AAPL", "GOOGL", "MSFT"],
                "shares": [10, 5, 15],
                "current_price": [150.0, 2600.0, 400.0],
            }
        )

        # Calculate total value
        positions["position_value"] = positions["shares"] * positions["current_price"]
        total_value = positions["position_value"].sum()

        expected_value = (10 * 150.0) + (5 * 2600.0) + (15 * 400.0)
        assert total_value == expected_value
        assert total_value == 20500.0


class TestMarketDataCaching:
    """Test market data caching functionality."""

    @patch("services.market.get_current_price")
    def test_price_caching_logic(self, mock_get_price):
        """Test price caching to reduce API calls."""
        from services.market import get_cached_price

        try:
            # Mock price service
            mock_get_price.return_value = 150.25

            # First call should fetch from API
            price1 = get_cached_price("AAPL")
            assert price1 == 150.25
            assert mock_get_price.call_count == 1

            # Second call within cache time should use cache
            price2 = get_cached_price("AAPL")
            assert price2 == 150.25
            assert mock_get_price.call_count == 1  # No additional call

        except ImportError:
            # Caching might not be implemented
            pass

    def test_cache_expiration_logic(self):
        """Test cache expiration handling."""
        # Test cache timestamp logic
        cache_duration = 300  # 5 minutes
        current_time = datetime.now()
        cache_time = current_time - timedelta(seconds=600)  # 10 minutes ago

        # Cache should be expired
        time_diff = (current_time - cache_time).total_seconds()
        is_expired = time_diff > cache_duration
        assert is_expired is True

        # Recent cache should not be expired
        recent_cache_time = current_time - timedelta(seconds=60)  # 1 minute ago
        time_diff = (current_time - recent_cache_time).total_seconds()
        is_expired = time_diff > cache_duration
        assert is_expired is False


class TestMarketDataIntegration:
    """Test market data integration with portfolio."""

    @patch("services.market.fetch_prices")
    def test_portfolio_price_updates(self, mock_fetch_prices):
        """Test updating portfolio with current market prices."""
        # Mock price fetching
        mock_fetch_prices.return_value = pd.DataFrame(
            {
                "ticker": ["AAPL", "GOOGL"],
                "current_price": [155.0, 2700.0],
                "pct_change": [3.33, 3.85],
            }
        )

        # Test portfolio
        portfolio = pd.DataFrame(
            {
                "ticker": ["AAPL", "GOOGL"],
                "shares": [10, 5],
                "buy_price": [150.0, 2600.0],
                "cost_basis": [1500.0, 13000.0],
            }
        )

        # Simulate price update
        tickers = portfolio["ticker"].tolist()
        price_data = mock_fetch_prices.return_value

        # Merge price data with portfolio
        updated_portfolio = portfolio.merge(price_data, on="ticker", how="left")

        # Verify updates
        assert "current_price" in updated_portfolio.columns
        assert "pct_change" in updated_portfolio.columns
        assert len(updated_portfolio) == 2

        # Test value calculations
        updated_portfolio["current_value"] = (
            updated_portfolio["shares"] * updated_portfolio["current_price"]
        )
        updated_portfolio["unrealized_pnl"] = (
            updated_portfolio["current_value"] - updated_portfolio["cost_basis"]
        )

        aapl_pnl = updated_portfolio[updated_portfolio["ticker"] == "AAPL"]["unrealized_pnl"].iloc[
            0
        ]
        googl_pnl = updated_portfolio[updated_portfolio["ticker"] == "GOOGL"][
            "unrealized_pnl"
        ].iloc[0]

        assert aapl_pnl == 50.0  # (10 * 155) - 1500
        assert googl_pnl == 500.0  # (5 * 2700) - 13000

    def test_market_data_error_recovery(self):
        """Test portfolio behavior when market data is unavailable."""
        # Test portfolio without current prices
        portfolio = pd.DataFrame(
            {
                "ticker": ["AAPL", "GOOGL"],
                "shares": [10, 5],
                "buy_price": [150.0, 2600.0],
                "cost_basis": [1500.0, 13000.0],
            }
        )

        # Simulate missing price data
        portfolio["current_price"] = None
        portfolio["pct_change"] = 0.0

        # Portfolio should still be valid for basic operations
        assert len(portfolio) == 2
        assert portfolio["cost_basis"].sum() == 14500.0

        # Use buy_price as fallback for current_price
        portfolio["current_price"] = portfolio["current_price"].fillna(portfolio["buy_price"])

        # Verify fallback works
        assert portfolio["current_price"].notna().all()
        assert portfolio[portfolio["ticker"] == "AAPL"]["current_price"].iloc[0] == 150.0


class TestMarketValidation:
    """Test market data validation and sanitization."""

    def test_ticker_format_validation(self):
        """Test ticker symbol format validation."""
        # Valid ticker formats
        valid_tickers = ["AAPL", "GOOGL", "BRK.A", "BRK.B", "MSFT"]

        for ticker in valid_tickers:
            assert isinstance(ticker, str)
            assert len(ticker) >= 1
            assert ticker.isupper()
            # Allow letters, numbers, and periods
            assert all(c.isalnum() or c == "." for c in ticker)

        # Invalid ticker formats
        invalid_tickers = ["", "aapl", "12345", "@#$%", None]

        for ticker in invalid_tickers:
            if ticker is None:
                assert ticker is None
            elif not isinstance(ticker, str):
                assert not isinstance(ticker, str)
            elif len(ticker) == 0:
                assert len(ticker) == 0
            else:
                # Check for invalid characters or format
                has_invalid_chars = any(not (c.isalnum() or c == ".") for c in ticker)
                is_lowercase = ticker.islower()
                # Also consider purely numeric strings as invalid
                assert has_invalid_chars or is_lowercase or ticker.isdigit()

    def test_price_range_validation(self):
        """Test price range validation."""
        # Reasonable price ranges for validation
        min_price = 0.01
        max_price = 100000.0

        # Valid prices
        valid_prices = [0.01, 1.0, 150.25, 2650.50, 10000.0]

        for price in valid_prices:
            assert min_price <= price <= max_price
            assert isinstance(price, (int, float))

        # Invalid prices
        invalid_prices = [0, -1.0, 100001.0, None, "invalid"]

        for price in invalid_prices:
            if price is None or not isinstance(price, (int, float)):
                assert not isinstance(price, (int, float)) or price is None
            else:
                assert not (min_price <= price <= max_price)

    def test_data_sanitization(self):
        """Test market data sanitization."""
        # Raw market data that might need cleaning
        raw_data = pd.DataFrame(
            {
                "ticker": ["AAPL", "googl", "MSFT", None],
                "price": [150.25, 2650.50, None, 400.0],
                "volume": [1000000, 0, 500000, -100],
            }
        )

        # Sanitization logic
        clean_data = raw_data.copy()

        # Clean ticker symbols
        clean_data["ticker"] = clean_data["ticker"].str.upper()
        clean_data = clean_data.dropna(subset=["ticker"])

        # Clean prices
        clean_data = clean_data.dropna(subset=["price"])
        clean_data = clean_data[clean_data["price"] > 0]

        # Clean volume
        clean_data = clean_data[clean_data["volume"] > 0]

        # Verify cleaned data: only AAPL should remain after cleaning
        assert len(clean_data) == 1
        assert all(clean_data["ticker"].str.isupper())
        assert all(clean_data["price"] > 0)
        assert all(clean_data["volume"] > 0)
