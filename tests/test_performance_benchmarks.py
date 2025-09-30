"""
Performance benchmarks for ui.summary module.

This module establishes performance baselines and validates
caching effectiveness for the refactored summary functionality.
"""
import unittest
import time
import statistics
from unittest.mock import patch, MagicMock
import pandas as pd
from typing import List, Dict, Any

from ui.summary import render_daily_portfolio_summary, _fetch_price_volume
from config.summary_config import create_test_config
from tests.test_comprehensive_summary import TestDataFixtures


class PerformanceBenchmarks(unittest.TestCase):
    """Performance benchmark tests for summary module."""
    
    def setUp(self):
        """Set up performance test fixtures."""
        self.sample_data = TestDataFixtures.sample_portfolio_data()
        self.benchmark_config = create_test_config(
            price_cache_ttl_minutes=5,
            default_history_months=6
        )
    
    def _time_function_calls(self, func, *args, **kwargs) -> List[float]:
        """Time multiple function calls and return execution times."""
        times = []
        for _ in range(5):  # Run 5 times for statistical significance
            start_time = time.time()
            func(*args, **kwargs)
            end_time = time.time()
            times.append(end_time - start_time)
        return times
    
    def test_single_summary_generation_performance(self):
        """Benchmark single summary generation performance."""
        with patch('ui.summary.get_cached_price_data') as mock_price, \
             patch('ui.summary.get_cached_price_history') as mock_history, \
             patch('ui.summary.warm_cache_for_symbols') as mock_warm:
            
            mock_price.return_value = TestDataFixtures.sample_price_data()
            mock_history.return_value = TestDataFixtures.sample_history_dataframe()
            mock_warm.return_value = None
            
            times = self._time_function_calls(
                render_daily_portfolio_summary, 
                self.sample_data, 
                self.benchmark_config
            )
            
            avg_time = statistics.mean(times)
            max_time = max(times)
            
            # Performance expectations (with mocked external calls)
            self.assertLess(avg_time, 0.1, f"Average time {avg_time:.3f}s exceeds 100ms limit")
            self.assertLess(max_time, 0.2, f"Maximum time {max_time:.3f}s exceeds 200ms limit")
            
            print(f"Summary generation - Avg: {avg_time:.3f}s, Max: {max_time:.3f}s")
    
    def test_price_fetch_performance_scaling(self):
        """Test price fetching performance with different symbol counts."""
        symbol_counts = [1, 5, 10, 25, 50]
        performance_results = {}
        
        with patch('ui.summary.get_cached_price_data') as mock_price:
            mock_price.return_value = TestDataFixtures.sample_price_data()
            
            for count in symbol_counts:
                symbols = [f"STOCK{i:03d}" for i in range(count)]
                
                start_time = time.time()
                results = [_fetch_price_volume(symbol) for symbol in symbols]
                end_time = time.time()
                
                total_time = end_time - start_time
                time_per_symbol = total_time / count
                
                performance_results[count] = {
                    'total_time': total_time,
                    'time_per_symbol': time_per_symbol,
                    'results_count': len(results)
                }
                
                # Verify all symbols were processed
                self.assertEqual(len(results), count)
                
                print(f"{count} symbols - Total: {total_time:.3f}s, Per symbol: {time_per_symbol:.4f}s")
        
        # Performance should scale reasonably (not exponentially)
        # Time per symbol should remain relatively constant
        time_per_1 = performance_results[1]['time_per_symbol']
        time_per_50 = performance_results[50]['time_per_symbol']
        
        # Should not be more than 2x slower per symbol with 50 symbols vs 1
        scaling_factor = time_per_50 / time_per_1
        self.assertLess(scaling_factor, 2.0, 
                       f"Performance degradation too high: {scaling_factor:.2f}x")
    
    def test_large_portfolio_performance(self):
        """Benchmark performance with large portfolio datasets."""
        # Create large portfolio data
        large_holdings = []
        for i in range(100):
            large_holdings.append({
                "symbol": f"STOCK{i:03d}",
                "shares": 100 + i,
                "price": 50.0 + i,
                "cost_basis": 45.0 + i,
                "ticker": f"STOCK{i:03d}"
            })
        
        large_data = self.sample_data.copy()
        large_data["holdings"] = large_holdings
        
        with patch('ui.summary.get_cached_price_data') as mock_price, \
             patch('ui.summary.get_cached_price_history') as mock_history, \
             patch('ui.summary.warm_cache_for_symbols') as mock_warm:
            
            mock_price.return_value = TestDataFixtures.sample_price_data()
            mock_history.return_value = TestDataFixtures.sample_history_dataframe()
            mock_warm.return_value = None
            
            start_time = time.time()
            result = render_daily_portfolio_summary(large_data, self.benchmark_config)
            end_time = time.time()
            
            execution_time = end_time - start_time
            
            # Large portfolio should still complete in reasonable time
            self.assertLess(execution_time, 2.0, 
                           f"Large portfolio processing too slow: {execution_time:.2f}s")
            
            # Verify result was generated
            self.assertIsInstance(result, str)
            self.assertGreater(len(result), 1000)
            
            print(f"100-holding portfolio processing: {execution_time:.3f}s")
    
    def test_caching_effectiveness_simulation(self):
        """Simulate caching effectiveness with repeated calls."""
        cache_simulation = {}
        
        def mock_cached_price_data(symbol, ttl_minutes=5):
            """Simulate caching behavior."""
            if symbol not in cache_simulation:
                # Simulate network delay for cache miss
                time.sleep(0.01)  # 10ms delay
                cache_simulation[symbol] = TestDataFixtures.sample_price_data()
                cache_simulation[symbol]["symbol"] = symbol
            
            # Cache hit - no delay
            return cache_simulation[symbol]
        
        with patch('ui.summary.get_cached_price_data', side_effect=mock_cached_price_data):
            symbols = ["AAPL", "MSFT", "GOOGL"] * 3  # Repeat symbols
            
            start_time = time.time()
            results = [_fetch_price_volume(symbol) for symbol in symbols]
            end_time = time.time()
            
            total_time = end_time - start_time
            
            # With effective caching, should be much faster than 9 * 10ms = 90ms
            # Expect around 3 * 10ms = 30ms for cache misses + minimal time for hits
            self.assertLess(total_time, 0.06, 
                           f"Caching not effective enough: {total_time:.3f}s")
            
            # Verify all results were returned
            self.assertEqual(len(results), 9)
            
            print(f"Cached fetch simulation (3 unique, 9 total calls): {total_time:.3f}s")
    
    def test_memory_usage_with_large_dataframes(self):
        """Test memory efficiency with large historical datasets."""
        # Create large historical dataset
        large_history = pd.DataFrame({
            "date": pd.date_range("2020-01-01", periods=5000),  # ~13 years daily
            "ticker": ["TOTAL"] * 5000,
            "total_equity": [10000 + i * 10 for i in range(5000)],
            "total_value": [9000 + i * 10 for i in range(5000)],
            "cash_balance": [1000] * 5000
        })
        
        large_data = self.sample_data.copy()
        large_data["history"] = large_history
        
        with patch('ui.summary.get_cached_price_data') as mock_price, \
             patch('ui.summary.get_cached_price_history') as mock_history, \
             patch('ui.summary.warm_cache_for_symbols') as mock_warm:
            
            mock_price.return_value = TestDataFixtures.sample_price_data()
            mock_history.return_value = large_history.copy()
            mock_warm.return_value = None
            
            start_time = time.time()
            result = render_daily_portfolio_summary(large_data, self.benchmark_config)
            end_time = time.time()
            
            execution_time = end_time - start_time
            
            # Should handle large datasets efficiently
            self.assertLess(execution_time, 1.0, 
                           f"Large dataset processing too slow: {execution_time:.3f}s")
            
            # Verify result quality
            self.assertIsInstance(result, str)
            
            print(f"Large history dataset (5000 rows): {execution_time:.3f}s")


