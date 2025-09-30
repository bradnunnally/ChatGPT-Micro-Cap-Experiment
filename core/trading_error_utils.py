"""Trading-specific error handling utilities and patterns.

Provides consistent error handling for trading operations that maintains
backward compatibility while improving separation of concerns.
"""

from __future__ import annotations

from typing import Any, TypeVar, Union, Tuple, Optional
import pandas as pd

from core.error_utils import log_and_return_default, log_and_raise_domain_error
from core.errors import MarketDataError, ValidationError, RepositoryError
from infra.logging import get_logger
from services.logging import log_error, audit_logger

T = TypeVar('T')


def handle_market_data_failure(
    operation: str, 
    ticker: str, 
    exception: Exception, 
    allow_fallback: bool = True
) -> tuple[bool, str | None]:
    """Handle market data failures consistently across trading operations.
    
    Args:
        operation: Name of the trading operation (e.g., "buy_price_validation")
        ticker: The ticker symbol involved
        exception: The market data exception that occurred
        allow_fallback: Whether to allow fallback behavior (graceful degradation)
        
    Returns:
        Tuple of (has_data, error_message). If allow_fallback=True and the error
        is non-critical, returns (False, None) to allow graceful degradation.
    """
    logger = get_logger(__name__)
    
    # For specific market data errors, allow graceful degradation
    from core.errors import MarketDataDownloadError, NoMarketDataError
    if isinstance(exception, (MarketDataDownloadError, NoMarketDataError)) and allow_fallback:
        logger.warning(f"Market data unavailable for {operation}", extra={
            "operation": operation,
            "ticker": ticker,
            "reason": str(exception),
            "fallback_enabled": True
        })
        return False, None
    
    # For other errors or when fallback not allowed, return error
    error_msg = f"Market data error for {ticker}: {str(exception)}"
    logger.error(f"Market data failure in {operation}", extra={
        "operation": operation,
        "ticker": ticker,
        "exception_type": type(exception).__name__,
        "exception_message": str(exception)
    })
    return False, error_msg


def handle_repository_failure(
    operation: str,
    exception: Exception,
    context: dict[str, Any] | None = None
) -> str:
    """Handle repository/database failures consistently.
    
    Args:
        operation: Name of the operation that failed
        exception: The repository exception that occurred
        context: Additional context for logging
        
    Returns:
        Human-readable error message for user display
    """
    logger = get_logger(__name__)
    
    error_msg = f"Database operation failed: {str(exception)}"
    logger.error(f"Repository failure in {operation}", extra={
        "operation": operation,
        "exception_type": type(exception).__name__,
        "exception_message": str(exception),
        **(context or {})
    })
    return error_msg


def audit_trade_failure(
    action: str,
    ticker: str,
    shares: float,
    price: float,
    reason: str
) -> None:
    """Consistently audit failed trade attempts.
    
    Args:
        action: Trade action ("buy" or "sell")
        ticker: Ticker symbol
        shares: Number of shares
        price: Price per share
        reason: Reason for failure
    """
    audit_logger.trade(
        action, 
        ticker=ticker, 
        shares=shares, 
        price=price, 
        status="failure", 
        reason=reason
    )


def create_trade_response(
    success: bool,
    message: str,
    portfolio_df: pd.DataFrame,
    cash: float,
    session_mode: bool
) -> Union[bool, Tuple[bool, str, pd.DataFrame, float]]:
    """Create consistent trade response based on operation mode.
    
    Args:
        success: Whether the trade succeeded
        message: Success/error message
        portfolio_df: Updated portfolio DataFrame
        cash: Updated cash balance  
        session_mode: Whether in session mode (returns bool) or full mode (returns tuple)
        
    Returns:
        Bool if session_mode=True, tuple if session_mode=False
    """
    if success:
        return True if session_mode else (True, message, portfolio_df, cash)
    else:
        # Log error and audit failure
        log_error(message)
        return False if session_mode else (False, message, portfolio_df, cash)


def safe_repository_operation(
    operation_name: str,
    operation_func: callable,
    *args: Any,
    **kwargs: Any
) -> tuple[bool, str | None]:
    """Safely execute repository operations with consistent error handling.
    
    Args:
        operation_name: Human-readable name of the operation
        operation_func: Function to execute
        *args: Positional arguments to pass to operation_func
        **kwargs: Keyword arguments to pass to operation_func
        
    Returns:
        Tuple of (success, error_message). If success=False, error_message contains details.
    """
    logger = get_logger(__name__)
    
    try:
        operation_func(*args, **kwargs)
        return True, None
    except Exception as exc:
        error_msg = handle_repository_failure(operation_name, exc)
        return False, error_msg