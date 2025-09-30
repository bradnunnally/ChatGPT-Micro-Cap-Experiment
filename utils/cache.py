"""
Market data caching utilities for performance optimization.

This module provides TTL-based caching for market data to reduce redundant API calls
and improve daily summary generation performance.
"""

import time
import logging
from functools import lru_cache
from typing import Dict, Optional, Any, List
import pandas as pd
import threading

from services.core.market_service import MarketService


# Configure logging
logger = logging.getLogger(__name__)

# Thread-safe cache access
_cache_lock = threading.RLock()

# Global market service instance
_market_service: Optional[MarketService] = None


def _get_market_service() -> MarketService:
    """Get singleton market service instance."""
    global _market_service
    if _market_service is None:
        _market_service = MarketService()
    return _market_service


@lru_cache(maxsize=256)
def _cached_price_history(symbol: str, months: int, cache_key: int) -> Optional[pd.DataFrame]:
    """
    Internal cached function for price history data.
    
    Args:
        symbol: Stock symbol to fetch
        months: Number of months of history
        cache_key: Time-based cache key for TTL behavior
        
    Returns:
        DataFrame with price history or None if fetch failed
    """
    with _cache_lock:
        try:
            logger.debug(f"Cache MISS: Fetching price history for {symbol} ({months}m) - key {cache_key}")
            market_service = _get_market_service()
            result = market_service.fetch_history(symbol, months=months)
            
            if result is not None and not result.empty:
                logger.debug(f"Cache STORE: Successfully cached {len(result)} records for {symbol}")
                return result.copy()  # Return copy to prevent cache mutation
            else:
                logger.warning(f"Cache STORE: Empty/None result for {symbol}")
                return None
                
        except Exception as e:
            logger.error(f"Cache MISS ERROR: Failed to fetch {symbol} - {e}")
            return None


@lru_cache(maxsize=128)
def _cached_price_data(symbol: str, cache_key: int) -> Dict[str, Optional[float]]:
    """
    Internal cached function for current price/volume data.
    
    Args:
        symbol: Stock symbol to fetch
        cache_key: Time-based cache key for TTL behavior
        
    Returns:
        Dictionary with symbol, close, pct_change, volume data
    """
    with _cache_lock:
        try:
            logger.debug(f"Cache MISS: Fetching current price for {symbol} - key {cache_key}")
            market_service = _get_market_service()
            
            # Fetch 3 months of history to get recent price/volume
            hist = market_service.fetch_history(symbol, months=3)
            
            result: Dict[str, Optional[float]] = {
                "symbol": symbol, 
                "close": None, 
                "pct_change": None, 
                "volume": None
            }
            
            if hist is None or hist.empty:
                logger.warning(f"Cache STORE: Empty history for {symbol}")
                return result

            df = hist.copy()
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"], errors="coerce")
                df = df.dropna(subset=["date"]).sort_values("date")

            closes = pd.to_numeric(df.get("close"), errors="coerce") if "close" in df else pd.Series([], dtype=float)
            closes = closes.dropna()
            
            if closes.empty:
                logger.warning(f"Cache STORE: No valid closes for {symbol}")
                return result

            close = float(closes.iloc[-1])
            prev = float(closes.iloc[-2]) if len(closes) > 1 else None
            pct = None
            if prev and prev != 0:
                pct = (close - prev) / prev * 100.0

            volume_series = pd.to_numeric(df.get("volume"), errors="coerce") if "volume" in df else pd.Series([], dtype=float)
            volume_series = volume_series.dropna()
            volume = float(volume_series.iloc[-1]) if not volume_series.empty else None

            result["close"] = close
            result["pct_change"] = pct
            result["volume"] = volume
            
            logger.debug(f"Cache STORE: Cached price data for {symbol} - ${close:.2f}")
            return result
            
        except Exception as e:
            logger.error(f"Cache MISS ERROR: Failed to fetch price data for {symbol} - {e}")
            return {"symbol": symbol, "close": None, "pct_change": None, "volume": None}


