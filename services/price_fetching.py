"""Price fetching service for portfolio operations.

This module provides centralized price fetching functionality with fallback mechanisms
for portfolio snapshot operations.
"""

import logging
from typing import Dict, List
import pandas as pd

from services.market import fetch_prices, get_current_price
from services.manual_pricing import get_manual_price

logger = logging.getLogger(__name__)


class PriceFetchingService:
    """Service for fetching current prices with multiple fallback strategies."""
    
    def fetch_prices_for_portfolio(self, tickers: List[str]) -> Dict[str, float]:
        """Fetch current prices for a list of tickers with fallback strategies.
        
        Args:
            tickers: List of ticker symbols to fetch prices for
            
        Returns:
            Dict mapping ticker symbols to current prices (0.0 if unavailable)
        """
        if not tickers:
            return {}
            
        logger.debug(f"Fetching prices for {len(tickers)} tickers: {tickers}")
        
        # Initialize prices dict with zeros
        prices: Dict[str, float] = {ticker: 0.0 for ticker in tickers}
        
        # Try bulk fetch first
        bulk_data = self._try_bulk_fetch(tickers)
        if bulk_data:
            prices.update(bulk_data)
            successful_tickers = [t for t, p in prices.items() if p > 0.0]
            logger.info(f"Bulk fetch successful for {len(successful_tickers)}/{len(tickers)} tickers")
        
        # For tickers that still have zero prices, try individual fallback
        failed_tickers = [ticker for ticker, price in prices.items() if price == 0.0]
        if failed_tickers:
            individual_data = self._try_individual_fetch(failed_tickers)
            prices.update(individual_data)
            
            final_successful = [t for t, p in prices.items() if p > 0.0]
            logger.info(f"Final price fetch: {len(final_successful)}/{len(tickers)} tickers successful")
        
        return prices
    
    def _try_bulk_fetch(self, tickers: List[str]) -> Dict[str, float]:
        """Attempt bulk price fetching.
        
        Args:
            tickers: List of ticker symbols
            
        Returns:
            Dict of successfully fetched prices
        """
        try:
            # Use the existing fetch_prices function to maintain compatibility
            data = fetch_prices(tickers)
            if data.empty:
                logger.debug("Bulk fetch returned empty DataFrame")
                return {}
                
            return self._extract_prices_from_bulk_data(data, tickers)
            
        except Exception as e:
            logger.warning(f"Bulk price fetch failed: {e}")
            return {}
    
    def _extract_prices_from_bulk_data(self, data: pd.DataFrame, tickers: List[str]) -> Dict[str, float]:
        """Extract prices from bulk fetch response data.
        
        Args:
            data: DataFrame returned from bulk fetch
            tickers: Original list of tickers requested
            
        Returns:
            Dict of extracted prices
        """
        prices = {}
        
        try:
            # Handle MultiIndex columns (yfinance format)
            if isinstance(data.columns, pd.MultiIndex):
                if "Close" in data.columns.get_level_values(0):
                    close_data = data["Close"].iloc[-1]
                    for ticker in tickers:
                        val = close_data.get(ticker)
                        if val is not None and not pd.isna(val):
                            prices[ticker] = float(val)
            
            # Handle ticker/current_price format (our internal format)
            elif set(["ticker", "current_price"]).issubset(set(data.columns)):
                for _, row in data.iterrows():
                    ticker = str(row["ticker"])
                    current_price = row.get("current_price") if hasattr(row, "get") else row["current_price"]
                    if ticker in tickers and pd.notna(current_price):
                        prices[ticker] = float(current_price)
            
            # Handle single ticker case
            elif "Close" in data.columns and len(tickers) == 1:
                val = data["Close"].iloc[-1]
                if not pd.isna(val):
                    prices[tickers[0]] = float(val)
                    
        except Exception as e:
            logger.warning(f"Error extracting prices from bulk data: {e}")
        
        return prices
    
    def _try_individual_fetch(self, tickers: List[str]) -> Dict[str, float]:
        """Attempt individual price fetching with manual price fallback.
        
        Args:
            tickers: List of ticker symbols that failed bulk fetch
            
        Returns:
            Dict of successfully fetched prices
        """
        prices = {}
        
        if not tickers:
            return prices
            
        logger.info(f"Attempting individual price lookups for {len(tickers)} tickers")
        
        for ticker in tickers:
            price = self._fetch_single_ticker_price(ticker)
            if price is not None and price > 0.0:
                prices[ticker] = price
                
        return prices
    
    def _fetch_single_ticker_price(self, ticker: str) -> float:
        """Fetch price for a single ticker with manual override fallback.
        
        Args:
            ticker: Ticker symbol
            
        Returns:
            Price if found, 0.0 if not available
        """
        # First try manual pricing override
        manual_price = get_manual_price(ticker)
        if manual_price is not None:
            logger.info(f"Using manual price for {ticker}: ${manual_price}")
            return float(manual_price)
        
        # If no manual price, try API
        try:
            api_price = get_current_price(ticker)
            if api_price is not None and api_price > 0:
                logger.info(f"Successfully fetched individual price for {ticker}: ${api_price}")
                return float(api_price)
        except Exception as e:
            logger.warning(f"Individual price fetch failed for {ticker}: {e}")
        
        return 0.0


# Global service instance
_price_service = PriceFetchingService()


def get_current_prices_for_portfolio(tickers: List[str]) -> Dict[str, float]:
    """Convenience function to fetch prices using the global service instance.
    
    Args:
        tickers: List of ticker symbols
        
    Returns:
        Dict mapping tickers to current prices
    """
    return _price_service.fetch_prices_for_portfolio(tickers)