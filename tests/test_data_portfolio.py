"""Tests for data/portfolio.py module."""

import pytest
import pandas as pd
from unittest.mock import patch, MagicMock, mock_open
import sys
from pathlib import Path
import sqlite3

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from data.portfolio import load_portfolio, save_portfolio_snapshot


class TestLoadPortfolio:
    """Test the load_portfolio function."""

    @patch("data.portfolio.get_connection")
    @patch("data.portfolio.init_db")
    def test_load_empty_portfolio_and_cash(self, mock_init_db, mock_get_connection):
        """Test loading when both portfolio and cash are empty."""
        # Mock database connection
        mock_conn = MagicMock()
        mock_get_connection.return_value.__enter__.return_value = mock_conn

        # Mock empty portfolio query
        mock_conn.execute.return_value.fetchone.return_value = None

        # Mock pandas read_sql_query to return empty DataFrame
        with patch("pandas.read_sql_query") as mock_read_sql:
            mock_read_sql.return_value = pd.DataFrame()

            portfolio, cash, is_first_time = load_portfolio()

            assert portfolio.empty
            assert cash == 0.0
            assert is_first_time is True

    @patch("data.portfolio.get_connection")
    @patch("data.portfolio.init_db")
    def test_load_portfolio_with_cash(self, mock_init_db, mock_get_connection):
        """Test loading portfolio with cash balance."""
        # Mock database connection
        mock_conn = MagicMock()
        mock_get_connection.return_value.__enter__.return_value = mock_conn

        # Mock cash balance
        mock_conn.execute.return_value.fetchone.return_value = [1000.0]

        # Mock portfolio data
        portfolio_data = pd.DataFrame(
            {
                "ticker": ["AAPL", "MSFT"],
                "shares": [100, 50],
                "price": [150.0, 300.0],
                "stop_loss": [140.0, 280.0],
            }
        )

        with patch("pandas.read_sql_query") as mock_read_sql:
            mock_read_sql.return_value = portfolio_data

            with patch("data.portfolio.ensure_schema") as mock_ensure_schema:
                mock_ensure_schema.return_value = portfolio_data

                portfolio, cash, is_first_time = load_portfolio()

                assert not portfolio.empty
                assert cash == 1000.0
                assert is_first_time is False
                assert len(portfolio) == 2

    @patch("data.portfolio.get_connection")
    @patch("data.portfolio.init_db")
    def test_load_portfolio_no_cash_record(self, mock_init_db, mock_get_connection):
        """Test loading portfolio when no cash record exists."""
        # Mock database connection
        mock_conn = MagicMock()
        mock_get_connection.return_value.__enter__.return_value = mock_conn

        # Mock no cash balance
        mock_conn.execute.return_value.fetchone.return_value = None

        # Mock portfolio data
        portfolio_data = pd.DataFrame(
            {"ticker": ["AAPL"], "shares": [100], "price": [150.0], "stop_loss": [140.0]}
        )

        with patch("pandas.read_sql_query") as mock_read_sql:
            mock_read_sql.return_value = portfolio_data

            with patch("data.portfolio.ensure_schema") as mock_ensure_schema:
                mock_ensure_schema.return_value = portfolio_data

                portfolio, cash, is_first_time = load_portfolio()

                assert not portfolio.empty
                assert cash == 0.0
                assert is_first_time is False


