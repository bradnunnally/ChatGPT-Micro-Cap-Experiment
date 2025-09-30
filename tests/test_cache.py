"""
Tests for market data caching functionality.
"""

import time
import unittest
from unittest.mock import patch, MagicMock
import pandas as pd

from utils.cache import (
    get_cached_price_data, 
    get_cached_price_history, 
    warm_cache_for_symbols,
    get_cache_stats,
    clear_cache,
    COMMON_SYMBOLS
)


class TestMarketCache(unittest.TestCase):
    """Test market data caching functionality."""
    
    def setUp(self):
        """Clear cache before each test."""
        clear_cache()

    def tearDown(self):
        """Clear cache after each test."""
        clear_cache()

    @patch('utils.cache._get_market_service')
    def test_cached_price_data(self, mock_get_service):
        """Test that price data is cached correctly."""
        # Mock market service
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service
        
        # Mock historical data
        mock_history = pd.DataFrame({
            'date': ['2024-01-01', '2024-01-02'],
            'close': [100.0, 102.0],
            'volume': [1000000, 1100000]
        })
        mock_service.fetch_history.return_value = mock_history
        
        # First call should miss cache
        result1 = get_cached_price_data("AAPL")
        self.assertEqual(result1["symbol"], "AAPL")
        self.assertEqual(result1["close"], 102.0)
        self.assertEqual(result1["pct_change"], 2.0)  # (102-100)/100 * 100
        self.assertEqual(result1["volume"], 1100000)
        
        # Second call should hit cache (same cache key)
        result2 = get_cached_price_data("AAPL")
        self.assertEqual(result1, result2)
        
        # Verify market service was only called once (cache hit)
        self.assertEqual(mock_service.fetch_history.call_count, 1)

    @patch('utils.cache._get_market_service')
    def test_cached_price_history(self, mock_get_service):
        """Test that price history is cached correctly."""
        # Mock market service
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service
        
        # Mock historical data
        mock_history = pd.DataFrame({
            'date': ['2024-01-01', '2024-01-02', '2024-01-03'],
            'close': [100.0, 102.0, 101.0],
            'volume': [1000000, 1100000, 950000]
        })
        mock_service.fetch_history.return_value = mock_history
        
        # First call should miss cache
        result1 = get_cached_price_history("AAPL", months=3)
        self.assertIsNotNone(result1)
        self.assertEqual(len(result1), 3)
        
        # Second call should hit cache
        result2 = get_cached_price_history("AAPL", months=3)
        pd.testing.assert_frame_equal(result1, result2)
        
        # Verify market service was only called once
        self.assertEqual(mock_service.fetch_history.call_count, 1)

    @patch('utils.cache._get_market_service')
    def test_cache_ttl_behavior(self, mock_get_service):
        """Test that cache respects TTL settings."""
        # Mock market service
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service
        
        # Mock different data for each call
        mock_history1 = pd.DataFrame({
            'date': ['2024-01-01'], 'close': [100.0], 'volume': [1000000]
        })
        mock_history2 = pd.DataFrame({
            'date': ['2024-01-01'], 'close': [105.0], 'volume': [1200000]
        })
        mock_service.fetch_history.side_effect = [mock_history1, mock_history2]
        
        # First call with 1-minute TTL
        result1 = get_cached_price_data("AAPL", ttl_minutes=1)
        self.assertEqual(result1["close"], 100.0)
        
        # Mock time advancement (simulate TTL expiry)
        with patch('time.time', return_value=time.time() + 120):  # 2 minutes later
            result2 = get_cached_price_data("AAPL", ttl_minutes=1)
            self.assertEqual(result2["close"], 105.0)  # Should be new data
        
        # Verify both calls went to market service (cache expired)
        self.assertEqual(mock_service.fetch_history.call_count, 2)

    @patch('utils.cache._get_market_service')
    def test_warm_cache_for_symbols(self, mock_get_service):
        """Test cache warming functionality."""
        # Mock market service
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service
        
        # Mock data for different symbols
        def mock_fetch_history(symbol, months):
            if symbol == "^GSPC":
                return pd.DataFrame({'date': ['2024-01-01'], 'close': [4500.0], 'volume': [1000000]})
            elif symbol == "^DJI":
                return pd.DataFrame({'date': ['2024-01-01'], 'close': [35000.0], 'volume': [800000]})
            return pd.DataFrame()  # Empty for other symbols
        
        mock_service.fetch_history.side_effect = mock_fetch_history
        
        # Warm cache for test symbols
        test_symbols = ["^GSPC", "^DJI", "INVALID"]
        results = warm_cache_for_symbols(test_symbols)
        
        # Verify results
        self.assertTrue(results["^GSPC"])
        self.assertTrue(results["^DJI"])
        self.assertFalse(results["INVALID"])
        
        # Verify cache was populated
        cached_gspc = get_cached_price_data("^GSPC")
        self.assertEqual(cached_gspc["close"], 4500.0)

    def test_cache_stats(self):
        """Test cache statistics functionality."""
        # Initially empty cache
        stats = get_cache_stats()
        self.assertEqual(stats["price_cache"]["hits"], 0)
        self.assertEqual(stats["price_cache"]["misses"], 0)
        self.assertEqual(stats["history_cache"]["hits"], 0)
        self.assertEqual(stats["history_cache"]["misses"], 0)

    def test_empty_symbol_handling(self):
        """Test handling of empty or invalid symbols."""
        # Empty symbol
        result = get_cached_price_data("")
        self.assertIsNone(result["close"])
        
        # None symbol
        result = get_cached_price_data(None)
        self.assertIsNone(result["close"])
        
        # Empty history
        history = get_cached_price_history("")
        self.assertIsNone(history)

    def test_common_symbols_defined(self):
        """Test that common symbols for warming are defined."""
        self.assertIsInstance(COMMON_SYMBOLS, list)
        self.assertGreater(len(COMMON_SYMBOLS), 0)
        self.assertIn("^GSPC", COMMON_SYMBOLS)  # S&P 500 should be included


if __name__ == '__main__':
    unittest.main()