class CachingEffectivenessTests(unittest.TestCase):
    """Tests specifically focused on caching system effectiveness."""
    
    def test_cache_ttl_configuration_impact(self):
        """Test impact of different cache TTL configurations."""
        ttl_configs = [1, 5, 15, 60]  # Different TTL minutes
        performance_by_ttl = {}
        
        for ttl in ttl_configs:
            config = create_test_config(price_cache_ttl_minutes=ttl)
            
            with patch('ui.summary.get_cached_price_data') as mock_price, \
                 patch('ui.summary.warm_cache_for_symbols') as mock_warm:
                
                mock_price.return_value = TestDataFixtures.sample_price_data()
                mock_warm.return_value = None
                
                start_time = time.time()
                
                # Simulate multiple fetches that could benefit from caching
                for _ in range(10):
                    _fetch_price_volume("AAPL")
                
                end_time = time.time()
                
                performance_by_ttl[ttl] = {
                    'time': end_time - start_time,
                    'call_count': mock_price.call_count
                }
                
                # Verify TTL parameter was passed correctly
                if mock_price.called:
                    # Check that TTL was used in at least one call
                    ttl_used = any(
                        call.kwargs.get('ttl_minutes') == ttl 
                        for call in mock_price.call_args_list
                    )
                    self.assertTrue(ttl_used, f"TTL {ttl} was not used in cache calls")
        
        print("Cache TTL Performance Impact:")
        for ttl, perf in performance_by_ttl.items():
            print(f"  TTL {ttl}min: {perf['time']:.4f}s, {perf['call_count']} calls")
    
    def test_cache_warm_up_effectiveness(self):
        """Test effectiveness of cache warming."""
        common_symbols = ["AAPL", "MSFT", "GOOGL", "TSLA", "AMZN"]
        
        with patch('ui.summary.warm_cache_for_symbols') as mock_warm, \
             patch('ui.summary.get_cached_price_data') as mock_price:
            
            mock_price.return_value = TestDataFixtures.sample_price_data()
            
            # Test with cache warming
            start_time = time.time()
            
            # This would normally warm the cache
            from ui.summary import warm_cache_for_symbols
            mock_warm.return_value = None
            
            # Then fetch prices (should benefit from warming)
            results = [_fetch_price_volume(symbol) for symbol in common_symbols]
            
            end_time = time.time()
            
            warmed_time = end_time - start_time
            
            # Verify cache warming was called
            self.assertTrue(mock_warm.called, "Cache warming should be called")
            
            # Verify all symbols were processed
            self.assertEqual(len(results), len(common_symbols))
            
            print(f"Cache warming test completed in {warmed_time:.4f}s")


