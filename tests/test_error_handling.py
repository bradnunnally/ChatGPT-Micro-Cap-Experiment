"""
Tests for standardized error handling functionality.
"""

import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
import logging

from utils.error_handling import (
    handle_summary_errors,
    handle_data_errors,
    safe_numeric_conversion,
    create_empty_result,
    validate_input_data
)
from ui.summary import (
    _fetch_price_volume,
    _prepare_summary_data,
    _calculate_portfolio_metrics,
    render_daily_portfolio_summary
)


class TestErrorHandling(unittest.TestCase):
    """Test standardized error handling functionality."""
    
    def setUp(self):
        """Set up test logging."""
        logging.basicConfig(level=logging.DEBUG)

    def test_handle_summary_errors_decorator(self):
        """Test that the error handling decorator works correctly."""
        
        @handle_summary_errors(fallback_value="fallback")
        def test_function(should_fail=False):
            if should_fail:
                raise ValueError("Test error")
            return "success"
        
        # Test success case
        result = test_function(should_fail=False)
        self.assertEqual(result, "success")
        
        # Test error case
        with self.assertLogs(level='WARNING') as cm:
            result = test_function(should_fail=True)
            self.assertEqual(result, "fallback")
            self.assertIn("Error in test_function: Test error", cm.output[0])

    def test_safe_numeric_conversion(self):
        """Test safe numeric conversion utility."""
        # Valid conversions
        self.assertEqual(safe_numeric_conversion("123.45"), 123.45)
        self.assertEqual(safe_numeric_conversion(456), 456.0)
        self.assertEqual(safe_numeric_conversion("0"), 0.0)
        
        # Invalid conversions use fallback
        self.assertEqual(safe_numeric_conversion("invalid"), 0.0)
        self.assertEqual(safe_numeric_conversion(None), 0.0)
        self.assertEqual(safe_numeric_conversion(pd.NA), 0.0)
        
        # Custom fallback
        self.assertEqual(safe_numeric_conversion("invalid", fallback=99.9), 99.9)

    def test_create_empty_result(self):
        """Test empty result creation for different types."""
        # Test dict result
        dict_result = create_empty_result('dict')
        self.assertEqual(dict_result, {})
        
        # Test list result
        list_result = create_empty_result('list')
        self.assertEqual(list_result, [])
        
        # Test price_data result
        price_result = create_empty_result('price_data')
        expected = {"symbol": None, "close": None, "pct_change": None, "volume": None}
        self.assertEqual(price_result, expected)
        
        # Test risk_metrics result
        risk_result = create_empty_result('risk_metrics')
        self.assertIsInstance(risk_result, dict)
        self.assertIn("max_drawdown", risk_result)
        self.assertIn("note", risk_result)
        self.assertEqual(risk_result["note"], "Error occurred during calculation")

    def test_validate_input_data(self):
        """Test input data validation."""
        # Valid data
        valid_data = {"asOfDate": "2024-01-01", "cashBalance": 1000.0}
        self.assertTrue(validate_input_data(valid_data, ["asOfDate"]))
        self.assertTrue(validate_input_data(valid_data, ["asOfDate", "cashBalance"]))
        
        # Missing required fields
        with self.assertLogs(level='WARNING') as cm:
            result = validate_input_data(valid_data, ["asOfDate", "missingField"])
            self.assertFalse(result)
            self.assertIn("Missing required fields", cm.output[0])

    @patch('utils.cache.get_cached_price_data')
    def test_fetch_price_volume_error_handling(self, mock_cache):
        """Test that _fetch_price_volume handles errors correctly."""
        # Mock cache to raise an error
        mock_cache.side_effect = Exception("Cache error")
        
        # Function should handle the error gracefully
        result = _fetch_price_volume("TEST")
        
        # Function preserves symbol but returns None for other values on error
        self.assertEqual(result['symbol'], "TEST")
        self.assertIsNone(result['close'])
        self.assertIsNone(result['pct_change'])
        self.assertIsNone(result['volume'])
        
        # Test that the function returns a valid structure even on error
        self.assertIsInstance(result, dict)
        self.assertIn('symbol', result)
        self.assertIn('close', result)
        self.assertIn('pct_change', result)
        self.assertIn('volume', result)

    def test_prepare_summary_data_error_handling(self):
        """Test that _prepare_summary_data handles invalid input."""
        # Test with data that will cause internal processing errors
        invalid_data = {
            "asOfDate": "invalid-date-format",
            "cashBalance": "not-a-number",
            "holdings": "not-a-list"
        }
        
        with self.assertLogs(level='WARNING') as cm:
            result = _prepare_summary_data(invalid_data)
            
            # Function handles errors gracefully and returns valid structure
            self.assertIsInstance(result, dict)
            self.assertIn('as_of_display', result)
            self.assertIn('cash_balance', result)
            self.assertIn('holdings_df', result)
            
            # Should log the error
            self.assertTrue(any("Error in _prepare_summary_data" in log for log in cm.output))

    @patch('ui.summary.get_portfolio_history_for_analytics')
    def test_calculate_portfolio_metrics_error_handling(self, mock_analytics):
        """Test portfolio metrics calculation error handling."""
        # Mock to raise an error
        mock_analytics.side_effect = Exception("Analytics error")
        
        with self.assertLogs(level='WARNING') as cm:
            result = _calculate_portfolio_metrics(
                pd.DataFrame(), None, None, 1000.0, "^GSPC"
            )
            
            # Should return fallback value
            expected_fallback = create_empty_result('portfolio_metrics')
            self.assertEqual(result, expected_fallback)
            
            # Should log the error
            self.assertTrue(any("Error in _calculate_portfolio_metrics" in log for log in cm.output))

    def test_render_daily_summary_input_validation(self):
        """Test that main function validates input properly."""
        # Test with missing required fields
        invalid_data = {"cashBalance": 1000.0}  # Missing asOfDate
        
        with self.assertLogs(level='WARNING') as cm:
            result = render_daily_portfolio_summary(invalid_data)
            
            # Should still generate a summary (with warnings)
            self.assertIsInstance(result, str)
            self.assertIn("Daily Results", result)
            
            # Should log validation warning
            self.assertTrue(any("Missing required input data" in log for log in cm.output))

    def test_error_handling_preserves_function_signatures(self):
        """Test that error handling decorators preserve function signatures."""
        # Original function
        def original_func(arg1: str, arg2: int = 10, *args, **kwargs) -> str:
            return f"{arg1}-{arg2}"
        
        # Decorated function
        @handle_summary_errors(fallback_value="error")
        def decorated_func(arg1: str, arg2: int = 10, *args, **kwargs) -> str:
            return f"{arg1}-{arg2}"
        
        # Test that both work the same way
        self.assertEqual(original_func("test"), decorated_func("test"))
        self.assertEqual(original_func("test", 20), decorated_func("test", 20))
        
        # Test that function name is preserved
        self.assertEqual(decorated_func.__name__, "decorated_func")

    def test_logging_levels(self):
        """Test that different error handlers use appropriate logging levels."""
        
        @handle_data_errors(fallback_value=None, log_level="debug")
        def debug_function():
            raise ValueError("Debug level error")
        
        @handle_data_errors(fallback_value=None, log_level="error") 
        def error_function():
            raise ValueError("Error level error")
        
        # Test debug level logging
        with self.assertLogs(level='DEBUG') as cm:
            debug_function()
            self.assertTrue(any("DEBUG" in log for log in cm.output))
        
        # Test error level logging
        with self.assertLogs(level='ERROR') as cm:
            error_function()
            self.assertTrue(any("ERROR" in log for log in cm.output))


if __name__ == '__main__':
    unittest.main()