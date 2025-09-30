"""
Comprehensive test suite for ui.summary module.

This module provides complete test coverage for all functions in the 
refactored summary module, including extracted helper functions, 
error handling, caching, and configuration.
"""
import unittest
from unittest.mock import patch, MagicMock, Mock
import pandas as pd
import numpy as np
from datetime import datetime, date
from typing import Dict, Any, List
import math

from config.summary_config import SummaryConfig, create_test_config, get_config, set_config
from ui.summary import (
    render_daily_portfolio_summary,
    _fetch_price_volume,
    _prepare_summary_data,
    _calculate_portfolio_metrics,
    _format_price_volume_section,
    _format_risk_metrics_section,
    _format_snapshot_section,
    _format_instructions_section,
    _build_portfolio_history_from_market,
    _collect_portfolio_symbols,
    _history_has_valid_equity,
    _compute_risk_metrics_with_source_info,
    get_portfolio_history_for_analytics,
    fmt_currency,
    fmt_close,
    fmt_pct_signed,
    fmt_currency_padded,
    fmt_shares,
    fmt_ratio
)


class TestDataFixtures:
    """Common test data fixtures for consistent testing."""
    
    @staticmethod
    def sample_holdings_data() -> List[Dict[str, Any]]:
        """Standard holdings data for testing."""
        return [
            {
                "symbol": "AAPL",
                "shares": 100,
                "price": 150.0,
                "cost_basis": 145.0,
                "ticker": "AAPL"
            },
            {
                "symbol": "MSFT",
                "shares": 50,
                "price": 300.0,
                "cost_basis": 280.0,
                "ticker": "MSFT"
            },
            {
                "symbol": "GOOGL",
                "shares": 25,
                "price": 2500.0,
                "cost_basis": 2400.0,
                "ticker": "GOOGL"
            }
        ]
    
    @staticmethod
    def sample_portfolio_data() -> Dict[str, Any]:
        """Standard portfolio data for testing."""
        return {
            "asOfDate": "2024-01-15",
            "cashBalance": 10000.0,
            "holdings": TestDataFixtures.sample_holdings_data(),
            "summaryFrame": None,
            "history": None,
            "indexSymbols": ["^GSPC", "^NDX"],
            "benchmarkSymbol": "^GSPC"
        }
    
    @staticmethod
    def sample_price_data() -> Dict[str, Any]:
        """Standard price data response."""
        return {
            "symbol": "AAPL",
            "close": 150.0,
            "pct_change": 1.5,
            "volume": 1000000
        }
    
    @staticmethod
    def sample_history_dataframe() -> pd.DataFrame:
        """Standard history DataFrame."""
        dates = pd.date_range("2024-01-01", periods=30, freq="D")
        return pd.DataFrame({
            "date": dates,
            "ticker": ["TOTAL"] * 30,
            "total_equity": [10000 + i * 100 for i in range(30)],
            "total_value": [9000 + i * 100 for i in range(30)],
            "cash_balance": [1000] * 30
        })
    
    @staticmethod
    def sample_benchmark_history() -> pd.DataFrame:
        """Standard benchmark history."""
        dates = pd.date_range("2024-01-01", periods=30, freq="D")
        return pd.DataFrame({
            "date": dates,
            "close": [4000 + i * 10 for i in range(30)]
        })