class ErrorHandlingPerformanceTests(unittest.TestCase):
    """Performance tests for error handling scenarios."""
    
    def test_error_recovery_performance(self):
        """Test performance when errors occur."""
        data = TestDataFixtures.sample_portfolio_data()
        
        # Simulate various error conditions
        error_scenarios = [
            ("network_error", Exception("Network timeout")),
            ("data_error", ValueError("Invalid data format")),
            ("system_error", RuntimeError("System overload"))
        ]
        
        for scenario_name, error in error_scenarios:
            with patch('ui.summary.get_cached_price_data') as mock_price, \
                 patch('ui.summary.get_cached_price_history') as mock_history, \
                 patch('ui.summary.warm_cache_for_symbols') as mock_warm:
                
                # Make all external calls fail
                mock_price.side_effect = error
                mock_history.side_effect = error
                mock_warm.side_effect = error
                
                start_time = time.time()
                result = render_daily_portfolio_summary(data)
                end_time = time.time()
                
                error_recovery_time = end_time - start_time
                
                # Error recovery should not take too long
                self.assertLess(error_recovery_time, 0.5, 
                               f"{scenario_name} recovery too slow: {error_recovery_time:.3f}s")
                
                # Should still return valid result
                self.assertIsInstance(result, str)
                self.assertGreater(len(result), 100)
                
                print(f"Error recovery ({scenario_name}): {error_recovery_time:.3f}s")
    
    def test_partial_failure_handling(self):
        """Test performance when some operations fail."""
        data = TestDataFixtures.sample_portfolio_data()
        
        call_count = 0
        def intermittent_failure(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count % 3 == 0:  # Every 3rd call fails
                raise Exception("Intermittent failure")
            return TestDataFixtures.sample_price_data()
        
        with patch('ui.summary.get_cached_price_data', side_effect=intermittent_failure), \
             patch('ui.summary.get_cached_price_history') as mock_history, \
             patch('ui.summary.warm_cache_for_symbols') as mock_warm:
            
            mock_history.return_value = TestDataFixtures.sample_history_dataframe()
            mock_warm.return_value = None
            
            start_time = time.time()
            result = render_daily_portfolio_summary(data)
            end_time = time.time()
            
            partial_failure_time = end_time - start_time
            
            # Should handle partial failures gracefully
            self.assertLess(partial_failure_time, 1.0, 
                           f"Partial failure handling too slow: {partial_failure_time:.3f}s")
            
            # Should still return result
            self.assertIsInstance(result, str)
            
            print(f"Partial failure handling: {partial_failure_time:.3f}s")


if __name__ == '__main__':
    # Run performance benchmarks
    print("Running Performance Benchmarks...")
    print("=" * 50)
    
    unittest.main(verbosity=2)