def get_cached_price_history(symbol: str, months: int = 3, ttl_minutes: int = 5) -> Optional[pd.DataFrame]:
    """
    Get cached price history with TTL behavior.
    
    Args:
        symbol: Stock symbol to fetch
        months: Number of months of history to fetch
        ttl_minutes: Cache TTL in minutes (default 5 minutes)
        
    Returns:
        DataFrame with price history or None if unavailable
    """
    if not symbol or not symbol.strip():
        return None
        
    cache_key = int(time.time() // (ttl_minutes * 60))
    
    try:
        result = _cached_price_history(symbol.strip().upper(), months, cache_key)
        if result is not None:
            logger.debug(f"Cache HIT: Price history for {symbol} from cache key {cache_key}")
            return result.copy()  # Return copy to prevent mutation
        return None
    except Exception as e:
        logger.error(f"Cache error for {symbol}: {e}")
        return None


def get_cached_price_data(symbol: str, ttl_minutes: int = 5) -> Dict[str, Optional[float]]:
    """
    Get cached current price/volume data with TTL behavior.
    
    Args:
        symbol: Stock symbol to fetch
        ttl_minutes: Cache TTL in minutes (default 5 minutes)
        
    Returns:
        Dictionary with symbol, close, pct_change, volume data
    """
    if not symbol or not symbol.strip():
        return {"symbol": symbol, "close": None, "pct_change": None, "volume": None}
        
    cache_key = int(time.time() // (ttl_minutes * 60))
    
    try:
        result = _cached_price_data(symbol.strip().upper(), cache_key)
        logger.debug(f"Cache HIT: Price data for {symbol} from cache key {cache_key}")
        return result
    except Exception as e:
        logger.error(f"Cache error for {symbol}: {e}")
        return {"symbol": symbol, "close": None, "pct_change": None, "volume": None}


def warm_cache_for_symbols(symbols: List[str], ttl_minutes: int = 5) -> Dict[str, bool]:
    """
    Warm cache for common symbols to improve performance.
    
    Args:
        symbols: List of symbols to pre-cache
        ttl_minutes: Cache TTL in minutes
        
    Returns:
        Dictionary mapping symbols to success status
    """
    results = {}
    
    logger.info(f"Cache warming: Pre-loading {len(symbols)} symbols")
    
    for symbol in symbols:
        if not symbol or not symbol.strip():
            results[symbol] = False
            continue
            
        try:
            # Warm both price data and history caches
            price_data = get_cached_price_data(symbol, ttl_minutes)
            history_data = get_cached_price_history(symbol, months=6, ttl_minutes=ttl_minutes)
            
            success = (
                price_data.get("close") is not None or 
                (history_data is not None and not history_data.empty)
            )
            results[symbol] = success
            
            if success:
                logger.debug(f"Cache warm SUCCESS: {symbol}")
            else:
                logger.warning(f"Cache warm FAILED: {symbol} - no data available")
                
        except Exception as e:
            logger.error(f"Cache warm ERROR: {symbol} - {e}")
            results[symbol] = False
    
    success_count = sum(results.values())
    logger.info(f"Cache warming complete: {success_count}/{len(symbols)} symbols cached successfully")
    
    return results


def get_cache_stats() -> Dict[str, Any]:
    """Get cache statistics for monitoring."""
    with _cache_lock:
        price_info = _cached_price_data.cache_info()
        history_info = _cached_price_history.cache_info()
        
        return {
            "price_cache": {
                "hits": price_info.hits,
                "misses": price_info.misses,
                "hit_rate": price_info.hits / (price_info.hits + price_info.misses) if (price_info.hits + price_info.misses) > 0 else 0.0,
                "size": price_info.currsize,
                "max_size": price_info.maxsize
            },
            "history_cache": {
                "hits": history_info.hits,
                "misses": history_info.misses,
                "hit_rate": history_info.hits / (history_info.hits + history_info.misses) if (history_info.hits + history_info.misses) > 0 else 0.0,
                "size": history_info.currsize,
                "max_size": history_info.maxsize
            }
        }


def clear_cache() -> None:
    """Clear all cached data."""
    with _cache_lock:
        _cached_price_data.cache_clear()
        _cached_price_history.cache_clear()
        logger.info("Cache cleared: All cached market data removed")


# Common symbols for cache warming
COMMON_SYMBOLS = ["^GSPC", "^DJI", "^IXIC", "^RUT", "^VIX"]