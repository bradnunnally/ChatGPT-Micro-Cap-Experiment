"""Centralized retry utilities for handling transient failures with exponential backoff."""

from __future__ import annotations

import random
import time
from functools import wraps
from typing import Any, Callable, Optional, TypeVar

T = TypeVar('T')


def exponential_backoff_retry(
    attempts: int = 3,
    base_delay: float = 0.3,
    max_delay: float = 60.0,
    jitter: bool = False,
    jitter_range: float = 0.2,
    retry_on_403: bool = False,
) -> Callable[[Callable[..., T]], Callable[..., Optional[T]]]:
    """Decorator for retry logic with exponential backoff.
    
    Args:
        attempts: Maximum number of retry attempts
        base_delay: Base delay in seconds between retries
        max_delay: Maximum delay cap in seconds
        jitter: Whether to add random jitter to delay
        jitter_range: Jitter range as fraction (e.g., 0.2 = ±20%)
        retry_on_403: Whether to retry on 403 Forbidden errors
        
    Returns:
        Decorated function that returns None on final failure
    """
    def decorator(func: Callable[..., T]) -> Callable[..., Optional[T]]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Optional[T]:
            return retry_with_backoff(
                lambda: func(*args, **kwargs),
                attempts=attempts,
                base_delay=base_delay,
                max_delay=max_delay,
                jitter=jitter,
                jitter_range=jitter_range,
                retry_on_403=retry_on_403,
            )
        return wrapper
    return decorator


def retry_with_backoff(
    func: Callable[[], T],
    attempts: int = 3,
    base_delay: float = 0.3,
    max_delay: float = 60.0,
    jitter: bool = False,
    jitter_range: float = 0.2,
    retry_on_403: bool = False,
) -> Optional[T]:
    """Execute function with exponential backoff retry.
    
    Args:
        func: Function to execute (should take no arguments)
        attempts: Maximum number of retry attempts
        base_delay: Base delay in seconds between retries  
        max_delay: Maximum delay cap in seconds
        jitter: Whether to add random jitter to delay
        jitter_range: Jitter range as fraction (e.g., 0.2 = ±20%)
        retry_on_403: Whether to retry on 403 Forbidden errors
        
    Returns:
        Function result on success, None on final failure
    """
    last_err: Optional[Exception] = None
    
    for i in range(attempts):
        try:
            return func()
        except Exception as e:
            last_err = e
            msg = str(e)
            
            # Check for specific error conditions
            is_429 = "429" in msg or "Too Many Requests" in msg.lower()
            is_403 = "403" in msg or "forbidden" in msg.lower() or "access" in msg.lower()
            
            # Don't retry on 403 unless explicitly requested
            if is_403 and not retry_on_403:
                break
                
            # Don't retry on final attempt or non-retryable errors
            if i == attempts - 1:
                break
            
            # Calculate delay with exponential backoff
            delay = base_delay * (2 ** i)
            delay = min(delay, max_delay)
            
            # Add jitter if requested
            if jitter:
                jitter_amount = delay * jitter_range * random.uniform(-1, 1)
                delay = max(0.1, delay + jitter_amount)
            
            time.sleep(delay)
    
    return None


def retry_with_exception_propagation(
    func: Callable[[], T],
    attempts: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 60.0,
    jitter: bool = True,
    jitter_range: float = 0.2,
    retry_on_403: bool = False,
) -> T:
    """Execute function with retry, propagating the last exception on failure.
    
    This version raises the last encountered exception instead of returning None,
    which is useful for cases where you need to handle specific error types.
    
    Args:
        func: Function to execute (should take no arguments)
        attempts: Maximum number of retry attempts
        base_delay: Base delay in seconds between retries
        max_delay: Maximum delay cap in seconds
        jitter: Whether to add random jitter to delay
        jitter_range: Jitter range as fraction (e.g., 0.2 = ±20%)
        retry_on_403: Whether to retry on 403 Forbidden errors
        
    Returns:
        Function result on success
        
    Raises:
        Last encountered exception on final failure
    """
    last_err: Optional[Exception] = None
    
    for i in range(attempts):
        try:
            return func()
        except Exception as e:
            last_err = e
            msg = str(e)
            
            # Check for specific error conditions
            is_429 = "429" in msg or "Too Many Requests" in msg.lower()
            is_403 = "403" in msg or "forbidden" in msg.lower() or "access" in msg.lower()
            
            # Don't retry on 403 unless explicitly requested
            if is_403 and not retry_on_403:
                break
                
            # Don't retry on final attempt
            if i == attempts - 1:
                break
            
            # Calculate delay with exponential backoff
            delay = base_delay * (2 ** i)
            delay = min(delay, max_delay)
            
            # Add jitter if requested
            if jitter:
                jitter_amount = delay * jitter_range * random.uniform(-1, 1)
                delay = max(0.1, delay + jitter_amount)
            
            time.sleep(delay)
    
    # Propagate the last exception
    if last_err:
        raise last_err
    raise RuntimeError("Retry function failed without exception")