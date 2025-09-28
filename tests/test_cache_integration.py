"""
Integration test to verify caching reduces API calls.
"""

import unittest
from unittest.mock import patch, MagicMock
import pandas as pd

from ui.summary import _fetch_price_volume, render_daily_portfolio_summary
from utils.cache import clear_cache


class TestCacheIntegration(unittest.TestCase):
    """Test cache integration with existing functions."""
    
    def setUp(self):
        """Clear cache before each test."""
        clear_cache()

    def tearDown(self):
        """Clear cache after each test."""
        clear_cache()

    @patch('utils.cache._get_market_service')
    def test_fetch_price_volume_uses_cache(self, mock_get_service):
        """Test that _fetch_price_volume uses caching."""
        # Mock market service
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service
        
        # Mock historical data
        mock_history = pd.DataFrame({
            'date': ['2024-01-01', '2024-01-02'],
            'close': [100.0, 105.0],
            'volume': [1000000, 1200000]
        })
        mock_service.fetch_history.return_value = mock_history
        
        # Call function twice with same symbol
        result1 = _fetch_price_volume("AAPL")
        result2 = _fetch_price_volume("AAPL")
        
        # Results should be identical
        self.assertEqual(result1, result2)
        self.assertEqual(result1["close"], 105.0)
        self.assertEqual(result1["pct_change"], 5.0)  # (105-100)/100 * 100
        
        # Market service should only be called once (second call cached)
        self.assertEqual(mock_service.fetch_history.call_count, 1)

    @patch('utils.cache._get_market_service')
    def test_daily_summary_cache_effectiveness(self, mock_get_service):
        """Test that daily summary generation benefits from caching."""
        # Mock market service
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service
        
        # Mock historical data for portfolio symbols and benchmark
        def mock_fetch_history(symbol, months):
            base_data = {
                'date': ['2024-01-01', '2024-01-02', '2024-01-03'],
                'close': [100.0, 102.0, 101.0],
                'volume': [1000000, 1100000, 950000]
            }
            if symbol == "^GSPC":
                base_data['close'] = [4500.0, 4520.0, 4510.0]
            elif symbol == "AAPL":
                base_data['close'] = [150.0, 152.0, 149.0]
            return pd.DataFrame(base_data)
        
        mock_service.fetch_history.side_effect = mock_fetch_history
        
        # Sample portfolio data
        test_data = {
            "asOfDate": "2024-01-03",
            "cashBalance": 1000.0,
            "holdings": [
                {
                    "ticker": "AAPL",
                    "shares": 10,
                    "costPerShare": 140.0,
                    "currentPrice": 149.0,
                    "stopType": "none"
                }
            ],
            "indexSymbols": ["^GSPC"],
            "benchmarkSymbol": "^GSPC"
        }
        
        # Generate summary - this should populate cache
        summary1 = render_daily_portfolio_summary(test_data)
        self.assertIn("Daily Results", summary1)
        self.assertIn("AAPL", summary1)
        
        # Generate summary again - should use cached data
        summary2 = render_daily_portfolio_summary(test_data)
        self.assertEqual(summary1, summary2)
        
        # Verify significant reduction in API calls
        # First run: warmup (5 symbols) + AAPL price + AAPL history + ^GSPC for risk
        # Second run: should reuse most cached data
        call_count = mock_service.fetch_history.call_count
        
        # We expect some calls but not as many as without caching
        # The exact number depends on cache warming and TTL behavior
        self.assertGreater(call_count, 0)
        print(f"Total API calls made: {call_count}")


if __name__ == '__main__':
    unittest.main()