import pytest
import pandas as pd
import tempfile
import os
from unittest.mock import patch, Mock
from datetime import datetime

from services.portfolio_manager import PortfolioManager
from services.core.market_service import MarketService


class TestPortfolioManagerHistoryPersistence:
    """Test historical data persistence functionality in PortfolioManager."""

    def test_save_history_for_ticker_success(self):
        """Test successful historical data persistence."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_db:
            temp_db_path = temp_db.name
        
        try:
            with patch('data.db.DB_FILE', temp_db_path):
                manager = PortfolioManager()
                
                # Create sample historical data
                dates = pd.date_range(start='2024-01-01', periods=5, freq='D')
                history_data = pd.DataFrame({
                    'date': dates,
                    'open': [100.0, 101.0, 102.0, 103.0, 104.0],
                    'high': [105.0, 106.0, 107.0, 108.0, 109.0],
                    'low': [95.0, 96.0, 97.0, 98.0, 99.0],
                    'close': [102.0, 103.0, 104.0, 105.0, 106.0],
                    'volume': [1000000] * 5
                })
                
                # Save history
                manager._save_history_for_ticker('TEST', history_data)
                
                # Verify data was saved
                from data.db import get_connection
                with get_connection() as conn:
                    cursor = conn.execute("SELECT COUNT(*) FROM market_history WHERE ticker = 'TEST'")
                    count = cursor.fetchone()[0]
                    assert count == 5
                    
                    # Verify data integrity
                    cursor = conn.execute("SELECT date, close FROM market_history WHERE ticker = 'TEST' ORDER BY date")
                    rows = cursor.fetchall()
                    assert rows[0][1] == 102.0  # First close price
                    assert rows[-1][1] == 106.0  # Last close price
        finally:
            if os.path.exists(temp_db_path):
                os.unlink(temp_db_path)

    def test_save_history_empty_dataframe(self):
        """Test handling of empty historical data."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_db:
            temp_db_path = temp_db.name
        
        try:
            with patch('data.db.DB_FILE', temp_db_path):
                manager = PortfolioManager()
                
                # Test with empty DataFrame
                empty_history = pd.DataFrame()
                manager._save_history_for_ticker('EMPTY', empty_history)
                
                # Should not create any records
                from data.db import get_connection
                with get_connection() as conn:
                    # Check if table exists first
                    cursor = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='market_history'")
                    table_count = cursor.fetchone()[0]
                    
                    if table_count > 0:
                        cursor = conn.execute("SELECT COUNT(*) FROM market_history WHERE ticker = 'EMPTY'")
                        count = cursor.fetchone()[0]
                        assert count == 0
        finally:
            if os.path.exists(temp_db_path):
                os.unlink(temp_db_path)

    def test_add_position_triggers_history_fetch(self):
        """Test that adding a position triggers historical data fetch and storage."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_db:
            temp_db_path = temp_db.name
        
        try:
            with patch('data.db.DB_FILE', temp_db_path):
                # Mock market service
                mock_market_service = Mock(spec=MarketService)
                sample_history = pd.DataFrame({
                    'date': pd.date_range(start='2024-01-01', periods=3, freq='D'),
                    'close': [150.0, 151.0, 152.0],
                    'open': [149.0, 150.0, 151.0],
                    'high': [152.0, 153.0, 154.0],
                    'low': [148.0, 149.0, 150.0],
                    'volume': [1000000] * 3
                })
                mock_market_service.fetch_history.return_value = sample_history
                
                manager = PortfolioManager(market_service=mock_market_service)
                
                # Add position
                manager.add_position("AAPL", 10, 150.0)
                
                # Verify fetch_history was called
                mock_market_service.fetch_history.assert_called_once_with("AAPL", months=6)
                
                # Verify position was added
                positions = manager.get_positions()
                assert len(positions) == 1
                assert positions.iloc[0]['ticker'] == 'AAPL'
                
                # Verify historical data was stored
                from data.db import get_connection
                with get_connection() as conn:
                    cursor = conn.execute("SELECT COUNT(*) FROM market_history WHERE ticker = 'AAPL'")
                    count = cursor.fetchone()[0]
                    assert count == 3
        finally:
            if os.path.exists(temp_db_path):
                os.unlink(temp_db_path)

    def test_history_fetch_failure_graceful_handling(self):
        """Test that position addition works even when history fetch fails."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_db:
            temp_db_path = temp_db.name
        
        try:
            with patch('data.db.DB_FILE', temp_db_path):
                # Mock market service to raise exception
                mock_market_service = Mock(spec=MarketService)
                mock_market_service.fetch_history.side_effect = Exception("API Error")
                
                manager = PortfolioManager(market_service=mock_market_service)
                
                # This should still work despite the exception
                manager.add_position("FAIL", 5, 100.0)
                
                # Verify position was still added
                positions = manager.get_positions()
                assert len(positions) == 1
                assert positions.iloc[0]['ticker'] == 'FAIL'
                
                # Verify no historical data was stored
                from data.db import get_connection
                with get_connection() as conn:
                    cursor = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='market_history'")
                    table_exists = cursor.fetchone()[0] > 0
                    
                    if table_exists:
                        cursor = conn.execute("SELECT COUNT(*) FROM market_history WHERE ticker = 'FAIL'")
                        count = cursor.fetchone()[0]
                        assert count == 0
        finally:
            if os.path.exists(temp_db_path):
                os.unlink(temp_db_path)

    def test_duplicate_data_handling(self):
        """Test that duplicate historical data is handled properly."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_db:
            temp_db_path = temp_db.name
        
        try:
            with patch('data.db.DB_FILE', temp_db_path):
                manager = PortfolioManager()
                
                # Create sample historical data
                history_data = pd.DataFrame({
                    'date': ['2024-01-01', '2024-01-02'],
                    'close': [100.0, 101.0],
                    'open': [99.0, 100.0],
                    'high': [101.0, 102.0],
                    'low': [98.0, 99.0],
                    'volume': [1000000, 1100000]
                })
                
                # Save history twice
                manager._save_history_for_ticker('DUP', history_data)
                manager._save_history_for_ticker('DUP', history_data)
                
                # Should only have one set of data (no duplicates)
                from data.db import get_connection
                with get_connection() as conn:
                    cursor = conn.execute("SELECT COUNT(*) FROM market_history WHERE ticker = 'DUP'")
                    count = cursor.fetchone()[0]
                    assert count == 2  # Should replace, not duplicate
        finally:
            if os.path.exists(temp_db_path):
                os.unlink(temp_db_path)