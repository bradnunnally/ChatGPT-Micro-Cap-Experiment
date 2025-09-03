"""Tests for MarketService.fetch_history functionality."""

import unittest.mock as mock
from datetime import datetime, timedelta

import pandas as pd
import pytest

from services.core.market_service import MarketService
from services.portfolio_manager import PortfolioManager


class TestMarketServiceFetchHistory:
    """Test the fetch_history method in MarketService."""

    def test_fetch_history_with_daily_candles_provider(self):
        """Test fetch_history uses get_daily_candles when available."""
        # Mock provider with get_daily_candles method
        mock_provider = mock.MagicMock()
        mock_provider.get_daily_candles.return_value = pd.DataFrame({
            'date': [datetime.now().date() - timedelta(days=i) for i in range(5)],
            'open': [100.0, 101.0, 102.0, 103.0, 104.0],
            'high': [105.0, 106.0, 107.0, 108.0, 109.0],
            'low': [95.0, 96.0, 97.0, 98.0, 99.0],
            'close': [102.0, 103.0, 104.0, 105.0, 106.0],
            'volume': [1000, 1100, 1200, 1300, 1400]
        })
        
        with mock.patch('micro_config.get_provider', return_value=mock_provider):
            service = MarketService()
            result = service.fetch_history("AAPL", months=6)
            
            assert not result.empty
            assert len(result) == 5
            assert "close" in result.columns
            mock_provider.get_daily_candles.assert_called_once()

    def test_fetch_history_with_generic_history_provider(self):
        """Test fetch_history falls back to get_history method."""
        # Mock provider with only get_history method
        mock_provider = mock.MagicMock()
        mock_provider.get_history.return_value = pd.DataFrame({
            'date': [datetime.now().date() - timedelta(days=i) for i in range(3)],
            'close': [100.0, 101.0, 102.0],
            'volume': [1000, 1100, 1200]
        })
        # Remove get_daily_candles to force fallback
        del mock_provider.get_daily_candles
        
        with mock.patch('micro_config.get_provider', return_value=mock_provider):
            service = MarketService()
            result = service.fetch_history("AAPL", months=6)
            
            assert not result.empty
            assert len(result) == 3
            mock_provider.get_history.assert_called_once()

    def test_fetch_history_returns_empty_on_failure(self):
        """Test fetch_history returns empty DataFrame when provider fails."""
        # Mock provider that raises exceptions
        mock_provider = mock.MagicMock()
        mock_provider.get_daily_candles.side_effect = Exception("Provider error")
        mock_provider.get_history.side_effect = Exception("Provider error")
        
        with mock.patch('micro_config.get_provider', return_value=mock_provider):
            service = MarketService()
            result = service.fetch_history("AAPL", months=6)
            
            assert result.empty
            assert list(result.columns) == ["date", "open", "high", "low", "close", "volume"]

    def test_fetch_history_validates_inputs(self):
        """Test fetch_history handles invalid inputs gracefully."""
        service = MarketService()
        
        # Test invalid symbol
        result = service.fetch_history("", months=6)
        assert result.empty
        
        result = service.fetch_history(None, months=6)
        assert result.empty
        
        # Test invalid months
        result = service.fetch_history("AAPL", months=0)
        assert result.empty
        
        result = service.fetch_history("AAPL", months=-1)
        assert result.empty

    def test_fetch_history_calculates_correct_date_range(self):
        """Test fetch_history calculates correct start/end dates."""
        mock_provider = mock.MagicMock()
        mock_provider.get_daily_candles.return_value = pd.DataFrame()
        
        with mock.patch('micro_config.get_provider', return_value=mock_provider):
            service = MarketService()
            service.fetch_history("AAPL", months=6)
            
            # Verify the date range calculation
            call_args = mock_provider.get_daily_candles.call_args
            start_date = call_args.kwargs['start']
            end_date = call_args.kwargs['end']
            
            # Should be approximately 6 months (180 days)
            date_diff = end_date - start_date
            assert 170 <= date_diff.days <= 190  # Allow some variance