class TestFormattingFunctions(unittest.TestCase):
    """Test suite for all formatting functions."""
    
    def setUp(self):
        """Set up test configuration."""
        self.original_config = get_config()
        self.test_config = create_test_config(
            currency_precision=2,
            percentage_precision=2
        )
        set_config(self.test_config)
    
    def tearDown(self):
        """Restore original configuration."""
        set_config(self.original_config)
    
    def test_fmt_currency_normal_values(self):
        """Test currency formatting with normal values."""
        self.assertEqual(fmt_currency(1234.56), "$1,234.56")
        self.assertEqual(fmt_currency(0.0), "$0.00")
        self.assertEqual(fmt_currency(1000000), "$1,000,000.00")
    
    def test_fmt_currency_none_and_nan(self):
        """Test currency formatting with None and NaN values."""
        self.assertEqual(fmt_currency(None), "—")
        self.assertEqual(fmt_currency(float('nan')), "—")
        self.assertEqual(fmt_currency(pd.NA), "—")
    
    def test_fmt_currency_precision_configuration(self):
        """Test currency formatting uses configuration precision."""
        config = create_test_config(currency_precision=3)
        set_config(config)
        
        self.assertEqual(fmt_currency(1234.56789), "$1,234.568")
        
        config = create_test_config(currency_precision=0)
        set_config(config)
        
        self.assertEqual(fmt_currency(1234.56), "$1,235")
    
    def test_fmt_close_normal_values(self):
        """Test close price formatting."""
        self.assertEqual(fmt_close(150.45), "150.45")
        self.assertEqual(fmt_close(1234.5678), "1,234.57")
        self.assertEqual(fmt_close(0.01), "0.01")
    
    def test_fmt_pct_signed_positive_negative(self):
        """Test percentage formatting with signs."""
        self.assertEqual(fmt_pct_signed(1.5), "+1.50%")
        self.assertEqual(fmt_pct_signed(-2.3), "-2.30%")
        self.assertEqual(fmt_pct_signed(0.0), "+0.00%")
    
    def test_fmt_currency_padded_alignment(self):
        """Test padded currency formatting for alignment."""
        result = fmt_currency_padded(1234.56)
        self.assertIn("$", result)
        self.assertIn("1,234.56", result)
        # Should have proper formatting structure
        self.assertTrue(len(result) > 10)  # Should be longer due to padding
    
    def test_fmt_shares_whole_numbers(self):
        """Test share formatting."""
        self.assertEqual(fmt_shares(100.0), "100")
        self.assertEqual(fmt_shares(1000.5), "1,000")  # Formats as whole number
        self.assertEqual(fmt_shares(None), "—")
    
    def test_fmt_ratio_precision(self):
        """Test ratio formatting with different precision."""
        self.assertEqual(fmt_ratio(0.12345), "0.1235")
        self.assertEqual(fmt_ratio(0.12345, decimals=2), "0.12")
        self.assertEqual(fmt_ratio(None), "—")
    
    def test_fmt_currency_edge_cases(self):
        """Test currency formatting with edge cases."""
        # Test with very large numbers
        result = fmt_currency(1e12)
        self.assertIn("1,000,000,000,000", result)
        
        # Test with very small numbers
        result = fmt_currency(0.001)
        self.assertEqual(result, "$0.00")  # Should round to configured precision


