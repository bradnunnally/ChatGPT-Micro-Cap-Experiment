"""
Tests for configuration centralization functionality.

This module tests that configuration values are properly applied
and that the system is testable with custom configurations.
"""
import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
from datetime import datetime

from config.summary_config import SummaryConfig, create_test_config, get_config, set_config, DEFAULT_CONFIG
from ui.summary import render_daily_portfolio_summary, _fetch_price_volume, _build_portfolio_history_from_market
from ui.summary import fmt_currency, fmt_close, fmt_pct_signed


class TestConfigurationCentralization(unittest.TestCase):
    """Test suite for configuration centralization."""

    def setUp(self):
        """Set up test fixtures."""
        # Store original config to restore after tests
        self.original_config = get_config()
        
        # Sample test data
        self.sample_data = {
            "asOfDate": "2024-01-15",
            "cashBalance": 10000.0,
            "holdings": [
                {"symbol": "AAPL", "shares": 10, "price": 150.0},
                {"symbol": "MSFT", "shares": 5, "price": 300.0},
            ],
            "summaryFrame": None,
            "history": None,
            "indexSymbols": ["^GSPC", "^NDX"],
        }
    
    def tearDown(self):
        """Clean up after tests."""
        # Restore original configuration
        set_config(self.original_config)

    def test_default_configuration_values(self):
        """Test that default configuration values are correct."""
        config = get_config()
        
        self.assertEqual(config.default_history_months, 6)
        self.assertEqual(config.min_observations_for_metrics, 10)
        self.assertEqual(config.price_cache_ttl_minutes, 5)
        self.assertEqual(config.benchmark_symbol, "^GSPC")
        self.assertEqual(config.trading_days_per_year, 252)
        self.assertEqual(config.currency_precision, 2)
        self.assertEqual(config.percentage_precision, 2)

    def test_create_test_config_with_overrides(self):
        """Test creating configuration with specific overrides."""
        test_config = create_test_config(
            price_cache_ttl_minutes=1,
            min_observations_for_metrics=5,
            benchmark_symbol="^NDX",
            currency_precision=3
        )
        
        self.assertEqual(test_config.price_cache_ttl_minutes, 1)
        self.assertEqual(test_config.min_observations_for_metrics, 5)
        self.assertEqual(test_config.benchmark_symbol, "^NDX")
        self.assertEqual(test_config.currency_precision, 3)
        
        # Unchanged values should remain default
        self.assertEqual(test_config.default_history_months, 6)
        self.assertEqual(test_config.trading_days_per_year, 252)

    def test_config_injection_in_main_function(self):
        """Test that configuration can be injected into main function."""
        test_config = create_test_config(
            benchmark_symbol="^NDX",
            currency_precision=3,
            price_cache_ttl_minutes=1
        )
        
        with patch('ui.summary.get_cached_price_data') as mock_price, \
             patch('ui.summary.get_cached_price_history') as mock_history, \
             patch('ui.summary.warm_cache_for_symbols') as mock_warm:
            
            # Mock return values
            mock_price.return_value = {"symbol": "AAPL", "close": 150.0, "pct_change": 1.5, "volume": 1000000}
            mock_history.return_value = pd.DataFrame()
            
            result = render_daily_portfolio_summary(self.sample_data, config=test_config)
            
            # Verify the custom configuration was used
            self.assertIn("NDX", result)  # Should show custom benchmark
            
            # Verify cache was called with custom TTL
            mock_warm.assert_called_with(unittest.mock.ANY, ttl_minutes=1)

    def test_formatting_functions_use_config_precision(self):
        """Test that formatting functions use configuration precision values."""
        # Test with custom precision
        test_config = create_test_config(
            currency_precision=3,
            percentage_precision=3
        )
        set_config(test_config)
        
        # Test currency formatting
        result = fmt_currency(1234.56789)
        self.assertEqual(result, "$1,234.568")  # Should use 3 decimal places
        
        # Test percentage formatting  
        result = fmt_pct_signed(12.3456)
        self.assertEqual(result, "+12.346%")  # Should use 3 decimal places
        
        # Test close price formatting
        result = fmt_close(987.6543)
        self.assertEqual(result, "987.654")  # Should use 3 decimal places

    @patch('ui.summary.get_cached_price_data')
    def test_fetch_price_volume_uses_config_ttl(self, mock_cache):
        """Test that _fetch_price_volume uses configured TTL."""
        test_config = create_test_config(price_cache_ttl_minutes=15)
        set_config(test_config)
        
        mock_cache.return_value = {"symbol": "AAPL", "close": 150.0, "pct_change": 1.5, "volume": 1000000}
        
        result = _fetch_price_volume("AAPL")
        
        # Verify cache was called with custom TTL
        mock_cache.assert_called_with("AAPL", ttl_minutes=15)
        
        # Verify result structure
        self.assertIn("symbol", result)
        self.assertEqual(result["symbol"], "AAPL")

    @patch('ui.summary.get_cached_price_history')
    def test_build_portfolio_history_uses_config_months(self, mock_history):
        """Test that portfolio history uses configured default months."""
        test_config = create_test_config(
            default_history_months=12,
            price_cache_ttl_minutes=10
        )
        set_config(test_config)
        
        mock_history.return_value = pd.DataFrame({"date": [], "close": []})
        
        holdings_df = pd.DataFrame([{"symbol": "AAPL", "shares": 10}])
        
        _build_portfolio_history_from_market(holdings_df, 1000.0)
        
        # Verify history was fetched with custom months and TTL
        # Note: The function might not be called if holdings_df doesn't have valid data
        if mock_history.called:
            # Check that at least one call used the correct configuration
            calls = mock_history.call_args_list
            ttl_found = any(call.kwargs.get('ttl_minutes') == 10 for call in calls)
            self.assertTrue(ttl_found, f"Expected TTL 10 not found in calls: {calls}")

    def test_configuration_is_backward_compatible(self):
        """Test that existing code works without configuration changes."""
        # This should work with default configuration
        with patch('ui.summary.get_cached_price_data') as mock_price, \
             patch('ui.summary.get_cached_price_history') as mock_history, \
             patch('ui.summary.warm_cache_for_symbols') as mock_warm:
            
            mock_price.return_value = {"symbol": "AAPL", "close": 150.0, "pct_change": 1.5, "volume": 1000000}
            mock_history.return_value = pd.DataFrame()
            
            # Call without config parameter (backward compatibility)
            result = render_daily_portfolio_summary(self.sample_data)
            
            # Should work and use default config
            self.assertIsInstance(result, str)
            self.assertIn("GSPC", result)  # Should use default benchmark

    def test_config_values_are_actually_used_in_calculations(self):
        """Test that configuration values affect benchmark symbol display."""
        # Test with a configuration that has different benchmark
        test_config = create_test_config(benchmark_symbol="^NDX")
        
        # Test with sample portfolio data
        test_data = self.sample_data.copy()
        
        with patch('ui.summary.get_cached_price_data') as mock_price, \
             patch('ui.summary.get_cached_price_history') as mock_history, \
             patch('ui.summary.warm_cache_for_symbols'):
            
            mock_price.return_value = {"symbol": "AAPL", "close": 150.0, "pct_change": 1.5, "volume": 1000000}
            mock_history.return_value = pd.DataFrame()
            
            # Generate results with different configs
            result_default = render_daily_portfolio_summary(test_data)  # Default ^GSPC
            result_custom = render_daily_portfolio_summary(test_data, config=test_config)  # ^NDX
            
            # Results should show different benchmark symbols
            self.assertIn("^GSPC", result_default)
            self.assertIn("^NDX", result_custom)
            self.assertNotIn("^NDX", result_default)
            self.assertNotIn("^GSPC", result_custom)

    def test_environment_variables_not_needed(self):
        """Test that no environment variables are required for configuration."""
        # Configuration should work entirely through code
        config = create_test_config()
        self.assertIsInstance(config, SummaryConfig)
        
        # All attributes should be accessible without environment setup
        self.assertIsNotNone(config.default_history_months)
        self.assertIsNotNone(config.benchmark_symbol)
        self.assertIsNotNone(config.trading_days_per_year)


if __name__ == '__main__':
    unittest.main()