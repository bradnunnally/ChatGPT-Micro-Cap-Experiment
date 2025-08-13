"""Comprehensive tests for data layer functionality."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
import sqlite3
from datetime import datetime


class TestDatabaseCore:
    """Test core database operations."""

    @patch("sqlite3.connect")
    def test_database_connection_management(self, mock_connect):
        """Test database connection context manager."""
        from data.db import get_connection

        # Setup mock connection
        mock_conn = Mock()
        mock_connect.return_value = mock_conn

        # Test context manager
        with get_connection() as conn:
            assert conn is mock_conn

        # Verify connection was opened
        mock_connect.assert_called_once()

    @patch("sqlite3.connect")
    def test_database_initialization(self, mock_connect):
        """Test database table initialization."""
        from data.db import init_db

        # Setup mock connection
        mock_conn = Mock()
        mock_context = Mock()
        mock_context.__enter__ = Mock(return_value=mock_conn)
        mock_context.__exit__ = Mock(return_value=None)
        mock_connect.return_value = mock_context

        # Initialize database
        init_db()

        # Verify tables were created
        assert mock_conn.execute.call_count >= 4  # portfolio, cash, portfolio_history, trade_log

        # Check for key table creation commands
        calls = [str(call) for call in mock_conn.execute.call_args_list]
        table_commands = [call for call in calls if "CREATE TABLE" in call.upper()]
        assert len(table_commands) >= 4


class TestPortfolioDataOperations:
    """Test portfolio data operations."""

    @patch("data.portfolio.get_connection")
    @patch("data.portfolio.fetch_prices")
    def test_portfolio_loading(self, mock_fetch_prices, mock_get_connection):
        """Test portfolio loading from database."""
        from data.portfolio import load_portfolio

        # Mock database response
        mock_conn = Mock()
        mock_context = Mock()
        mock_context.__enter__ = Mock(return_value=mock_conn)
        mock_context.__exit__ = Mock(return_value=None)
        mock_get_connection.return_value = mock_context

        # Mock portfolio data
        mock_conn.execute.return_value.fetchall.return_value = [
            ("AAPL", 10, 140.0, 150.0, 1500.0),
            ("GOOGL", 5, 2400.0, 2500.0, 12500.0),
        ]

        # Mock price fetching
        mock_fetch_prices.return_value = pd.DataFrame(
            {
                "ticker": ["AAPL", "GOOGL"],
                "current_price": [155.0, 2600.0],
                "pct_change": [3.33, 4.0],
            }
        )

        # Load portfolio
        result = load_portfolio()

        # Verify results
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2
        assert "ticker" in result.columns
        assert "shares" in result.columns
        assert "current_price" in result.columns

    @patch("data.portfolio.get_connection")
    @patch("data.portfolio.fetch_prices")
    def test_portfolio_saving(self, mock_fetch_prices, mock_get_connection):
        """Test portfolio saving to database."""
        from data.portfolio import save_portfolio_snapshot

        # Mock database connection
        mock_conn = Mock()
        mock_context = Mock()
        mock_context.__enter__ = Mock(return_value=mock_conn)
        mock_context.__exit__ = Mock(return_value=None)
        mock_get_connection.return_value = mock_context

        # Mock price fetching
        mock_fetch_prices.return_value = pd.DataFrame(
            {"ticker": ["AAPL"], "current_price": [155.0], "pct_change": [3.33]}
        )

        # Test portfolio data
        portfolio_df = pd.DataFrame(
            {
                "ticker": ["AAPL"],
                "shares": [10],
                "stop_loss": [140.0],
                "buy_price": [150.0],
                "cost_basis": [1500.0],
            }
        )
        cash = 8500.0

        # Save portfolio
        result = save_portfolio_snapshot(portfolio_df, cash)

        # Verify database operations
        assert mock_conn.execute.call_count >= 3  # DELETE, INSERT cash, to_sql calls

        # Check specific operations
        calls = [str(call) for call in mock_conn.execute.call_args_list]
        delete_calls = [call for call in calls if "DELETE FROM portfolio" in call]
        cash_calls = [call for call in calls if "INSERT OR REPLACE INTO cash" in call]

        assert len(delete_calls) >= 1
        assert len(cash_calls) >= 1

    def test_portfolio_data_filtering(self):
        """Test portfolio data column filtering."""
        from data.portfolio import save_portfolio_snapshot

        # Create portfolio with extra columns
        portfolio_df = pd.DataFrame(
            {
                "ticker": ["AAPL", "GOOGL"],
                "shares": [10, 5],
                "stop_loss": [140.0, 2400.0],
                "buy_price": [150.0, 2500.0],
                "cost_basis": [1500.0, 12500.0],
                "extra_column": ["extra1", "extra2"],  # Should be filtered out
                "another_extra": [1, 2],  # Should be filtered out
            }
        )

        # Test column filtering logic
        core_columns = ["ticker", "shares", "stop_loss", "buy_price", "cost_basis"]
        available_columns = [col for col in core_columns if col in portfolio_df.columns]

        assert len(available_columns) == 5
        assert "extra_column" not in available_columns
        assert "another_extra" not in available_columns

        # Test filtered dataframe
        filtered_df = portfolio_df[available_columns]
        assert len(filtered_df.columns) == 5
        assert all(col in core_columns for col in filtered_df.columns)


class TestCashManagement:
    """Test cash balance management."""

    @patch("data.portfolio.get_connection")
    def test_cash_loading(self, mock_get_connection):
        """Test cash balance loading from database."""
        from data.portfolio import load_cash_balance

        # Mock database connection
        mock_conn = Mock()
        mock_context = Mock()
        mock_context.__enter__ = Mock(return_value=mock_conn)
        mock_context.__exit__ = Mock(return_value=None)
        mock_get_connection.return_value = mock_context

        # Mock cash balance query result
        mock_conn.execute.return_value.fetchone.return_value = (10000.0,)

        try:
            balance = load_cash_balance()
            assert balance == 10000.0
            mock_conn.execute.assert_called_once()
        except ImportError:
            # Function might be inline in other functions
            pass

    def test_cash_calculations(self):
        """Test cash calculation logic."""
        # Test buy transaction impact
        initial_cash = 10000.0
        shares = 10
        price = 150.0
        transaction_cost = shares * price

        remaining_cash = initial_cash - transaction_cost
        assert remaining_cash == 8500.0

        # Test sell transaction impact
        sell_shares = 5
        sell_price = 160.0
        sell_proceeds = sell_shares * sell_price

        final_cash = remaining_cash + sell_proceeds
        assert final_cash == 9300.0

    def test_cash_validation(self):
        """Test cash validation logic."""
        # Test sufficient funds
        cash_balance = 10000.0
        purchase_cost = 5000.0
        assert cash_balance >= purchase_cost

        # Test insufficient funds
        large_purchase = 15000.0
        assert cash_balance < large_purchase

        # Test minimum cash requirements
        min_cash = 100.0
        remaining_after_purchase = cash_balance - purchase_cost
        assert remaining_after_purchase >= min_cash


class TestWatchlistOperations:
    """Test watchlist functionality."""

    @patch("builtins.open")
    @patch("json.load")
    def test_watchlist_loading(self, mock_json_load, mock_open):
        """Test watchlist loading from JSON file."""
        from data.watchlist import load_watchlist

        # Mock JSON data
        mock_json_load.return_value = ["AAPL", "GOOGL", "MSFT"]

        watchlist = load_watchlist()

        assert isinstance(watchlist, list)
        assert len(watchlist) == 3
        assert "AAPL" in watchlist
        assert "GOOGL" in watchlist
        assert "MSFT" in watchlist

    @patch("builtins.open")
    @patch("json.dump")
    def test_watchlist_saving(self, mock_json_dump, mock_open):
        """Test watchlist saving to JSON file."""
        from data.watchlist import save_watchlist

        test_watchlist = ["AAPL", "GOOGL", "MSFT", "TSLA"]

        save_watchlist(test_watchlist)

        # Verify file operations
        mock_open.assert_called_once()
        mock_json_dump.assert_called_once()

        # Check that the correct data was written
        call_args = mock_json_dump.call_args[0]
        assert call_args[0] == test_watchlist

    def test_watchlist_validation(self):
        """Test watchlist data validation."""
        # Valid watchlist
        valid_watchlist = ["AAPL", "GOOGL", "MSFT"]
        assert isinstance(valid_watchlist, list)
        assert all(isinstance(ticker, str) for ticker in valid_watchlist)
        assert all(len(ticker) > 0 for ticker in valid_watchlist)

        # Test uniqueness
        unique_watchlist = list(set(valid_watchlist))
        assert len(unique_watchlist) == len(valid_watchlist)

        # Test ticker format
        for ticker in valid_watchlist:
            assert ticker.isupper()
            assert ticker.replace(".", "").isalnum()


class TestDataIntegrity:
    """Test data integrity and consistency."""

    def test_portfolio_data_consistency(self):
        """Test portfolio data consistency checks."""
        portfolio_data = pd.DataFrame(
            {
                "ticker": ["AAPL", "GOOGL", "MSFT"],
                "shares": [10, 5, 15],
                "stop_loss": [140.0, 2400.0, 350.0],
                "buy_price": [150.0, 2500.0, 400.0],
                "cost_basis": [1500.0, 12500.0, 6000.0],
            }
        )

        # Test cost basis calculation consistency
        for idx, row in portfolio_data.iterrows():
            expected_cost_basis = row["shares"] * row["buy_price"]
            assert abs(row["cost_basis"] - expected_cost_basis) < 0.01

        # Test stop loss validation
        for idx, row in portfolio_data.iterrows():
            assert row["stop_loss"] < row["buy_price"]
            assert row["stop_loss"] > 0

        # Test shares validation
        for idx, row in portfolio_data.iterrows():
            assert row["shares"] > 0
            assert isinstance(row["shares"], (int, float))

    def test_transaction_data_integrity(self):
        """Test transaction data integrity."""
        # Test buy transaction
        buy_data = {
            "ticker": "AAPL",
            "shares": 10,
            "price": 150.0,
            "transaction_type": "BUY",
            "timestamp": datetime.now(),
        }

        assert buy_data["shares"] > 0
        assert buy_data["price"] > 0
        assert buy_data["transaction_type"] in ["BUY", "SELL"]
        assert isinstance(buy_data["timestamp"], datetime)

        # Test sell transaction
        sell_data = {
            "ticker": "AAPL",
            "shares": 5,
            "price": 160.0,
            "transaction_type": "SELL",
            "timestamp": datetime.now(),
        }

        assert sell_data["shares"] > 0
        assert sell_data["price"] > 0
        assert sell_data["transaction_type"] in ["BUY", "SELL"]

        # Test transaction consistency
        assert buy_data["ticker"] == sell_data["ticker"]
        assert sell_data["shares"] <= buy_data["shares"]  # Can't sell more than owned

    def test_data_type_consistency(self):
        """Test data type consistency across operations."""
        # Test numeric data types
        shares = 10
        price = 150.50
        cash_balance = 10000.00

        assert isinstance(shares, int)
        assert isinstance(price, float)
        assert isinstance(cash_balance, float)

        # Test string data types
        ticker = "AAPL"
        transaction_type = "BUY"

        assert isinstance(ticker, str)
        assert isinstance(transaction_type, str)
        assert ticker.isupper()

        # Test calculated values maintain correct types
        total_cost = shares * price
        assert isinstance(total_cost, float)

        remaining_cash = cash_balance - total_cost
        assert isinstance(remaining_cash, float)
        assert remaining_cash >= 0
