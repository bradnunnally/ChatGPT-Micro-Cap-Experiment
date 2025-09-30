"""
Targeted tests for achieving >95% coverage on ui.summary module.

This focuses on testing the specific functions and edge cases 
that haven't been covered by the comprehensive tests.
"""
import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
import numpy as np
from datetime import datetime

from config.summary_config import create_test_config, set_config, get_config
from ui.summary import (
    render_daily_portfolio_summary,
    build_daily_summary,
    _compute_risk_metrics_with_source_info,
    _build_portfolio_history_from_market,
    get_portfolio_history_for_analytics
)


class TestRemainingCoverage(unittest.TestCase):
    """Tests targeting remaining uncovered code paths."""
    
    def setUp(self):
        """Set up test configuration."""
        self.original_config = get_config()
        self.test_config = create_test_config()
        set_config(self.test_config)
    
    def tearDown(self):
        """Restore configuration."""
        set_config(self.original_config)
    
    def test_build_daily_summary_empty_data(self):
        """Test build_daily_summary with empty data."""
        empty_df = pd.DataFrame()
        
        result = build_daily_summary(empty_df)
        
        self.assertIsInstance(result, str)
        self.assertIn("No portfolio data", result)
    
    def test_build_daily_summary_missing_columns(self):
        """Test build_daily_summary with missing required columns."""
        df = pd.DataFrame({
            "date": ["2024-01-01"],
            "some_column": [123]
        })
        
        result = build_daily_summary(df)
        
        self.assertIsInstance(result, str)
    
    def test_build_daily_summary_valid_data(self):
        """Test build_daily_summary with valid data."""
        df = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=5),
            "ticker": ["AAPL"] * 5,
            "total_equity": [10000, 10100, 10200, 10150, 10300],
            "shares": [100] * 5,
            "close": [100, 101, 102, 101.5, 103]
        })
        
        result = build_daily_summary(df)
        
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 100)
    
    @patch('ui.summary.get_cached_price_history')
    def test_compute_risk_metrics_complete_flow(self, mock_history):
        """Test complete risk metrics computation."""
        # Create portfolio data with sufficient observations
        portfolio_history = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=30),
            "total_equity": [10000 + i * 100 + np.random.normal(0, 50) for i in range(30)]
        })
        
        # Create benchmark data
        benchmark_history = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=30),
            "close": [4000 + i * 10 + np.random.normal(0, 20) for i in range(30)]
        })
        
        mock_history.return_value = benchmark_history
        
        result = _compute_risk_metrics_with_source_info(
            portfolio_history, "^GSPC", 6
        )
        
        self.assertIsInstance(result, dict)
        self.assertIn("max_drawdown", result)
        self.assertIn("sharpe_period", result)
        self.assertIn("beta", result)
        self.assertIn("obs", result)
        
        # Should have meaningful observations
        self.assertGreater(result["obs"], 10)
    
    @patch('ui.summary.get_cached_price_history')
    def test_compute_risk_metrics_insufficient_data(self, mock_history):
        """Test risk metrics with insufficient data."""
        # Portfolio with too few observations
        portfolio_history = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=3),
            "total_equity": [10000, 10100, 10200]
        })
        
        mock_history.return_value = pd.DataFrame()
        
        result = _compute_risk_metrics_with_source_info(
            portfolio_history, "^GSPC", 6
        )
        
        self.assertIsInstance(result, dict)
        self.assertIn("note", result)
        self.assertIn("insufficient", result["note"].lower())
    
    @patch('ui.summary.get_cached_price_history')
    def test_compute_risk_metrics_no_benchmark(self, mock_history):
        """Test risk metrics when benchmark fetch fails."""
        portfolio_history = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=20),
            "total_equity": [10000 + i * 100 for i in range(20)]
        })
        
        mock_history.side_effect = Exception("Benchmark fetch failed")
        
        result = _compute_risk_metrics_with_source_info(
            portfolio_history, "^GSPC", 6
        )
        
        self.assertIsInstance(result, dict)
        # Should still calculate basic metrics without benchmark
        self.assertIn("max_drawdown", result)
        self.assertIn("obs", result)
    
    @patch('ui.summary.get_cached_price_history')
    def test_build_portfolio_history_various_holdings(self, mock_history):
        """Test portfolio history building with various holding scenarios."""
        # Mock different price histories for different symbols
        def mock_price_history(symbol, **kwargs):
            if symbol == "AAPL":
                return pd.DataFrame({
                    "date": pd.date_range("2024-01-01", periods=10),
                    "close": [150 + i for i in range(10)]
                })
            elif symbol == "MSFT":
                return pd.DataFrame({
                    "date": pd.date_range("2024-01-01", periods=10),
                    "close": [300 + i * 2 for i in range(10)]
                })
            else:
                return pd.DataFrame()
        
        mock_history.side_effect = mock_price_history
        
        holdings_df = pd.DataFrame([
            {"symbol": "AAPL", "shares": 100, "ticker": "AAPL"},
            {"symbol": "MSFT", "shares": 50, "ticker": "MSFT"},
            {"symbol": "INVALID", "shares": 10, "ticker": "INVALID"}  # This should fail
        ])
        
        result = _build_portfolio_history_from_market(holdings_df, 1000.0, months=3)
        
        self.assertIsInstance(result, pd.DataFrame)
        # Should handle mixed success/failure scenarios
    
    @patch('ui.summary.get_cached_price_history')
    def test_build_portfolio_history_invalid_shares(self, mock_history):
        """Test portfolio history with invalid share amounts."""
        mock_history.return_value = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=5),
            "close": [100, 101, 102, 103, 104]
        })
        
        holdings_df = pd.DataFrame([
            {"symbol": "AAPL", "shares": None, "ticker": "AAPL"},  # Invalid shares
            {"symbol": "MSFT", "shares": 0, "ticker": "MSFT"},    # Zero shares
            {"symbol": "GOOGL", "shares": "invalid", "ticker": "GOOGL"}  # Non-numeric shares
        ])
        
        result = _build_portfolio_history_from_market(holdings_df, 1000.0)
        
        self.assertIsInstance(result, pd.DataFrame)
        # Should handle invalid data gracefully
    
    def test_get_portfolio_history_stored_insufficient(self):
        """Test portfolio history selection with insufficient stored data."""
        # Create stored history with insufficient TOTAL rows
        insufficient_history = pd.DataFrame({
            "date": [pd.Timestamp("2024-01-01")],
            "ticker": ["TOTAL"],
            "total_equity": [10000]
        })
        
        holdings_df = pd.DataFrame([{"symbol": "AAPL", "shares": 100}])
        
        with patch('ui.summary._build_portfolio_history_from_market') as mock_build:
            mock_build.return_value = pd.DataFrame({
                "date": pd.date_range("2024-01-01", periods=10),
                "total_equity": [10000 + i * 100 for i in range(10)]
            })
            
            result_df, is_synthetic = get_portfolio_history_for_analytics(
                insufficient_history, holdings_df, 1000.0, "^GSPC"
            )
            
            # Should fall back to synthetic
            self.assertTrue(is_synthetic)
            mock_build.assert_called_once()
    
    def test_get_portfolio_history_no_valid_equity(self):
        """Test portfolio history with invalid equity data."""
        # Create history without proper total_equity
        invalid_history = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=10),
            "ticker": ["AAPL"] * 10,  # No TOTAL ticker
            "price": [100 + i for i in range(10)]
        })
        
        holdings_df = pd.DataFrame([{"symbol": "AAPL", "shares": 100}])
        
        with patch('ui.summary._build_portfolio_history_from_market') as mock_build:
            mock_build.return_value = pd.DataFrame()
            
            result_df, is_synthetic = get_portfolio_history_for_analytics(
                invalid_history, holdings_df, 1000.0, "^GSPC"
            )
            
            # Should attempt synthetic generation
            mock_build.assert_called_once()
    
    @patch('ui.summary.get_cached_price_data')
    @patch('ui.summary.get_cached_price_history')
    @patch('ui.summary.warm_cache_for_symbols')
    def test_render_daily_summary_error_paths(self, mock_warm, mock_history, mock_price):
        """Test error handling paths in render_daily_portfolio_summary."""
        # Test various error scenarios
        error_scenarios = [
            # Price data errors
            (lambda: setattr(mock_price, 'side_effect', Exception("Price error")), "price"),
            # History data errors
            (lambda: setattr(mock_history, 'side_effect', Exception("History error")), "history"),
            # Cache warming errors
            (lambda: setattr(mock_warm, 'side_effect', Exception("Cache error")), "cache")
        ]
        
        sample_data = {
            "asOfDate": "2024-01-15",
            "cashBalance": 1000.0,
            "holdings": [{"symbol": "AAPL", "shares": 10}]
        }
        
        for error_setup, error_type in error_scenarios:
            # Reset mocks
            mock_price.reset_mock()
            mock_history.reset_mock()
            mock_warm.reset_mock()
            
            # Set up error
            error_setup()
            
            # Should still return a result
            result = render_daily_portfolio_summary(sample_data)
            self.assertIsInstance(result, str)
    
    def test_edge_case_data_types(self):
        """Test handling of edge case data types."""
        edge_case_data = {
            "asOfDate": 20240115,  # Integer instead of string
            "cashBalance": "1000.0",  # String instead of float
            "holdings": None,  # None instead of list
            "summaryFrame": "invalid",  # String instead of DataFrame
            "history": [],  # Empty list instead of DataFrame
            "indexSymbols": "^GSPC",  # String instead of list
        }
        
        with patch('ui.summary.get_cached_price_data'), \
             patch('ui.summary.get_cached_price_history'), \
             patch('ui.summary.warm_cache_for_symbols'):
            
            # Should handle gracefully without crashing
            result = render_daily_portfolio_summary(edge_case_data)
            self.assertIsInstance(result, str)
    
    def test_configuration_edge_cases(self):
        """Test configuration edge cases."""
        # Test with extreme configuration values
        extreme_config = create_test_config(
            default_history_months=0,  # Zero months
            min_observations_for_metrics=1000,  # Very high threshold
            price_cache_ttl_minutes=0,  # No caching
            currency_precision=10,  # High precision
            percentage_precision=0   # No decimal places
        )
        
        sample_data = {
            "asOfDate": "2024-01-15",
            "cashBalance": 1234.5678,
            "holdings": [{"symbol": "AAPL", "shares": 10, "price": 150.123456}]
        }
        
        with patch('ui.summary.get_cached_price_data') as mock_price, \
             patch('ui.summary.get_cached_price_history'), \
             patch('ui.summary.warm_cache_for_symbols'):
            
            mock_price.return_value = {"symbol": "AAPL", "close": 150.123456, "pct_change": 1.23456, "volume": 1000000}
            
            result = render_daily_portfolio_summary(sample_data, config=extreme_config)
            
            # Should handle extreme config values
            self.assertIsInstance(result, str)
            # Check precision is applied
            self.assertIn("1,234.5678000000", result)  # High currency precision


if __name__ == '__main__':
    unittest.main(verbosity=2)