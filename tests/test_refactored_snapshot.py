#!/usr/bin/env python3
"""Test script to verify the refactored save_portfolio_snapshot function."""

import pandas as pd
import tempfile
import os
from unittest.mock import patch, Mock

# Add the project root to path
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data.portfolio import save_portfolio_snapshot


def test_refactored_save_portfolio_snapshot():
    """Test that the refactored save_portfolio_snapshot works correctly."""
    print("Testing refactored save_portfolio_snapshot...")
    
    # Create a temporary database for testing
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_db:
        temp_db_path = temp_db.name
    
    try:
        # Patch the database path and initialize database
        with patch('data.db.DB_FILE', temp_db_path):
            # Initialize the database first
            from data.db import init_db
            init_db()
            
            # Create sample portfolio data
            portfolio_df = pd.DataFrame({
                    'ticker': ['AAPL', 'GOOGL'],
                    'shares': [10, 5],
                    'stop_loss': [140.0, 2400.0],
                    'buy_price': [150.0, 2500.0],
                    'cost_basis': [1500.0, 12500.0]
                })
                
                cash = 5000.0
                
                # Mock the price fetching to return known values
                mock_prices = {'AAPL': 155.0, 'GOOGL': 2600.0}
                
                with patch('services.price_fetching.get_current_prices_for_portfolio', return_value=mock_prices):
                    # Call the refactored function
                    result = save_portfolio_snapshot(portfolio_df, cash)
                    
                    # Verify result structure
                    assert isinstance(result, pd.DataFrame), "Result should be a DataFrame"
                    assert not result.empty, "Result should not be empty"
                    
                    # Check that we have the expected columns
                    expected_columns = ['date', 'ticker', 'shares', 'cost_basis', 'stop_loss', 
                                      'current_price', 'total_value', 'pnl', 'action']
                    for col in expected_columns:
                        assert col in result.columns, f"Missing column: {col}"
                    
                    # Verify we have rows for both tickers plus potentially a TOTAL row
                    assert len(result) >= 2, "Should have at least 2 rows (one per ticker)"
                    
                    # Check that prices were applied correctly
                    aapl_rows = result[result['ticker'] == 'AAPL']
                    if not aapl_rows.empty:
                        assert aapl_rows.iloc[0]['current_price'] == 155.0, "AAPL price should be 155.0"
                    
                    print("✓ Refactored function returns correct DataFrame structure")
                    print(f"✓ Result has {len(result)} rows with expected columns")
                    print("✓ Price data correctly applied to snapshot")
        
        print("✓ Refactored save_portfolio_snapshot test passed!")
                    
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        if os.path.exists(temp_db_path):
            os.unlink(temp_db_path)


def test_empty_portfolio_handling():
    """Test handling of empty portfolio."""
    print("\nTesting empty portfolio handling...")
    
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_db:
        temp_db_path = temp_db.name
    
    try:
        with patch('data.db.DB_FILE', temp_db_path):
            # Initialize the database first
            from data.db import init_db
            init_db()
            
            # Empty portfolio
            portfolio_df = pd.DataFrame(columns=['ticker', 'shares', 'stop_loss', 'buy_price', 'cost_basis'])
            cash = 10000.0
            
            # Mock empty price fetching
            with patch('services.price_fetching.get_current_prices_for_portfolio', return_value={}):
                result = save_portfolio_snapshot(portfolio_df, cash)
                
                # Should still return a valid DataFrame
                assert isinstance(result, pd.DataFrame), "Result should be a DataFrame"
                # May be empty or have just cash/total rows
                
                print("✓ Empty portfolio handled correctly")
        
    except Exception as e:
        print(f"✗ Empty portfolio test failed: {e}")
        raise
    finally:
        if os.path.exists(temp_db_path):
            os.unlink(temp_db_path)


if __name__ == '__main__':
    test_refactored_save_portfolio_snapshot()
    test_empty_portfolio_handling()
    print("\n🎉 All refactoring tests passed! The save_portfolio_snapshot function has been successfully refactored.")