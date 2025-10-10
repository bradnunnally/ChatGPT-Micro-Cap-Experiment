#!/usr/bin/env python3
"""
Production Demo Script
Demonstrates the production-ready features of the portfolio management system.
"""

import logging
from datetime import datetime

from services.core.market_service import MarketService
from services.portfolio_manager import PortfolioManager


def setup_logging():
    """Configure logging for production demo."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def demo_market_service():
    """Demonstrate MarketService production features."""
    print("\n=== MarketService Production Demo ===")
    
    service = MarketService()
    
    # Test input validation
    print("Testing input validation...")
    result = service.fetch_history("", months=6)
    print(f"Empty ticker result: {len(result)} rows")
    
    result = service.fetch_history("AAPL", months=0)
    print(f"Invalid months result: {len(result)} rows")
    
    # Test successful history fetch
    print("\nFetching AAPL history...")
    result = service.fetch_history("AAPL", months=6)
    print(f"AAPL history: {len(result)} rows")
    if not result.empty:
        print(f"Columns: {list(result.columns)}")
        print(f"Date range: {result['date'].min()} to {result['date'].max()}")


def demo_portfolio_manager():
    """Demonstrate PortfolioManager production features."""
    print("\n=== PortfolioManager Production Demo ===")
    
    # Create portfolio manager
    portfolio_manager = PortfolioManager()
    
    # Test input validation
    print("Testing input validation...")
    try:
        portfolio_manager.add_position("", 10, 150.0)
    except ValueError as e:
        print(f"Caught expected error: {e}")
    
    try:
        portfolio_manager.add_position("AAPL", 0, 150.0)
    except ValueError as e:
        print(f"Caught expected error: {e}")
    
    try:
        portfolio_manager.add_position("AAPL", 10, 0)
    except ValueError as e:
        print(f"Caught expected error: {e}")
    
    # Add valid positions
    print("\nAdding valid positions...")
    portfolio_manager.add_position("AAPL", 10, 150.0)
    portfolio_manager.add_position("MSFT", 5, 300.0)
    
    # Show portfolio metrics
    metrics = portfolio_manager.get_portfolio_metrics()
    print(f"\nPortfolio metrics:")
    print(f"  Total value: ${metrics.total_value:,.2f}")
    print(f"  Total gain: ${metrics.total_gain:,.2f}")
    print(f"  Total return: {metrics.total_return:.2f}%")
    print(f"  Holdings count: {metrics.holdings_count}")
    
    # Show positions
    positions = portfolio_manager.get_positions()
    print(f"\nCurrent positions:")
    for _, position in positions.iterrows():
        print(f"  {position['ticker']}: {position['shares']} shares @ ${position['price']:.2f}")
    
    # Test remove position
    print("\nRemoving MSFT position...")
    removed = portfolio_manager.remove_position("MSFT")
    print(f"Removal successful: {removed}")
    
    final_metrics = portfolio_manager.get_portfolio_metrics()
    print(f"Final holdings count: {final_metrics.holdings_count}")


def main():
    """Run the production demo."""
    setup_logging()
    
    print("Production Portfolio Management System Demo")
    print("=" * 50)
    print(f"Started at: {datetime.now()}")
    
    demo_market_service()
    demo_portfolio_manager()
    
    print(f"\nDemo completed at: {datetime.now()}")


if __name__ == "__main__":
    main()
