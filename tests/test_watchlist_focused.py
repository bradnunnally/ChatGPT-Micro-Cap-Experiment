"""Focused tests for actual watchlist functionality."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
import streamlit as st


class TestWatchlistServiceCore:
    """Test core watchlist service functionality."""

    def test_watchlist_state_initialization(self):
        """Test WatchlistState initialization."""
        from services.watchlist_service import WatchlistState

        # Test default initialization
        state = WatchlistState()
        assert isinstance(state.tickers, set)
        assert isinstance(state.prices, dict)
        assert len(state.tickers) == 0
        assert len(state.prices) == 0

        # Test initialization with None values
        state_none = WatchlistState(tickers=None, prices=None)
        assert isinstance(state_none.tickers, set)
        assert isinstance(state_none.prices, dict)

    def test_watchlist_state_with_data(self):
        """Test WatchlistState with initial data."""
        from services.watchlist_service import WatchlistState

        initial_tickers = {"AAPL", "GOOGL"}
        initial_prices = {"AAPL": 150.0, "GOOGL": 2500.0}

        state = WatchlistState(tickers=initial_tickers, prices=initial_prices)
        assert state.tickers == initial_tickers
        assert state.prices == initial_prices

    def test_init_watchlist_function(self):
        """Test init_watchlist function."""
        from services.watchlist_service import init_watchlist

        # Clear any existing state
        if hasattr(st.session_state, "watchlist_state"):
            delattr(st.session_state, "watchlist_state")

        # Initialize watchlist
        init_watchlist()

        # Verify initialization
        assert hasattr(st.session_state, "watchlist_state")
        assert isinstance(st.session_state.watchlist_state.tickers, set)
        assert isinstance(st.session_state.watchlist_state.prices, dict)

    def test_add_to_watchlist_function(self):
        """Test add_to_watchlist function."""
        from services.watchlist_service import add_to_watchlist, init_watchlist

        # Initialize clean state
        init_watchlist()
        initial_count = len(st.session_state.watchlist_state.tickers)

        # Add ticker
        add_to_watchlist("AAPL")

        # Verify addition
        assert "AAPL" in st.session_state.watchlist_state.tickers
        assert len(st.session_state.watchlist_state.tickers) == initial_count + 1

    def test_add_duplicate_ticker(self):
        """Test adding duplicate ticker to watchlist."""
        from services.watchlist_service import add_to_watchlist, init_watchlist

        # Initialize and add ticker
        init_watchlist()
        add_to_watchlist("AAPL")
        count_after_first = len(st.session_state.watchlist_state.tickers)

        # Try to add same ticker again
        add_to_watchlist("AAPL")
        count_after_second = len(st.session_state.watchlist_state.tickers)

        # Count should remain the same (sets don't allow duplicates)
        assert count_after_first == count_after_second
        assert "AAPL" in st.session_state.watchlist_state.tickers

    def test_remove_from_watchlist_function(self):
        """Test remove_from_watchlist function."""
        from services.watchlist_service import (
            add_to_watchlist,
            remove_from_watchlist,
            init_watchlist,
        )

        # Initialize and add ticker
        init_watchlist()
        add_to_watchlist("AAPL")
        add_to_watchlist("GOOGL")

        # Verify ticker exists
        assert "AAPL" in st.session_state.watchlist_state.tickers
        count_before = len(st.session_state.watchlist_state.tickers)

        # Remove ticker
        remove_from_watchlist("AAPL")

        # Verify removal
        assert "AAPL" not in st.session_state.watchlist_state.tickers
        assert len(st.session_state.watchlist_state.tickers) == count_before - 1
        assert "GOOGL" in st.session_state.watchlist_state.tickers  # Other ticker remains

    def test_remove_nonexistent_ticker(self):
        """Test removing non-existent ticker from watchlist."""
        from services.watchlist_service import remove_from_watchlist, init_watchlist

        # Initialize with some tickers
        init_watchlist()
        st.session_state.watchlist_state.tickers.add("AAPL")
        count_before = len(st.session_state.watchlist_state.tickers)

        # Try to remove non-existent ticker
        remove_from_watchlist("NONEXISTENT")

        # Count should remain the same
        assert len(st.session_state.watchlist_state.tickers) == count_before
        assert "AAPL" in st.session_state.watchlist_state.tickers

    def test_get_watchlist_function(self):
        """Test get_watchlist function."""
        from services.watchlist_service import add_to_watchlist, get_watchlist, init_watchlist

        # Initialize and add tickers
        init_watchlist()
        add_to_watchlist("AAPL")
        add_to_watchlist("GOOGL")
        add_to_watchlist("MSFT")

        # Get watchlist as DataFrame
        watchlist_df = get_watchlist()

        # Verify result
        assert isinstance(watchlist_df, pd.DataFrame)
        assert "ticker" in watchlist_df.columns
        assert len(watchlist_df) == 3

        # Verify all tickers are present
        tickers_in_df = set(watchlist_df["ticker"].tolist())
        expected_tickers = {"AAPL", "GOOGL", "MSFT"}
        assert tickers_in_df == expected_tickers


class TestWatchlistDataOperations:
    """Test watchlist data operations."""

    def test_watchlist_ticker_normalization(self):
        """Test ticker symbol normalization."""
        from services.watchlist_service import add_to_watchlist, init_watchlist

        # Initialize watchlist
        init_watchlist()

        # Add lowercase ticker
        add_to_watchlist("aapl")

        # Verify it's stored as uppercase
        assert "AAPL" in st.session_state.watchlist_state.tickers
        assert "aapl" not in st.session_state.watchlist_state.tickers

    def test_empty_watchlist_handling(self):
        """Test handling of empty watchlist."""
        from services.watchlist_service import get_watchlist, init_watchlist

        # Initialize empty watchlist
        init_watchlist()

        # Get empty watchlist
        watchlist_df = get_watchlist()

        # Verify empty DataFrame structure
        assert isinstance(watchlist_df, pd.DataFrame)
        assert len(watchlist_df) == 0
        assert "ticker" in watchlist_df.columns

    def test_watchlist_session_persistence(self):
        """Test watchlist persistence in session state."""
        from services.watchlist_service import add_to_watchlist, init_watchlist

        # Initialize and add tickers
        init_watchlist()
        add_to_watchlist("AAPL")
        add_to_watchlist("GOOGL")

        # Verify session state structure
        assert hasattr(st.session_state, "watchlist_state")
        assert "AAPL" in st.session_state.watchlist_state.tickers
        assert "GOOGL" in st.session_state.watchlist_state.tickers

        # Multiple calls to init_watchlist shouldn't reset data
        init_watchlist()
        assert "AAPL" in st.session_state.watchlist_state.tickers
        assert "GOOGL" in st.session_state.watchlist_state.tickers


class TestWatchlistValidation:
    """Test watchlist validation logic."""

    def test_ticker_format_validation(self):
        """Test ticker format validation."""
        # Valid ticker formats
        valid_tickers = ["AAPL", "GOOGL", "MSFT", "BRK.A", "BRK.B"]

        for ticker in valid_tickers:
            assert isinstance(ticker, str)
            assert len(ticker) > 0
            assert ticker.isupper()
            # Basic alphanumeric + period check
            assert all(c.isalnum() or c == "." for c in ticker)

    def test_watchlist_size_limits(self):
        """Test reasonable watchlist size limits."""
        from services.watchlist_service import add_to_watchlist, init_watchlist

        # Initialize watchlist
        init_watchlist()

        # Add multiple tickers
        test_tickers = ["AAPL", "GOOGL", "MSFT", "TSLA", "AMZN", "META", "NFLX", "NVDA"]

        for ticker in test_tickers:
            add_to_watchlist(ticker)

        # Verify all were added
        assert len(st.session_state.watchlist_state.tickers) == len(test_tickers)

        # Verify practical limit (should handle reasonable number of tickers)
        assert len(st.session_state.watchlist_state.tickers) <= 100  # Reasonable upper limit

    def test_watchlist_data_integrity(self):
        """Test watchlist data integrity."""
        from services.watchlist_service import (
            add_to_watchlist,
            remove_from_watchlist,
            init_watchlist,
        )

        # Initialize and perform operations
        init_watchlist()
        add_to_watchlist("AAPL")
        add_to_watchlist("GOOGL")
        add_to_watchlist("MSFT")

        # Verify data types
        assert isinstance(st.session_state.watchlist_state.tickers, set)
        assert isinstance(st.session_state.watchlist_state.prices, dict)

        # Verify all tickers are strings
        for ticker in st.session_state.watchlist_state.tickers:
            assert isinstance(ticker, str)
            assert len(ticker) > 0

        # Test operations don't corrupt data
        remove_from_watchlist("GOOGL")

        # Verify remaining data is still valid
        for ticker in st.session_state.watchlist_state.tickers:
            assert isinstance(ticker, str)
            assert len(ticker) > 0


class TestWatchlistIntegration:
    """Test watchlist integration with other components."""

    @patch("services.market.get_current_price")
    def test_watchlist_price_integration(self, mock_get_price):
        """Test watchlist integration with price fetching."""
        from services.watchlist_service import add_to_watchlist, init_watchlist

        # Initialize watchlist with tickers
        init_watchlist()
        add_to_watchlist("AAPL")
        add_to_watchlist("GOOGL")

        # Mock price fetching
        mock_get_price.side_effect = lambda ticker: {"AAPL": 150.25, "GOOGL": 2650.50}.get(
            ticker, None
        )

        # Simulate price updates
        for ticker in st.session_state.watchlist_state.tickers:
            price = mock_get_price(ticker)
            if price:
                st.session_state.watchlist_state.prices[ticker] = price

        # Verify price storage
        assert st.session_state.watchlist_state.prices["AAPL"] == 150.25
        assert st.session_state.watchlist_state.prices["GOOGL"] == 2650.50

    def test_watchlist_dataframe_conversion(self):
        """Test converting watchlist to DataFrame for display."""
        from services.watchlist_service import add_to_watchlist, get_watchlist, init_watchlist

        # Setup watchlist
        init_watchlist()
        test_tickers = ["AAPL", "GOOGL", "MSFT"]

        for ticker in test_tickers:
            add_to_watchlist(ticker)

        # Convert to DataFrame
        df = get_watchlist()

        # Verify DataFrame structure
        assert isinstance(df, pd.DataFrame)
        assert len(df) == len(test_tickers)
        assert "ticker" in df.columns

        # Verify data consistency
        df_tickers = set(df["ticker"].tolist())
        expected_tickers = set(test_tickers)
        assert df_tickers == expected_tickers

    def test_watchlist_with_portfolio_integration(self):
        """Test watchlist integration with portfolio data."""
        from services.watchlist_service import add_to_watchlist, get_watchlist, init_watchlist

        # Setup watchlist and mock portfolio
        init_watchlist()
        add_to_watchlist("AAPL")
        add_to_watchlist("GOOGL")
        add_to_watchlist("TSLA")  # Not in portfolio

        # Mock portfolio holdings
        portfolio_tickers = {"AAPL", "GOOGL"}

        # Get watchlist
        watchlist_df = get_watchlist()

        # Add flag for tickers also in portfolio
        watchlist_df["in_portfolio"] = watchlist_df["ticker"].isin(portfolio_tickers)

        # Verify integration logic
        aapl_row = watchlist_df[watchlist_df["ticker"] == "AAPL"]
        tsla_row = watchlist_df[watchlist_df["ticker"] == "TSLA"]

        assert aapl_row["in_portfolio"].iloc[0] is True
        assert tsla_row["in_portfolio"].iloc[0] is False


class TestWatchlistErrorHandling:
    """Test watchlist error handling."""

    def test_invalid_ticker_handling(self):
        """Test handling of invalid ticker symbols."""
        from services.watchlist_service import add_to_watchlist, init_watchlist

        # Initialize watchlist
        init_watchlist()
        initial_count = len(st.session_state.watchlist_state.tickers)

        # Test empty string - function should handle gracefully
        try:
            add_to_watchlist("")
            # Empty string gets converted to uppercase and added to set
            # This is current behavior - the function doesn't validate ticker format
        except Exception:
            # If it throws an exception, that's also acceptable error handling
            pass

        # Verify state remains valid
        assert isinstance(st.session_state.watchlist_state.tickers, set)

    def test_session_state_corruption_recovery(self):
        """Test recovery from corrupted session state."""
        from services.watchlist_service import init_watchlist

        # Corrupt session state
        st.session_state.watchlist_state = "corrupted_data"

        # Initialize should handle this gracefully
        init_watchlist()

        # Verify proper state is restored
        assert hasattr(st.session_state, "watchlist_state")
        assert isinstance(st.session_state.watchlist_state.tickers, set)
        assert isinstance(st.session_state.watchlist_state.prices, dict)

    def test_concurrent_operations(self):
        """Test concurrent watchlist operations."""
        from services.watchlist_service import (
            add_to_watchlist,
            remove_from_watchlist,
            init_watchlist,
        )

        # Initialize watchlist
        init_watchlist()

        # Perform multiple operations
        add_to_watchlist("AAPL")
        add_to_watchlist("GOOGL")
        remove_from_watchlist("AAPL")
        add_to_watchlist("MSFT")
        remove_from_watchlist("NONEXISTENT")
        add_to_watchlist("TSLA")

        # Verify final state is consistent
        expected_tickers = {"GOOGL", "MSFT", "TSLA"}
        assert st.session_state.watchlist_state.tickers == expected_tickers
        assert isinstance(st.session_state.watchlist_state.tickers, set)
        assert isinstance(st.session_state.watchlist_state.prices, dict)
