"""
Standardized error handling utilities for portfolio management application.

This module provides consistent error handling patterns, decorators, and logging
to improve debugging and maintain output format consistency.
"""

import logging
import functools
from typing import Any, Callable, TypeVar, Optional, Dict, List
import pandas as pd

# Configure logging
logger = logging.getLogger(__name__)

# Type variable for decorated functions
F = TypeVar('F', bound=Callable[..., Any])


def handle_summary_errors(fallback_value: Any = None):
    """
    Decorator for standardized error handling in summary functions.
    
    Args:
        fallback_value: Value to return on error (must match expected return type)
        
    Returns:
        Decorated function with error handling
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.warning(f"Error in {func.__name__}: {e}", exc_info=True)
                return fallback_value
        return wrapper
    return decorator


def handle_data_errors(fallback_value: Any = None, log_level: str = "warning"):
    """
    Decorator for data processing functions with configurable logging level.
    
    Args:
        fallback_value: Value to return on error
        log_level: Logging level ('debug', 'info', 'warning', 'error')
        
    Returns:
        Decorated function with error handling
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                log_func = getattr(logger, log_level.lower(), logger.warning)
                log_func(f"Data processing error in {func.__name__}: {e}", exc_info=True)
                return fallback_value
        return wrapper
    return decorator


def handle_cache_errors(fallback_value: Any = None):
    """
    Decorator specifically for cache-related operations.
    
    Args:
        fallback_value: Value to return on cache error
        
    Returns:
        Decorated function with cache error handling
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.debug(f"Cache error in {func.__name__}: {e}")
                return fallback_value
        return wrapper
    return decorator


def safe_numeric_conversion(value: Any, fallback: float = 0.0) -> float:
    """
    Safely convert value to numeric with fallback.
    
    Args:
        value: Value to convert
        fallback: Fallback value if conversion fails
        
    Returns:
        Numeric value or fallback
    """
    try:
        if pd.isna(value) or value is None:
            return fallback
        return float(value)
    except (ValueError, TypeError):
        logger.debug(f"Failed to convert {value} to numeric, using fallback {fallback}")
        return fallback


def safe_dataframe_operation(df: pd.DataFrame, operation: str, fallback: Any = None) -> Any:
    """
    Safely perform DataFrame operations with error handling.
    
    Args:
        df: DataFrame to operate on
        operation: Description of operation for logging
        fallback: Fallback value on error
        
    Returns:
        Operation result or fallback
    """
    try:
        if df is None or df.empty:
            logger.debug(f"Empty DataFrame for operation: {operation}")
            return fallback
        return df
    except Exception as e:
        logger.debug(f"DataFrame operation '{operation}' failed: {e}")
        return fallback


def create_empty_result(result_type: str) -> Any:
    """
    Create appropriate empty result based on expected type.
    
    Args:
        result_type: Type of result expected ('dict', 'list', 'dataframe', 'string')
        
    Returns:
        Appropriate empty result
    """
    # Define risk metrics separately to avoid recursion
    empty_risk_metrics = {
        "max_drawdown": None,
        "max_drawdown_date": None,
        "sharpe_period": None,
        "sharpe_annual": None,
        "sortino_period": None,
        "sortino_annual": None,
        "beta": None,
        "alpha_annual": None,
        "r_squared": None,
        "obs": 0,
        "note": "Error occurred during calculation",
        "sp_first_close": None,
        "sp_last_close": None,
        "is_synthetic": False,
    }
    
    empty_results = {
        'dict': {},
        'list': [],
        'dataframe': pd.DataFrame(),
        'string': "",
        'price_data': {"symbol": None, "close": None, "pct_change": None, "volume": None},
        'risk_metrics': empty_risk_metrics,
        'portfolio_metrics': {
            "risk_metrics": empty_risk_metrics,
            "invested_value": 0.0,
            "total_equity": 0.0,
        },
        'summary_data': {
            "as_of_display": "",
            "cash_balance": 0.0,
            "holdings": [],
            "holdings_df": pd.DataFrame(),
            "summary_df": None,
            "history_df": None,
            "index_symbols": [],
            "benchmark_symbol": "^GSPC",
        }
    }
    
    return empty_results.get(result_type, None)


def log_performance_metric(func_name: str, duration: float, success: bool = True):
    """
    Log performance metrics for functions.
    
    Args:
        func_name: Name of the function
        duration: Execution duration in seconds
        success: Whether the function succeeded
    """
    status = "SUCCESS" if success else "FAILED"
    logger.info(f"Performance: {func_name} completed in {duration:.3f}s - {status}")


def validate_input_data(data: Dict[str, Any], required_fields: List[str]) -> bool:
    """
    Validate that input data contains required fields.
    
    Args:
        data: Input data dictionary
        required_fields: List of required field names
        
    Returns:
        True if all required fields present, False otherwise
    """
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        logger.warning(f"Missing required fields: {missing_fields}")
        return False
    return True