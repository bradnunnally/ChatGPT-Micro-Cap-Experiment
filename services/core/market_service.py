from typing import Optional
from datetime import datetime, timedelta, UTC
import logging

import pandas as pd

from services.core.market_data_service import MarketDataService
from services.core.validation import validate_ticker


class MarketService:
    """Facade for market data operations with caching and resilience.
    
    Provides a simplified interface over MarketDataService with additional
    functionality for historical data fetching and provider abstraction.
    """

    # Standard OHLCV columns for consistency
    _STANDARD_COLUMNS = ["date", "open", "high", "low", "close", "volume"]

    def __init__(self) -> None:
        self._svc = MarketDataService()
        self._logger = logging.getLogger(__name__)

    def get_current_price(self, ticker: str) -> Optional[float]:
        """Get current price for a ticker symbol.
        
        Args:
            ticker: The ticker symbol to look up
            
        Returns:
            Current price or None if unavailable
        """
        try:
            return self._svc.get_price(ticker)
        except Exception as e:
            self._logger.warning("Failed to get price for %s: %s", ticker, e)
            return None

    def validate_ticker(self, ticker: str) -> bool:
        """Validate that a ticker symbol is valid and has available data.
        
        Args:
            ticker: The ticker symbol to validate
            
        Returns:
            True if ticker is valid and has price data available
        """
        try:
            validate_ticker(ticker)
            price = self.get_current_price(ticker)
            return price is not None
        except Exception as e:
            self._logger.debug("Ticker validation failed for %s: %s", ticker, e)
            return False

    def fetch_history(self, symbol: str, months: int = 6) -> pd.DataFrame:
        """Fetch historical OHLCV data for a symbol.
        
        Uses provider chain (Finnhub → yfinance → synthetic) to fetch
        up to the specified number of months of daily data.
        
        Args:
            symbol: The ticker symbol to fetch history for
            months: Number of months of history to fetch (default: 6)
            
        Returns:
            DataFrame with columns: date, open, high, low, close, volume
            Returns empty DataFrame with standard columns if fetch fails
        """
        if not symbol or not isinstance(symbol, str):
            self._logger.warning("Invalid symbol provided: %s", symbol)
            return self._empty_history_dataframe()
            
        if months <= 0:
            self._logger.warning("Invalid months parameter: %s", months)
            return self._empty_history_dataframe()
            
        symbol = symbol.strip().upper()
        
        try:
            provider = self._get_provider()
            if not provider:
                self._logger.warning("No provider available for history fetch")
                return self._empty_history_dataframe()
            
            # Calculate time window (use calendar days approximation)
            end_date = datetime.now(UTC).date()
            start_date = end_date - timedelta(days=months * 30)
            
            self._logger.debug("Fetching %d months history for %s (%s to %s)", 
                             months, symbol, start_date, end_date)
            
            # Try provider methods in order of preference
            for method_name in ["get_daily_candles", "get_history"]:
                df = self._try_provider_method(provider, method_name, symbol, start_date, end_date)
                if df is not None and not df.empty:
                    self._logger.info("Successfully fetched %d rows of history for %s via %s", 
                                    len(df), symbol, method_name)
                    return self._normalize_history_dataframe(df)
            
            self._logger.warning("All provider methods failed for %s", symbol)
            return self._empty_history_dataframe()
            
        except Exception as e:
            self._logger.exception("Unexpected error fetching history for %s: %s", symbol, e)
            return self._empty_history_dataframe()

    def _get_provider(self):
        """Get the active market data provider."""
        try:
            from micro_config import get_provider as micro_get_provider
            return micro_get_provider()
        except ImportError:
            try:
                from config import get_provider
                return get_provider()
            except ImportError:
                self._logger.error("No provider module available")
                return None

    def _try_provider_method(self, provider, method_name: str, symbol: str, start_date, end_date) -> Optional[pd.DataFrame]:
        """Try a specific provider method for fetching history."""
        if not hasattr(provider, method_name):
            return None
            
        try:
            method = getattr(provider, method_name)
            if method_name == "get_daily_candles":
                return method(symbol, start=start_date, end=end_date)
            else:  # get_history
                return method(symbol, start_date, end_date)
        except Exception as e:
            self._logger.debug("Provider method %s failed for %s: %s", method_name, symbol, e)
            return None

    def _normalize_history_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize a history DataFrame to standard columns and format."""
        if df.empty:
            return self._empty_history_dataframe()
            
        # Ensure we have the standard columns (use available data)
        normalized = pd.DataFrame()
        
        for col in self._STANDARD_COLUMNS:
            if col in df.columns:
                normalized[col] = df[col]
            elif col.title() in df.columns:  # Try title case
                normalized[col] = df[col.title()]
            else:
                # Fill missing columns with NaN for numeric, empty string for others
                if col == "date":
                    normalized[col] = pd.NaT
                else:
                    normalized[col] = pd.NA
        
        # Ensure date column is datetime
        if "date" in normalized.columns:
            normalized["date"] = pd.to_datetime(normalized["date"], errors="coerce")
        
        return normalized

    def _empty_history_dataframe(self) -> pd.DataFrame:
        """Return an empty DataFrame with standard history columns."""
        return pd.DataFrame(columns=self._STANDARD_COLUMNS)
