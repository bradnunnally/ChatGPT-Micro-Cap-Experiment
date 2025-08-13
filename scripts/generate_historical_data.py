"""Generate historical synthetic data for portfolio_history table."""

import sqlite3
from datetime import datetime, timedelta
from typing import List, Tuple
import random

from data.db import get_connection
from config.providers import is_dev_stage


def generate_historical_synthetic_data(days_back: int = 30) -> None:
    """Generate historical portfolio snapshots for the last N days in dev_stage.
    
    Creates realistic price movements and portfolio value progression over time
    to provide meaningful historical charts and analysis.
    """
    if not is_dev_stage():
        return  # Only run in dev_stage environment
    
    # Base portfolio positions for historical simulation
    base_positions = [
        {"ticker": "SYNAAA", "shares": 100.0, "buy_price": 5.0, "stop_loss": 4.5},
        {"ticker": "SYNBBB", "shares": 50.0, "buy_price": 8.0, "stop_loss": 7.25},
    ]
    
    # Starting cash and prices
    cash_balance = 10000.0
    base_prices = {"SYNAAA": 5.0, "SYNBBB": 8.0}
    
    with get_connection() as conn:
        # Check if historical data already exists
        existing_count = conn.execute(
            "SELECT COUNT(DISTINCT date) FROM portfolio_history WHERE date != ? AND ticker != 'TOTAL'",
            (datetime.now().strftime("%Y-%m-%d"),)
        ).fetchone()[0]
        
        if existing_count >= days_back // 2:
            print(f"Historical data already exists ({existing_count} days), skipping generation")
            return
        
        # Clear existing historical data (keep today's)
        today = datetime.now().strftime("%Y-%m-%d")
        conn.execute("DELETE FROM portfolio_history WHERE date != ?", (today,))
        
        # Generate historical data
        for i in range(days_back, 0, -1):
            date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            
            # Simulate price evolution with some volatility
            total_value = 0.0
            total_pnl = 0.0
            
            for pos in base_positions:
                ticker = pos["ticker"]
                shares = pos["shares"]
                buy_price = pos["buy_price"]
                stop_loss = pos["stop_loss"]
                
                # Generate realistic price movement (trending up with volatility)
                days_from_start = days_back - i
                trend_factor = 1 + (days_from_start * 0.02)  # 2% growth per day on average
                volatility = random.uniform(0.85, 1.15)  # ±15% daily volatility
                current_price = base_prices[ticker] * trend_factor * volatility
                
                # Ensure price doesn't go below reasonable minimum
                current_price = max(current_price, buy_price * 0.5)
                
                value = round(current_price * shares, 2)
                pnl = round((current_price - buy_price) * shares, 2)
                cost_basis = buy_price  # For historical consistency
                
                total_value += value
                total_pnl += pnl
                
                # Insert position row
                conn.execute("""
                    INSERT INTO portfolio_history 
                    (date, ticker, shares, cost_basis, stop_loss, current_price, total_value, pnl, action, cash_balance, total_equity)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    date, ticker, shares, cost_basis, stop_loss, current_price, value, pnl, "HOLD", "", ""
                ))
            
            # Insert TOTAL row for the date
            total_equity = total_value + cash_balance
            conn.execute("""
                INSERT INTO portfolio_history 
                (date, ticker, shares, cost_basis, stop_loss, current_price, total_value, pnl, action, cash_balance, total_equity)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                date, "TOTAL", "", "", "", "", round(total_value, 2), round(total_pnl, 2), "", round(cash_balance, 2), round(total_equity, 2)
            ))
        
        print(f"Generated {days_back} days of historical synthetic data")


if __name__ == "__main__":
    generate_historical_synthetic_data()
