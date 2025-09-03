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
        new_position = pd.DataFrame({
            "ticker": [ticker],
            "shares": [shares], 
            "price": [price],
            "cost_basis": [cost_basis],
        })
        
        self._portfolio = pd.concat([self._portfolio, new_position], ignore_index=True)
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
        """Save historical data for a ticker to persistent storage.
        
        Args:
            ticker: The ticker symbol
            history: DataFrame with historical OHLCV data
            
        Note:
            This is currently a placeholder. In production, this should
            persist to the portfolio_history database table.
        """
        # TODO: Implement actual persistence to portfolio_history table
        # This should:
        # 1. Connect to the database
        # 2. Transform history data to match portfolio_history schema
        # 3. Insert/upsert records with proper date handling
        # 4. Handle duplicate data gracefully
        
        self._logger.info("Would save %d history rows for ticker %s", len(history), ticker)
        
        # For now, validate the data structure
        required_columns = ["date", "close"]
        missing_columns = [col for col in required_columns if col not in history.columns]
        if missing_columns:
            self._logger.warning("History data missing required columns for %s: %s", 
                               ticker, missing_columns)

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
