"""Standardized error handling utilities for consistent logging and exception management.

This module provides utilities to create consistent error handling patterns across
the codebase while maintaining backward compatibility with existing APIs.
"""

from __future__ import annotations

import logging
from typing import Any, TypeVar, Type

from core.errors import AppError

T = TypeVar('T')


def log_and_reraise(logger: logging.Logger, exception: Exception, operation_name: str, **context: Any) -> None:
    """Log an exception with structured context and re-raise it.
    
    Args:
        logger: Logger to use for error logging
        exception: The original exception that occurred
        operation_name: Human-readable name of the operation that failed
        **context: Additional context fields for structured logging
        
    Raises:
        The original exception after logging
    """
    logger.error(f"{operation_name} failed", extra={
        "operation": operation_name,
        "exception_type": type(exception).__name__,
        "exception_message": str(exception),
        **context
    })
    raise


def log_and_return_default(
    logger: logging.Logger, 
    exception: Exception, 
    default_value: T, 
    operation_name: str, 
    **context: Any
) -> T:
    """Log an exception with structured context and return a default value.
    
    Args:
        logger: Logger to use for error logging
        exception: The original exception that occurred
        default_value: Value to return after logging the error
        operation_name: Human-readable name of the operation that failed
        **context: Additional context fields for structured logging
        
    Returns:
        The provided default value
    """
    logger.error(f"{operation_name} failed, returning default", extra={
        "operation": operation_name,
        "exception_type": type(exception).__name__,
        "exception_message": str(exception),
        "default_value": repr(default_value),
        **context
    })
    return default_value


def log_and_raise_domain_error(
    logger: logging.Logger, 
    exception: Exception, 
    domain_exception_class: Type[AppError], 
    operation_name: str,
    custom_message: str | None = None,
    **context: Any
) -> None:
    """Log an exception and raise the appropriate domain exception.
    
    Args:
        logger: Logger to use for error logging
        exception: The original exception that occurred
        domain_exception_class: Domain exception class to raise
        operation_name: Human-readable name of the operation that failed
        custom_message: Custom message for the domain exception (defaults to operation_name)
        **context: Additional context fields for structured logging
        
    Raises:
        An instance of domain_exception_class with appropriate message and cause
    """
    logger.error(f"{operation_name} failed", extra={
        "operation": operation_name,
        "original_exception": type(exception).__name__,
        "exception_message": str(exception),
        **context
    })
    
    message = custom_message or f"{operation_name} failed: {exception}"
    raise domain_exception_class(message) from exception


def log_operation_success(
    logger: logging.Logger, 
    operation_name: str, 
    **context: Any
) -> None:
    """Log successful completion of an operation with structured context.
    
    Args:
        logger: Logger to use for success logging
        operation_name: Human-readable name of the operation that succeeded
        **context: Additional context fields for structured logging
    """
    logger.info(f"{operation_name} completed successfully", extra={
        "operation": operation_name,
        "status": "success",
        **context
    })


def with_error_context(operation_name: str, **context: Any) -> dict[str, Any]:
    """Create a consistent error context dictionary for logging.
    
    Args:
        operation_name: Human-readable name of the operation
        **context: Additional context fields
        
    Returns:
        Dictionary with standard error context fields
    """
    return {
        "operation": operation_name,
        **context
    }