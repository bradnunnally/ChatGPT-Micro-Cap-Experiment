from dataclasses import dataclass
from typing import Optional
import logging

import pandas as pd

from services.core.market_service import MarketService


@dataclass
class PortfolioMetrics:
    """Portfolio performance metrics."""
    total_value: float
    total_gain: float
    total_return: float
    holdings_count: int


class PortfolioManager:
    """Manages portfolio positions and performance calculations.
    
    Handles adding/removing positions and integrates with MarketService
    to fetch historical data for new positions.
    """

    def __init__(self, market_service: Optional[MarketService] = None):
        """Initialize portfolio manager.
        
        Args:
            market_service: Optional MarketService instance for dependency injection
        """
        self._portfolio = pd.DataFrame(columns=["ticker", "shares", "price", "cost_basis"])
        self._market_service = market_service or MarketService()
        self._logger = logging.getLogger(__name__)

    def add_position(self, ticker: str, shares: int, price: float) -> None:
        """Add a new position to the portfolio.
        
        Also triggers historical data fetch for the ticker to support
        performance tracking and analysis.
        
        Args:
            ticker: The ticker symbol
            shares: Number of shares
            price: Price per share
            
        Raises:
            ValueError: If inputs are invalid
        """
        # Input validation
        if not ticker or not isinstance(ticker, str):
            raise ValueError(f"Invalid ticker: {ticker}")
        if not isinstance(shares, (int, float)) or shares <= 0:
            raise ValueError(f"Invalid shares: {shares}")
        if not isinstance(price, (int, float)) or price <= 0:
            raise ValueError(f"Invalid price: {price}")
        
        ticker = ticker.strip().upper()
        shares = int(shares)  # Ensure integer shares
        price = float(price)
        cost_basis = shares * price
        
        # Add position to portfolio
        new_position = {
            "ticker": ticker,
            "shares": shares,
            "price": price,
            "cost_basis": cost_basis,
        }
        
        # Use pd.concat with a properly constructed DataFrame to avoid FutureWarning
        new_position_df = pd.DataFrame([new_position])
        if self._portfolio.empty:
            self._portfolio = new_position_df
        else:
            self._portfolio = pd.concat([self._portfolio, new_position_df], ignore_index=True)
        self._logger.info("Added position: %s shares of %s at $%.2f", shares, ticker, price)
        
        # Fetch historical data asynchronously (don't block on failures)
        self._fetch_and_save_history(ticker)

    def _fetch_and_save_history(self, ticker: str) -> None:
        """Fetch and save historical data for a ticker.
        
        This is called automatically when adding positions and should not
        block the main operation if it fails.
        """
        try:
            self._logger.debug("Fetching 6-month history for %s", ticker)
            history = self._market_service.fetch_history(ticker, months=6)
            
            if not history.empty:
                self._save_history_for_ticker(ticker, history)
                self._logger.info("Successfully fetched and saved history for %s (%d rows)", 
                                ticker, len(history))
            else:
                self._logger.warning("No historical data available for %s", ticker)
                
        except Exception as e:
            # Don't block user action on history errors; log and continue
            self._logger.exception("Failed to fetch/persist 6mo history for %s: %s", ticker, e)

    def _save_history_for_ticker(self, ticker: str, history: pd.DataFrame) -> None:
        """Save historical market data for a ticker to persistent storage.
        
        This method stores market price history (OHLCV data) in a separate table
        from portfolio_history, which tracks portfolio position changes over time.
        
        Args:
            ticker: The ticker symbol
            history: DataFrame with historical OHLCV data (columns: date, open, high, low, close, volume)
        """
        if history.empty:
            self._logger.info("No historical data to save for %s", ticker)
            return
            
        # Validate required columns
        required_columns = ["date", "close"]
        missing_columns = [col for col in required_columns if col not in history.columns]
        if missing_columns:
            self._logger.warning("History data missing required columns for %s: %s", 
                               ticker, missing_columns)
            return
        
        try:
            from data.db import get_connection
            
            # Create market_history table if it doesn't exist
            with get_connection() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS market_history (
                        date TEXT,
                        ticker TEXT,
                        open REAL,
                        high REAL,
                        low REAL,
                        close REAL,
                        volume REAL,
                        PRIMARY KEY (date, ticker)
                    )
                """)
                
                # Prepare data for insertion
                ticker = ticker.upper()
                history_clean = history.copy()
                
                # Ensure date is in string format for database storage
                if 'date' in history_clean.columns:
                    history_clean['date'] = pd.to_datetime(history_clean['date']).dt.strftime('%Y-%m-%d')
                
                # Add ticker column
                history_clean['ticker'] = ticker
                
                # Select and reorder columns to match table schema
                columns_to_save = ['date', 'ticker', 'open', 'high', 'low', 'close', 'volume']
                
                # Fill missing columns with None/0
                for col in columns_to_save:
                    if col not in history_clean.columns:
                        if col == 'ticker':
                            history_clean[col] = ticker
                        elif col in ['open', 'high', 'low', 'close', 'volume']:
                            history_clean[col] = 0.0
                        else:
                            history_clean[col] = None
                
                # Reorder columns and clean data
                save_data = history_clean[columns_to_save].copy()
                
                # Remove any existing data for this ticker to avoid duplicates
                conn.execute("DELETE FROM market_history WHERE ticker = ?", (ticker,))
                
                # Insert new data using INSERT OR REPLACE for safety
                insert_sql = """
                    INSERT OR REPLACE INTO market_history 
                    (date, ticker, open, high, low, close, volume) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """
                
                # Convert DataFrame to list of tuples for insertion
                rows_to_insert = []
                for _, row in save_data.iterrows():
                    rows_to_insert.append((
                        row['date'],
                        row['ticker'],
                        float(row['open']) if pd.notna(row['open']) else 0.0,
                        float(row['high']) if pd.notna(row['high']) else 0.0,
                        float(row['low']) if pd.notna(row['low']) else 0.0,
                        float(row['close']) if pd.notna(row['close']) else 0.0,
                        float(row['volume']) if pd.notna(row['volume']) else 0.0
                    ))
                
                # Execute batch insert
                conn.executemany(insert_sql, rows_to_insert)
                
                self._logger.info("Successfully saved %d history rows for ticker %s to market_history table", 
                                len(rows_to_insert), ticker)
                
        except Exception as e:
            # Don't block user action on history persistence errors; log and continue
            self._logger.exception("Failed to persist historical data for %s: %s", ticker, e)

    def get_portfolio_metrics(self) -> PortfolioMetrics:
        """Calculate current portfolio performance metrics.
        
        Returns:
            PortfolioMetrics with current portfolio performance data
        """
        if self._portfolio.empty:
            return PortfolioMetrics(
                total_value=0.0,
                total_gain=0.0, 
                total_return=0.0,
                holdings_count=0
            )

        # Calculate metrics from current portfolio state
        total_value = (self._portfolio["shares"] * self._portfolio["price"]).sum()
        cost_basis = self._portfolio["cost_basis"].sum()
        total_gain = total_value - cost_basis
        total_return = (total_gain / cost_basis * 100) if cost_basis > 0 else 0.0

        return PortfolioMetrics(
            total_value=float(total_value),
            total_gain=float(total_gain),
            total_return=float(total_return),
            holdings_count=len(self._portfolio),
        )

    def get_positions(self) -> pd.DataFrame:
        """Get current portfolio positions.
        
        Returns:
            DataFrame with current positions or empty DataFrame if no positions
        """
        return self._portfolio.copy() if not self._portfolio.empty else pd.DataFrame()

    def remove_position(self, ticker: str) -> bool:
        """Remove a position from the portfolio.
        
        Args:
            ticker: The ticker symbol to remove
            
        Returns:
            True if position was removed, False if not found
        """
        if not ticker or not isinstance(ticker, str):
            return False
            
        ticker = ticker.strip().upper()
        initial_count = len(self._portfolio)
        
        # Remove all positions for this ticker
        self._portfolio = self._portfolio[self._portfolio["ticker"] != ticker]
        
        removed = len(self._portfolio) < initial_count
        if removed:
            self._logger.info("Removed position for %s", ticker)
        else:
            self._logger.warning("No position found for %s to remove", ticker)
            
        return removed
