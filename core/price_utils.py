"""Price extraction utilities for handling different quote data formats.

This module consolidates common price extraction patterns used across
market data services to reduce duplication and improve consistency.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Union
import pandas as pd


def extract_price_from_quote(quote: Optional[Dict[str, Any]]) -> Optional[float]:
    """Extract price from a quote dictionary with common field names.
    
    Args:
        quote: Quote dictionary from various providers
        
    Returns:
        Extracted price as float, or None if not found
    """
    if not quote or not isinstance(quote, dict):
        return None
    
    # Try common price field names in order of preference
    price_fields = ["price", "last", "c", "close", "current_price"]
    
    for field in price_fields:
        value = quote.get(field)
        if value is not None:
            try:
                price = float(value)
                if price > 0:  # Only return positive prices
                    return price
            except (ValueError, TypeError):
                continue
    
    return None


def extract_price_from_dataframe(
    df: pd.DataFrame, 
    close_column_names: Optional[list[str]] = None
) -> Optional[float]:
    """Extract the most recent price from a DataFrame.
    
    Args:
        df: DataFrame containing price data
        close_column_names: List of column names to try for close price
        
    Returns:
        Most recent close price as float, or None if not found
    """
    if df.empty:
        return None
    
    if close_column_names is None:
        close_column_names = ["Close", "close", "price", "last"]
    
    for col_name in close_column_names:
        if col_name in df.columns:
            close_prices = df[col_name].dropna()
            if not close_prices.empty:
                try:
                    price = float(close_prices.iloc[-1])
                    if price > 0:
                        return price
                except (ValueError, TypeError, IndexError):
                    continue
    
    return None


def extract_percentage_change_from_quote(quote: Optional[Dict[str, Any]]) -> Optional[float]:
    """Extract percentage change from a quote dictionary.
    
    Args:
        quote: Quote dictionary from various providers
        
    Returns:
        Percentage change as float, or None if not found
    """
    if not quote or not isinstance(quote, dict):
        return None
    
    # Try common percentage change field names
    pct_fields = ["percent", "pct_change", "change_percent", "dp", "percentage"]
    
    for field in pct_fields:
        value = quote.get(field)
        if value is not None:
            try:
                return float(value)
            except (ValueError, TypeError):
                continue
    
    return None


def create_price_row(
    ticker: str, 
    quote: Optional[Dict[str, Any]] = None,
    price: Optional[float] = None,
    pct_change: Optional[float] = None
) -> Dict[str, Any]:
    """Create a standardized price row dictionary.
    
    Args:
        ticker: Stock ticker symbol
        quote: Optional quote dictionary to extract data from
        price: Optional explicit price value
        pct_change: Optional explicit percentage change value
        
    Returns:
        Dictionary with standardized price row format
    """
    # Extract from quote if provided and explicit values not given
    if quote and price is None:
        price = extract_price_from_quote(quote)
    if quote and pct_change is None:
        pct_change = extract_percentage_change_from_quote(quote)
    
    return {
        "ticker": ticker,
        "current_price": price,
        "pct_change": pct_change
    }


def safe_price_extraction(extraction_func: callable, *args, **kwargs) -> Optional[float]:
    """Safely execute a price extraction function with error handling.
    
    Args:
        extraction_func: Function to execute for price extraction
        *args: Arguments to pass to the extraction function
        **kwargs: Keyword arguments to pass to the extraction function
        
    Returns:
        Extracted price or None if extraction failed
    """
    try:
        result = extraction_func(*args, **kwargs)
        if isinstance(result, (int, float)) and result > 0:
            return float(result)
        return None
    except Exception:
        return None