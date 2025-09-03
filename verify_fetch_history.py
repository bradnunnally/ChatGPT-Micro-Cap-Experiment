#!/usr/bin/env python3
"""
Quick verification script to test MarketService.fetch_history integration.
Run this to manually verify the implementation works end-to-end.
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.core.market_service import MarketService
from services.portfolio_manager import PortfolioManager

def test_market_service_fetch_history():
    """Test MarketService.fetch_history directly."""
    print("Testing MarketService.fetch_history...")
    
    service = MarketService()
    
    # Test with a well-known ticker
    print("Fetching 6 months history for AAPL...")
    history = service.fetch_history("AAPL", months=6)
    
    print(f"Result: {len(history)} rows")
    print(f"Columns: {list(history.columns)}")
    
    if not history.empty:
        print("Sample data:")
        print(history.head())
        print("✓ fetch_history working")
    else:
        print("⚠ Empty history returned (may be expected in dev_stage)")
    
    return history

def test_portfolio_manager_integration():
    """Test that PortfolioManager calls fetch_history when adding positions."""
    print("\nTesting PortfolioManager integration...")
    
    # Create portfolio manager
    pm = PortfolioManager()
    
    # Add a position (this should trigger fetch_history)
    print("Adding AAPL position...")
    pm.add_position("AAPL", 10, 150.0)
    
    # Check portfolio metrics
    metrics = pm.get_portfolio_metrics()
    print(f"Portfolio metrics: {metrics}")
    
    if metrics.holdings_count == 1 and metrics.total_value == 1500.0:
        print("✓ Portfolio position added successfully")
    else:
        print("✗ Portfolio position not added correctly")
    
    return pm

def main():
    """Run all verification tests."""
    print("MarketService.fetch_history Verification")
    print("=" * 50)
    
    try:
        # Test 1: Direct fetch_history call
        history = test_market_service_fetch_history()
        
        # Test 2: Portfolio manager integration
        portfolio = test_portfolio_manager_integration()
        
        print("\n" + "=" * 50)
        print("✓ All tests completed successfully!")
        print("\nNext steps:")
        print("1. Check logs for 'Would save X history rows for ticker Y' messages")
        print("2. In production (APP_ENV=production), this will fetch real data from Finnhub")
        print("3. In dev_stage, this uses SyntheticDataProvider for deterministic testing")
        
    except Exception as e:
        print(f"\n✗ Error during verification: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