class TestSavePortfolioSnapshot:
    """Test the save_portfolio_snapshot function."""

    @patch("data.portfolio.get_connection")
    @patch("data.portfolio.init_db")
    @patch("data.portfolio.fetch_prices")
    def test_save_empty_portfolio(self, mock_fetch_prices, mock_init_db, mock_get_connection):
        """Test saving an empty portfolio snapshot."""
        # Mock database connection
        mock_conn = MagicMock()
        mock_get_connection.return_value.__enter__.return_value = mock_conn

        # Mock empty fetch_prices
        mock_fetch_prices.return_value = pd.DataFrame()

        # Empty portfolio
        portfolio_df = pd.DataFrame(
            columns=["ticker", "shares", "stop_loss", "buy_price", "cost_basis"]
        )
        cash = 1000.0

        result = save_portfolio_snapshot(portfolio_df, cash)

        # Should return a DataFrame with just the TOTAL row
        assert len(result) == 1
        assert result.iloc[0]["ticker"] == "TOTAL"
        assert result.iloc[0]["cash_balance"] == 1000.0
        assert result.iloc[0]["total_equity"] == 1000.0

    @patch("data.portfolio.get_connection")
    @patch("data.portfolio.init_db")
    @patch("services.price_fetching.fetch_prices")
    def test_save_portfolio_with_positions(
        self, mock_fetch_prices, mock_init_db, mock_get_connection
    ):
        """Test saving portfolio snapshot with positions."""
        # Mock database connection
        mock_conn = MagicMock()
        mock_get_connection.return_value.__enter__.return_value = mock_conn

        # Mock price data with proper MultiIndex construction
        data = {"Close": [160.0, 320.0]}
        index = pd.Index(["2023-01-01"])
        columns = pd.MultiIndex.from_tuples([("Close", "AAPL"), ("Close", "MSFT")])
        price_data = pd.DataFrame([[160.0, 320.0]], index=index, columns=columns)
        mock_fetch_prices.return_value = price_data

        # Portfolio with positions
        portfolio_df = pd.DataFrame(
            {
                "ticker": ["AAPL", "MSFT"],
                "shares": [100, 50],
                "stop_loss": [140.0, 280.0],
                "buy_price": [150.0, 300.0],  # Cost basis prices
                "cost_basis": [15000.0, 15000.0],
            }
        )
        cash = 1000.0

        result = save_portfolio_snapshot(portfolio_df, cash)

        # Should have 3 rows: 2 positions + 1 total
        assert len(result) == 3

        # Check AAPL position
        aapl_row = result[result["ticker"] == "AAPL"].iloc[0]
        assert aapl_row["shares"] == 100
        assert aapl_row["current_price"] == 160.0
        assert aapl_row["total_value"] == 16000.0  # 100 * 160
        assert aapl_row["pnl"] == 1000.0  # (160-150) * 100

        # Check MSFT position
        msft_row = result[result["ticker"] == "MSFT"].iloc[0]
        assert msft_row["shares"] == 50
        assert msft_row["current_price"] == 320.0
        assert msft_row["total_value"] == 16000.0  # 50 * 320
        assert msft_row["pnl"] == 1000.0  # (320-300) * 50

        # Check TOTAL row
        total_row = result[result["ticker"] == "TOTAL"].iloc[0]
        assert total_row["total_value"] == 32000.0  # 16000 + 16000
        assert total_row["pnl"] == 2000.0  # 1000 + 1000
        assert total_row["cash_balance"] == 1000.0
        assert total_row["total_equity"] == 33000.0  # 32000 + 1000

    @patch("data.portfolio.get_connection")
    @patch("data.portfolio.init_db")
    @patch("services.price_fetching.fetch_prices")
    def test_save_portfolio_single_ticker(
        self, mock_fetch_prices, mock_init_db, mock_get_connection
    ):
        """Test saving portfolio snapshot with single ticker (non-MultiIndex data)."""
        # Mock database connection
        mock_conn = MagicMock()
        mock_get_connection.return_value.__enter__.return_value = mock_conn

        # Mock single ticker price data (non-MultiIndex)
        price_data = pd.DataFrame({"Close": [160.0]}, index=["2023-01-01"])
        mock_fetch_prices.return_value = price_data

        # Portfolio with single position
        portfolio_df = pd.DataFrame(
            {
                "ticker": ["AAPL"],
                "shares": [100],
                "stop_loss": [140.0],
                "buy_price": [150.0],
                "cost_basis": [15000.0],
            }
        )
        cash = 500.0

        result = save_portfolio_snapshot(portfolio_df, cash)

        # Should have 2 rows: 1 position + 1 total
        assert len(result) == 2

        # Check AAPL position
        aapl_row = result[result["ticker"] == "AAPL"].iloc[0]
        assert aapl_row["current_price"] == 160.0
        assert aapl_row["total_value"] == 16000.0

    @patch("data.portfolio.get_connection")
    @patch("data.portfolio.init_db")
    @patch("services.price_fetching.get_current_price")
    @patch("services.price_fetching.get_manual_price")
    @patch("services.price_fetching.fetch_prices")
    def test_save_portfolio_missing_price_data(
        self, mock_fetch_prices, mock_get_manual_price, mock_get_current_price, mock_init_db, mock_get_connection
    ):
        """Test saving portfolio snapshot when price data is missing."""
        # Mock database connection
        mock_conn = MagicMock()
        mock_get_connection.return_value.__enter__.return_value = mock_conn

        # Mock empty price data from all sources
        mock_fetch_prices.return_value = pd.DataFrame()
        mock_get_manual_price.return_value = None
        mock_get_current_price.return_value = None

        # Portfolio with position
        portfolio_df = pd.DataFrame(
            {
                "ticker": ["AAPL"],
                "shares": [100],
                "stop_loss": [140.0],
                "buy_price": [150.0],
                "cost_basis": [15000.0],
            }
        )
        cash = 500.0

        result = save_portfolio_snapshot(portfolio_df, cash)

        # Should still create snapshot but with 0 current prices
        assert len(result) == 2
        aapl_row = result[result["ticker"] == "AAPL"].iloc[0]
        assert aapl_row["current_price"] == 0.0
        assert aapl_row["total_value"] == 0.0

    @patch("services.data_persistence.get_connection")
    @patch("services.data_persistence.init_db")
    @patch("services.price_fetching.fetch_prices")
    def test_save_portfolio_database_operations(
        self, mock_fetch_prices, mock_init_db, mock_get_connection
    ):
        """Test that save_portfolio_snapshot makes correct database calls."""
        # Mock database connection
        mock_conn = MagicMock()
        mock_get_connection.return_value.__enter__.return_value = mock_conn

        # Mock empty fetch_prices
        mock_fetch_prices.return_value = pd.DataFrame()

        # Empty portfolio
        portfolio_df = pd.DataFrame(
            columns=["ticker", "shares", "stop_loss", "buy_price", "cost_basis"]
        )
        cash = 1000.0

        with patch("pandas.DataFrame.to_sql") as mock_to_sql:
            save_portfolio_snapshot(portfolio_df, cash)

            # Verify database operations (init_db can be called multiple times in refactored system)
            assert mock_init_db.call_count >= 1
            mock_conn.execute.assert_any_call("DELETE FROM portfolio")
            mock_conn.execute.assert_any_call(
                "INSERT OR REPLACE INTO cash (id, balance) VALUES (0, ?)", (1000.0,)
            )

            # For empty portfolio, only portfolio_history gets saved (1 call)
            # Portfolio table doesn't get to_sql call because the DataFrame is empty
            assert mock_to_sql.call_count == 1