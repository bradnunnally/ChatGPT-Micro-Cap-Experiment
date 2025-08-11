"""Tests for services/portfolio_manager.py."""

import pytest
import pandas as pd
from services.portfolio_manager import PortfolioManager, PortfolioMetrics


class TestPortfolioMetrics:
    """Test the PortfolioMetrics dataclass."""

    def test_portfolio_metrics_creation(self):
        """Test creating PortfolioMetrics with all parameters."""
        metrics = PortfolioMetrics(
            total_value=10000.0, total_gain=1000.0, total_return=0.10, holdings_count=5
        )

        assert metrics.total_value == 10000.0
        assert metrics.total_gain == 1000.0
        assert metrics.total_return == 0.10
        assert metrics.holdings_count == 5


class TestPortfolioManager:
    """Test the PortfolioManager class."""

    def test_init_empty_portfolio(self):
        """Test initializing with empty portfolio."""
        manager = PortfolioManager()
        assert manager._portfolio.empty

    def test_add_single_position(self):
        """Test adding a single position to portfolio."""
        manager = PortfolioManager()
        manager.add_position("AAPL", 100, 150.0)

        assert len(manager._portfolio) == 1
        assert manager._portfolio.iloc[0]["ticker"] == "AAPL"
        assert manager._portfolio.iloc[0]["shares"] == 100
        assert manager._portfolio.iloc[0]["price"] == 150.0
        assert manager._portfolio.iloc[0]["cost_basis"] == 15000.0

    def test_add_multiple_positions(self):
        """Test adding multiple positions to portfolio."""
        manager = PortfolioManager()
        manager.add_position("AAPL", 100, 150.0)
        manager.add_position("MSFT", 50, 300.0)
        manager.add_position("GOOGL", 25, 2500.0)

        assert len(manager._portfolio) == 3
        tickers = manager._portfolio["ticker"].tolist()
        assert "AAPL" in tickers
        assert "MSFT" in tickers
        assert "GOOGL" in tickers

    def test_add_position_with_fractional_shares(self):
        """Test adding position with fractional shares."""
        manager = PortfolioManager()
        manager.add_position("SPY", 10.5, 400.0)

        assert manager._portfolio.iloc[0]["shares"] == 10.5
        assert manager._portfolio.iloc[0]["cost_basis"] == 4200.0

    def test_get_portfolio_metrics_empty(self):
        """Test getting metrics for empty portfolio."""
        manager = PortfolioManager()
        metrics = manager.get_portfolio_metrics()

        assert metrics.total_value == 0
        assert metrics.total_gain == 0
        assert metrics.total_return == 0
        assert metrics.holdings_count == 0

    def test_get_portfolio_metrics_single_position(self):
        """Test getting metrics for portfolio with single position."""
        manager = PortfolioManager()
        manager.add_position("AAPL", 100, 150.0)

        metrics = manager.get_portfolio_metrics()

        assert metrics.total_value == 15000.0  # 100 * 150
        assert metrics.total_gain == 0.0  # Current price = buy price
        assert metrics.total_return == 0.0
        assert metrics.holdings_count == 1

    def test_get_portfolio_metrics_multiple_positions(self):
        """Test getting metrics for portfolio with multiple positions."""
        manager = PortfolioManager()
        manager.add_position("AAPL", 100, 150.0)  # $15,000
        manager.add_position("MSFT", 50, 300.0)  # $15,000
        manager.add_position("GOOGL", 10, 2500.0)  # $25,000

        metrics = manager.get_portfolio_metrics()

        assert metrics.total_value == 55000.0  # Total value
        assert metrics.total_gain == 0.0  # No gains (current = buy price)
        assert metrics.total_return == 0.0
        assert metrics.holdings_count == 3

    def test_get_portfolio_metrics_with_gains(self):
        """Test portfolio metrics calculation with different current prices."""
        manager = PortfolioManager()

        # Add positions and manually update prices to simulate current market values
        manager.add_position("AAPL", 100, 150.0)  # Cost: $15,000
        manager.add_position("MSFT", 50, 300.0)  # Cost: $15,000

        # Manually update prices to simulate current market values
        manager._portfolio.loc[0, "price"] = 180.0  # AAPL up to $180
        manager._portfolio.loc[1, "price"] = 280.0  # MSFT down to $280

        metrics = manager.get_portfolio_metrics()

        expected_total_value = (100 * 180.0) + (50 * 280.0)  # $18,000 + $14,000 = $32,000
        expected_cost_basis = 15000.0 + 15000.0  # $30,000
        expected_gain = expected_total_value - expected_cost_basis  # $2,000
        expected_return = expected_gain / expected_cost_basis  # 0.0667

        assert metrics.total_value == expected_total_value
        assert metrics.total_gain == expected_gain
        assert abs(metrics.total_return - expected_return) < 0.0001
        assert metrics.holdings_count == 2

    def test_get_portfolio_metrics_zero_cost_basis(self):
        """Test portfolio metrics when cost basis is zero."""
        manager = PortfolioManager()

        # Create a position with zero cost (edge case)
        manager.add_position("FREE", 100, 0.0)

        metrics = manager.get_portfolio_metrics()

        assert metrics.total_value == 0.0
        assert metrics.total_gain == 0.0
        assert metrics.total_return == 0  # Should handle division by zero
        assert metrics.holdings_count == 1

    def test_portfolio_dataframe_structure(self):
        """Test that the internal portfolio DataFrame has the correct structure."""
        manager = PortfolioManager()
        manager.add_position("TEST", 50, 100.0)

        df = manager._portfolio
        expected_columns = ["ticker", "shares", "price", "cost_basis"]

        assert list(df.columns) == expected_columns
        assert len(df) == 1