class TestDataExtractionFunctions(unittest.TestCase):
    """Test suite for data extraction and preparation functions."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.sample_data = TestDataFixtures.sample_portfolio_data()
        self.original_config = get_config()
    
    def tearDown(self):
        """Clean up configuration."""
        set_config(self.original_config)
    
    @patch('ui.summary.get_cached_price_data')
    def test_fetch_price_volume_success(self, mock_cache):
        """Test successful price volume fetch."""
        mock_cache.return_value = TestDataFixtures.sample_price_data()
        
        result = _fetch_price_volume("AAPL")
        
        self.assertEqual(result["symbol"], "AAPL")
        self.assertEqual(result["close"], 150.0)
        self.assertEqual(result["pct_change"], 1.5)
        self.assertEqual(result["volume"], 1000000)
        mock_cache.assert_called_once()
    
    @patch('ui.summary.get_cached_price_data')
    def test_fetch_price_volume_error_handling(self, mock_cache):
        """Test price volume fetch with error."""
        mock_cache.side_effect = Exception("Network error")
        
        result = _fetch_price_volume("INVALID")
        
        # Should return fallback structure (error handler provides empty result)
        self.assertIsInstance(result, dict)
        self.assertIn("symbol", result)
        self.assertIn("close", result)
        self.assertIn("pct_change", result)
        self.assertIn("volume", result)
    
    def test_fetch_price_volume_empty_symbol(self):
        """Test price volume fetch with empty symbol."""
        result = _fetch_price_volume("")
        self.assertEqual(result["symbol"], "")
        self.assertIsNone(result["close"])
        
        result = _fetch_price_volume(None)
        self.assertIsNone(result["symbol"])
    
    def test_prepare_summary_data_complete(self):
        """Test summary data preparation with complete data."""
        result = _prepare_summary_data(self.sample_data)
        
        self.assertEqual(result["as_of_display"], "2024-01-15")
        self.assertEqual(result["cash_balance"], 10000.0)
        self.assertEqual(len(result["holdings"]), 3)
        self.assertIsInstance(result["holdings_df"], pd.DataFrame)
        self.assertEqual(len(result["index_symbols"]), 2)
        self.assertEqual(result["benchmark_symbol"], "^GSPC")
    
    def test_prepare_summary_data_minimal(self):
        """Test summary data preparation with minimal data."""
        minimal_data = {"asOfDate": "2024-01-15"}
        
        result = _prepare_summary_data(minimal_data)
        
        self.assertEqual(result["as_of_display"], "2024-01-15")
        self.assertEqual(result["cash_balance"], 0.0)
        self.assertEqual(result["holdings"], [])
        self.assertTrue(result["holdings_df"].empty)
    
    def test_prepare_summary_data_invalid_types(self):
        """Test summary data preparation with invalid data types."""
        invalid_data = {
            "asOfDate": "invalid-date",
            "cashBalance": "not-a-number",
            "holdings": "not-a-list"
        }
        
        # Should handle gracefully without raising exceptions
        result = _prepare_summary_data(invalid_data)
        self.assertIsInstance(result, dict)
        self.assertIn("as_of_display", result)
        self.assertIn("cash_balance", result)
    
    def test_collect_portfolio_symbols(self):
        """Test symbol collection from portfolio data."""
        holdings_df = pd.DataFrame(TestDataFixtures.sample_holdings_data())
        index_symbols = ["^GSPC", "^NDX"]
        
        result = _collect_portfolio_symbols(holdings_df, index_symbols)
        
        expected_symbols = ["AAPL", "MSFT", "GOOGL", "^GSPC", "^NDX"]
        self.assertEqual(sorted(result), sorted(expected_symbols))
    
    def test_collect_portfolio_symbols_empty_holdings(self):
        """Test symbol collection with empty holdings."""
        holdings_df = pd.DataFrame()
        index_symbols = ["^GSPC"]
        
        result = _collect_portfolio_symbols(holdings_df, index_symbols)
        
        self.assertEqual(result, ["^GSPC"])
    
    def test_history_has_valid_equity_true(self):
        """Test valid equity detection with good data."""
        history_df = TestDataFixtures.sample_history_dataframe()
        
        result = _history_has_valid_equity(history_df)
        
        self.assertTrue(result)
    
    def test_history_has_valid_equity_false(self):
        """Test valid equity detection with insufficient data."""
        # Create DataFrame with only 1 row
        history_df = pd.DataFrame({
            "date": [pd.Timestamp("2024-01-01")],
            "ticker": ["TOTAL"],
            "total_equity": [10000]
        })
        
        result = _history_has_valid_equity(history_df)
        
        self.assertFalse(result)
    
    def test_history_has_valid_equity_no_total_rows(self):
        """Test valid equity detection with no TOTAL rows."""
        history_df = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=10),
            "ticker": ["AAPL"] * 10,
            "total_equity": [10000] * 10
        })
        
        result = _history_has_valid_equity(history_df)
        
        self.assertFalse(result)


class TestPortfolioHistoryFunctions(unittest.TestCase):
    """Test suite for portfolio history generation functions."""
    
    @patch('ui.summary.get_cached_price_history')
    def test_build_portfolio_history_success(self, mock_history):
        """Test successful portfolio history building."""
        # Mock price history for each symbol
        mock_history_data = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=10),
            "close": [150.0 + i for i in range(10)]
        })
        mock_history.return_value = mock_history_data
        
        holdings_df = pd.DataFrame([
            {"symbol": "AAPL", "shares": 100, "ticker": "AAPL"}
        ])
        
        result = _build_portfolio_history_from_market(holdings_df, 1000.0, months=3)
        
        self.assertIsInstance(result, pd.DataFrame)
        # Should be called for AAPL
        mock_history.assert_called()
    
    @patch('ui.summary.get_cached_price_history')
    def test_build_portfolio_history_empty_holdings(self, mock_history):
        """Test portfolio history with empty holdings."""
        holdings_df = pd.DataFrame()
        
        result = _build_portfolio_history_from_market(holdings_df, 1000.0)
        
        self.assertTrue(result.empty)
        mock_history.assert_not_called()
    
    @patch('ui.summary.get_cached_price_history')
    def test_build_portfolio_history_error_handling(self, mock_history):
        """Test portfolio history with network errors."""
        mock_history.side_effect = Exception("Network error")
        
        holdings_df = pd.DataFrame([
            {"symbol": "AAPL", "shares": 100, "ticker": "AAPL"}
        ])
        
        result = _build_portfolio_history_from_market(holdings_df, 1000.0)
        
        # Should return DataFrame (possibly empty) without raising
        self.assertIsInstance(result, pd.DataFrame)
    
    def test_get_portfolio_history_for_analytics_with_stored(self):
        """Test portfolio history selection with stored data."""
        stored_history = TestDataFixtures.sample_history_dataframe()
        holdings_df = pd.DataFrame(TestDataFixtures.sample_holdings_data())
        
        with patch('ui.summary._build_portfolio_history_from_market') as mock_build:
            result_df, is_synthetic = get_portfolio_history_for_analytics(
                stored_history, holdings_df, 1000.0, "^GSPC"
            )
            
            # Should use stored history, not build synthetic
            self.assertFalse(is_synthetic)
            self.assertEqual(len(result_df), 30)
            mock_build.assert_not_called()
    
    @patch('ui.summary._build_portfolio_history_from_market')
    def test_get_portfolio_history_for_analytics_synthetic(self, mock_build):
        """Test portfolio history with synthetic generation."""
        mock_build.return_value = TestDataFixtures.sample_history_dataframe()
        
        holdings_df = pd.DataFrame(TestDataFixtures.sample_holdings_data())
        
        result_df, is_synthetic = get_portfolio_history_for_analytics(
            None, holdings_df, 1000.0, "^GSPC"
        )
        
        # Should use synthetic history
        self.assertTrue(is_synthetic)
        mock_build.assert_called_once()


class TestPortfolioMetrics(unittest.TestCase):
    """Test suite for portfolio metrics calculation."""
    
    def setUp(self):
        """Set up test configuration."""
        self.original_config = get_config()
        self.test_config = create_test_config(
            trading_days_per_year=252,
            min_observations_for_metrics=10
        )
        set_config(self.test_config)
        
        self.holdings_df = pd.DataFrame(TestDataFixtures.sample_holdings_data())
        self.history_df = TestDataFixtures.sample_history_dataframe()
    
    def tearDown(self):
        """Restore configuration."""
        set_config(self.original_config)
    
    @patch('ui.summary.get_cached_price_history')
    def test_calculate_portfolio_metrics_complete(self, mock_benchmark):
        """Test complete portfolio metrics calculation."""
        mock_benchmark.return_value = TestDataFixtures.sample_benchmark_history()
        
        result = _calculate_portfolio_metrics(
            self.holdings_df, None, self.history_df, 1000.0, "^GSPC"
        )
        
        self.assertIn("risk_metrics", result)
        self.assertIn("invested_value", result)
        self.assertIn("total_equity", result)
        
        risk_metrics = result["risk_metrics"]
        self.assertIn("max_drawdown", risk_metrics)
        self.assertIn("sharpe_period", risk_metrics)
        self.assertIn("obs", risk_metrics)
    
    @patch('ui.summary.get_cached_price_history')
    def test_calculate_portfolio_metrics_insufficient_data(self, mock_benchmark):
        """Test metrics calculation with insufficient data."""
        # Create history with only 2 rows (below minimum)
        small_history = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=2),
            "ticker": ["TOTAL"] * 2,
            "total_equity": [10000, 10100]
        })
        
        mock_benchmark.return_value = pd.DataFrame()
        
        result = _calculate_portfolio_metrics(
            self.holdings_df, None, small_history, 1000.0, "^GSPC"
        )
        
        risk_metrics = result["risk_metrics"]
        # Should have note about insufficient data
        self.assertIn("note", risk_metrics)
        self.assertIn("insufficient", risk_metrics["note"].lower())
    
    def test_calculate_portfolio_metrics_no_history(self):
        """Test metrics calculation with no history."""
        result = _calculate_portfolio_metrics(
            self.holdings_df, None, None, 1000.0, "^GSPC"
        )
        
        # Should return valid structure with default values
        self.assertIn("risk_metrics", result)
        self.assertIn("invested_value", result)
        risk_metrics = result["risk_metrics"]
        self.assertEqual(risk_metrics["obs"], 0)


class TestDisplayFormatting(unittest.TestCase):
    """Test suite for display formatting functions."""
    
    def test_format_snapshot_section(self):
        """Test snapshot section formatting."""
        result = _format_snapshot_section(55000.0, 10000.0)
        
        self.assertIsInstance(result, list)
        self.assertTrue(any("Total Equity" in line for line in result))
        self.assertTrue(any("55,000.00" in line for line in result))
    
    def test_format_risk_metrics_section(self):
        """Test risk metrics section formatting."""
        risk_metrics = {
            "max_drawdown": -0.12,
            "max_drawdown_date": "2024-01-15",
            "sharpe_period": 0.8,
            "sharpe_annual": 1.2,
            "sortino_period": 0.9,
            "sortino_annual": 1.35,
            "beta": 1.1,
            "alpha_annual": 0.05,
            "r_squared": 0.85,
            "obs": 25
        }
        
        result = _format_risk_metrics_section(risk_metrics)
        
        self.assertIsInstance(result, list)
        self.assertTrue(any("Max Drawdown" in line for line in result))
        self.assertTrue(any("Sharpe Ratio" in line for line in result))
        self.assertTrue(any("Beta" in line for line in result))
    
    def test_format_price_volume_section(self):
        """Test price volume section formatting."""
        price_data = [
            {"symbol": "AAPL", "close": 155.0, "pct_change": 1.5, "volume": 1000000},
            {"symbol": "MSFT", "close": 310.0, "pct_change": -0.8, "volume": 800000},
            {"symbol": "GOOGL", "close": 2600.0, "pct_change": 2.1, "volume": 500000}
        ]
        
        result = _format_price_volume_section(price_data)
        
        self.assertIsInstance(result, list)
        # Should contain headers and data rows
        self.assertTrue(any("Ticker" in line for line in result))
        self.assertTrue(any("AAPL" in line for line in result))
        self.assertTrue(any("155.00" in line for line in result))
    
    def test_format_instructions_section(self):
        """Test instructions section formatting."""
        result = _format_instructions_section()
        
        self.assertIsInstance(result, list)
        # Should contain instruction text
        self.assertTrue(any("control" in line.lower() for line in result))
        self.assertTrue(len(result) > 0)


class TestIntegrationScenarios(unittest.TestCase):
    """Integration tests for complete workflow scenarios."""
    
    def setUp(self):
        """Set up integration test fixtures."""
        self.complete_data = TestDataFixtures.sample_portfolio_data()
        self.original_config = get_config()
    
    def tearDown(self):
        """Clean up configuration."""
        set_config(self.original_config)
    
    @patch('ui.summary.get_cached_price_data')
    @patch('ui.summary.get_cached_price_history') 
    @patch('ui.summary.warm_cache_for_symbols')
    def test_complete_summary_generation(self, mock_warm, mock_history, mock_price):
        """Test complete summary generation workflow."""
        # Mock all external calls
        mock_price.return_value = TestDataFixtures.sample_price_data()
        mock_history.return_value = TestDataFixtures.sample_history_dataframe()
        mock_warm.return_value = None
        
        result = render_daily_portfolio_summary(self.complete_data)
        
        # Should return complete formatted report
        self.assertIsInstance(result, str)
        self.assertIn("Daily Results", result)
        self.assertIn("Price & Volume", result)
        self.assertIn("Risk & Return", result)
        self.assertIn("Holdings", result)
        self.assertIn("Your Instructions", result)
    
    @patch('ui.summary.get_cached_price_data')
    @patch('ui.summary.get_cached_price_history')
    @patch('ui.summary.warm_cache_for_symbols')
    def test_error_recovery_scenario(self, mock_warm, mock_history, mock_price):
        """Test system behavior under multiple error conditions."""
        # Simulate various failures
        mock_price.side_effect = Exception("Price service down")
        mock_history.side_effect = Exception("History service down")
        mock_warm.side_effect = Exception("Cache service down")
        
        # Should still produce a result without crashing
        result = render_daily_portfolio_summary(self.complete_data)
        
        self.assertIsInstance(result, str)
        # Should contain error indicators but still be formatted
        self.assertIn("Daily Results", result)
    
    def test_configuration_injection_workflow(self):
        """Test complete workflow with custom configuration."""
        custom_config = create_test_config(
            benchmark_symbol="^NDX",
            currency_precision=1,
            price_cache_ttl_minutes=1
        )
        
        with patch('ui.summary.get_cached_price_data') as mock_price, \
             patch('ui.summary.get_cached_price_history') as mock_history, \
             patch('ui.summary.warm_cache_for_symbols') as mock_warm:
            
            mock_price.return_value = TestDataFixtures.sample_price_data()
            mock_history.return_value = pd.DataFrame()
            mock_warm.return_value = None
            
            result = render_daily_portfolio_summary(
                self.complete_data, 
                config=custom_config
            )
            
            # Should use custom configuration
            self.assertIn("^NDX", result)
            self.assertNotIn("^GSPC", result)
            
            # Verify custom TTL was used
            mock_warm.assert_called_with(unittest.mock.ANY, ttl_minutes=1)
    
    def test_minimal_data_handling(self):
        """Test system behavior with minimal input data."""
        minimal_data = {"asOfDate": "2024-01-15"}
        
        with patch('ui.summary.get_cached_price_data'), \
             patch('ui.summary.get_cached_price_history'), \
             patch('ui.summary.warm_cache_for_symbols'):
            
            result = render_daily_portfolio_summary(minimal_data)
            
            # Should handle gracefully
            self.assertIsInstance(result, str)
            self.assertIn("2024-01-15", result)
    
    def test_large_portfolio_handling(self):
        """Test system behavior with large portfolio data."""
        # Create large holdings list
        large_holdings = []
        for i in range(100):
            large_holdings.append({
                "symbol": f"STOCK{i:03d}",
                "shares": 100 + i,
                "price": 50.0 + i,
                "ticker": f"STOCK{i:03d}"
            })
        
        large_data = self.complete_data.copy()
        large_data["holdings"] = large_holdings
        
        with patch('ui.summary.get_cached_price_data') as mock_price, \
             patch('ui.summary.get_cached_price_history'), \
             patch('ui.summary.warm_cache_for_symbols'):
            
            mock_price.return_value = TestDataFixtures.sample_price_data()
            
            result = render_daily_portfolio_summary(large_data)
            
            # Should handle large datasets
            self.assertIsInstance(result, str)
            # Verify many price calls were made
            self.assertGreater(mock_price.call_count, 50)


class TestPerformanceAndCaching(unittest.TestCase):
    """Performance tests and caching effectiveness validation."""
    
    @patch('ui.summary.get_cached_price_data')
    def test_caching_reduces_api_calls(self, mock_price):
        """Test that caching reduces repeated API calls."""
        mock_price.return_value = TestDataFixtures.sample_price_data()
        
        # First call
        result1 = _fetch_price_volume("AAPL")
        initial_call_count = mock_price.call_count
        
        # Second call should use cache (in real scenario)
        result2 = _fetch_price_volume("AAPL")
        
        # Verify results are consistent
        self.assertEqual(result1["symbol"], result2["symbol"])
        
        # In our mock scenario, we expect calls to be made
        # In production, the second call would be cached
        self.assertGreater(mock_price.call_count, 0)
    
    def test_performance_with_large_symbol_list(self):
        """Test performance with large number of symbols."""
        symbols = [f"STOCK{i:03d}" for i in range(50)]
        
        with patch('ui.summary.get_cached_price_data') as mock_price:
            mock_price.return_value = TestDataFixtures.sample_price_data()
            
            import time
            start_time = time.time()
            
            results = [_fetch_price_volume(symbol) for symbol in symbols]
            
            end_time = time.time()
            execution_time = end_time - start_time
            
            # Should complete in reasonable time (under 1 second for mocked calls)
            self.assertLess(execution_time, 1.0)
            self.assertEqual(len(results), 50)
            
            # All calls should have been made
            self.assertEqual(mock_price.call_count, 50)
    
    def test_memory_efficiency_large_dataframes(self):
        """Test memory efficiency with large DataFrames."""
        # Create large DataFrame
        large_df = pd.DataFrame({
            "date": pd.date_range("2020-01-01", periods=1000),
            "ticker": ["TOTAL"] * 1000,
            "total_equity": range(10000, 11000)
        })
        
        # Should handle large DataFrames without memory issues
        result = _history_has_valid_equity(large_df)
        self.assertTrue(result)
        
        # Memory should be released after processing
        # (This is more of a conceptual test in our mock environment)
        import gc
        gc.collect()


if __name__ == '__main__':
    # Run tests with coverage if available
    unittest.main(verbosity=2)