class TestPortfolioManagerFetchHistoryIntegration:
    """Test that PortfolioManager calls fetch_history when adding positions."""

    def test_add_position_calls_fetch_history(self):
        """Test that add_position triggers fetch_history for the ticker."""
        # Mock the market service
        mock_market_service = mock.MagicMock()
        mock_market_service.fetch_history.return_value = pd.DataFrame({
            'date': [datetime.now().date()],
            'close': [100.0],
            'volume': [1000]
        })
        
        # Create portfolio manager with mocked service
        portfolio_manager = PortfolioManager(market_service=mock_market_service)
        
        # Add a position
        portfolio_manager.add_position("AAPL", 10, 150.0)
        
        # Verify fetch_history was called
        mock_market_service.fetch_history.assert_called_once_with("AAPL", months=6)

    def test_add_position_validates_inputs(self):
        """Test that add_position validates inputs properly."""
        portfolio_manager = PortfolioManager()
        
        # Test invalid ticker
        with pytest.raises(ValueError, match="Invalid ticker"):
            portfolio_manager.add_position("", 10, 150.0)
        
        with pytest.raises(ValueError, match="Invalid ticker"):
            portfolio_manager.add_position(None, 10, 150.0)
        
        # Test invalid shares
        with pytest.raises(ValueError, match="Invalid shares"):
            portfolio_manager.add_position("AAPL", 0, 150.0)
        
        with pytest.raises(ValueError, match="Invalid shares"):
            portfolio_manager.add_position("AAPL", -5, 150.0)
        
        # Test invalid price
        with pytest.raises(ValueError, match="Invalid price"):
            portfolio_manager.add_position("AAPL", 10, 0)
        
        with pytest.raises(ValueError, match="Invalid price"):
            portfolio_manager.add_position("AAPL", 10, -100)

    def test_add_position_continues_on_fetch_history_failure(self):
        """Test that add_position doesn't fail when fetch_history raises an exception."""
        # Mock market service that raises exception on fetch_history
        mock_market_service = mock.MagicMock()
        mock_market_service.fetch_history.side_effect = Exception("Network error")
        
        portfolio_manager = PortfolioManager(market_service=mock_market_service)
        
        # Should not raise exception
        portfolio_manager.add_position("AAPL", 10, 150.0)
        
        # Verify the position was still added
        metrics = portfolio_manager.get_portfolio_metrics()
        assert metrics.holdings_count == 1
        assert metrics.total_value == 1500.0  # 10 shares * 150.0 price

    def test_save_history_for_ticker_is_called(self):
        """Test that _save_history_for_ticker is called when history is fetched."""
        # Mock market service that returns history
        mock_market_service = mock.MagicMock()
        history_data = pd.DataFrame({
            'date': [datetime.now().date()],
            'close': [100.0],
            'volume': [1000]
        })
        mock_market_service.fetch_history.return_value = history_data
        
        portfolio_manager = PortfolioManager(market_service=mock_market_service)
        
        # Mock the _save_history_for_ticker method
        with mock.patch.object(portfolio_manager, '_save_history_for_ticker') as mock_save:
            portfolio_manager.add_position("AAPL", 10, 150.0)
            
            # Verify _save_history_for_ticker was called with correct args
            mock_save.assert_called_once_with("AAPL", history_data)

    def test_remove_position(self):
        """Test removing positions from portfolio."""
        portfolio_manager = PortfolioManager()
        
        # Add a position first
        portfolio_manager.add_position("AAPL", 10, 150.0)
        assert portfolio_manager.get_portfolio_metrics().holdings_count == 1
        
        # Remove the position
        result = portfolio_manager.remove_position("AAPL")
        assert result is True
        assert portfolio_manager.get_portfolio_metrics().holdings_count == 0
        
        # Try to remove non-existent position
        result = portfolio_manager.remove_position("GOOGL")
        assert result is False

    def test_get_positions(self):
        """Test getting current portfolio positions."""
        portfolio_manager = PortfolioManager()
        
        # Initially empty
        positions = portfolio_manager.get_positions()
        assert positions.empty
        
        # Add a position
        portfolio_manager.add_position("AAPL", 10, 150.0)
        positions = portfolio_manager.get_positions()
        
        assert len(positions) == 1
        assert positions.iloc[0]["ticker"] == "AAPL"
        assert positions.iloc[0]["shares"] == 10
        assert positions.iloc[0]["price"] == 150.0
