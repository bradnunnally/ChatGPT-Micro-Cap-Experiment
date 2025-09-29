"""Consolidated validation utilities for the trading application.

This module provides unified validation functions with multiple return types
to support different usage patterns across the application.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any, Optional, Tuple, Union

from core.errors import ValidationError
from core.constants import ERROR_MESSAGES, MAX_SHARES, MAX_PRICE, MAX_TICKER_LENGTH

# Ticker format regex - accepts 1-10 characters, starting with letter, may include dots
_TICKER_RE = re.compile(r"^[A-Z][A-Z0-9\.]{0,9}$")

# More restrictive ticker regex for basic format validation (used by tests)
_BASIC_TICKER_RE = re.compile(r"^[A-Z]{1,5}(\.[A-Z]{1,2})?$")


class ValidationResult:
    """Validation result with success/failure and optional error message."""
    
    def __init__(self, valid: bool, error_message: Optional[str] = None):
        self.valid = valid
        self.error_message = error_message
    
    def __bool__(self) -> bool:
        return self.valid
    
    def __repr__(self) -> str:
        if self.valid:
            return "ValidationResult(valid=True)"
        return f"ValidationResult(valid=False, error='{self.error_message}')"


def validate_ticker(ticker: str, strict: bool = True) -> None:
    """Validate ticker symbol format (exception-raising version).
    
    Args:
        ticker: Ticker symbol to validate
        strict: If True, use comprehensive regex. If False, use basic format only.
        
    Raises:
        ValidationError: If ticker format is invalid
    """
    if not isinstance(ticker, str):
        raise ValidationError("Ticker must be a string.")
    
    t = ticker.strip().upper()
    if not t:
        raise ValidationError(ERROR_MESSAGES["EMPTY_TICKER"])
    
    if len(t) > MAX_TICKER_LENGTH:
        raise ValidationError(ERROR_MESSAGES["TICKER_TOO_LONG"])
    
    pattern = _TICKER_RE if strict else _BASIC_TICKER_RE
    if not pattern.match(t):
        raise ValidationError(ERROR_MESSAGES["INVALID_TICKER"])


def validate_ticker_format(ticker: str, strict: bool = True) -> bool:
    """Validate ticker symbol format (boolean return version).
    
    Args:
        ticker: Ticker symbol to validate
        strict: If True, use comprehensive regex. If False, use basic format only.
        
    Returns:
        True if ticker format is valid, False otherwise
    """
    try:
        validate_ticker(ticker, strict=strict)
        return True
    except ValidationError:
        return False


def validate_ticker_with_message(ticker: str, strict: bool = True) -> ValidationResult:
    """Validate ticker symbol format (result object version).
    
    Args:
        ticker: Ticker symbol to validate
        strict: If True, use comprehensive regex. If False, use basic format only.
        
    Returns:
        ValidationResult with success status and optional error message
    """
    try:
        validate_ticker(ticker, strict=strict)
        return ValidationResult(True)
    except ValidationError as e:
        return ValidationResult(False, str(e))


def validate_shares(shares: Union[int, float]) -> None:
    """Validate share quantity (exception-raising version).
    
    Args:
        shares: Number of shares to validate
        
    Raises:
        ValidationError: If shares are invalid
    """
    if not isinstance(shares, (int, float)):
        raise ValidationError("Shares must be a number.")
    
    if not isinstance(shares, int):
        if not shares.is_integer():
            raise ValidationError("Shares must be a whole number.")
        shares = int(shares)
    
    if shares <= 0:
        raise ValidationError(ERROR_MESSAGES["INVALID_SHARES"])
    
    if shares > MAX_SHARES:
        raise ValidationError(ERROR_MESSAGES["SHARES_TOO_LARGE"])


def validate_shares_format(shares: Union[int, float]) -> bool:
    """Validate share quantity (boolean return version).
    
    Args:
        shares: Number of shares to validate
        
    Returns:
        True if shares are valid, False otherwise
    """
    try:
        validate_shares(shares)
        return True
    except ValidationError:
        return False


def validate_shares_with_message(shares: Union[int, float]) -> ValidationResult:
    """Validate share quantity (result object version).
    
    Args:
        shares: Number of shares to validate
        
    Returns:
        ValidationResult with success status and optional error message
    """
    try:
        validate_shares(shares)
        return ValidationResult(True)
    except ValidationError as e:
        return ValidationResult(False, str(e))


def validate_price(price: Union[Decimal, float, int, str]) -> None:
    """Validate price value (exception-raising version).
    
    Args:
        price: Price value to validate (will be converted to Decimal)
        
    Raises:
        ValidationError: If price is invalid
    """
    try:
        if isinstance(price, str):
            price_decimal = Decimal(price)
        elif isinstance(price, (int, float)):
            price_decimal = Decimal(str(price))
        elif isinstance(price, Decimal):
            price_decimal = price
        else:
            raise ValidationError("Price must be a number or numeric string.")
    except (InvalidOperation, ValueError):
        raise ValidationError("Price must be a valid number.")
    
    if price_decimal <= Decimal("0"):
        raise ValidationError(ERROR_MESSAGES["INVALID_PRICE"])
    
    if price_decimal > Decimal(str(MAX_PRICE)):
        raise ValidationError(ERROR_MESSAGES["PRICE_TOO_HIGH"])


def validate_price_format(price: Union[Decimal, float, int, str]) -> bool:
    """Validate price value (boolean return version).
    
    Args:
        price: Price value to validate
        
    Returns:
        True if price is valid, False otherwise
    """
    try:
        validate_price(price)
        return True
    except ValidationError:
        return False


def validate_price_with_message(price: Union[Decimal, float, int, str]) -> ValidationResult:
    """Validate price value (result object version).
    
    Args:
        price: Price value to validate
        
    Returns:
        ValidationResult with success status and optional error message
    """
    try:
        validate_price(price)
        return ValidationResult(True)
    except ValidationError as e:
        return ValidationResult(False, str(e))


# Legacy compatibility functions
def is_valid_price(value: Any) -> bool:
    """Check if value is a valid positive price (legacy compatibility).
    
    Args:
        value: Value to check
        
    Returns:
        True if value is a positive number, False otherwise
    """
    return isinstance(value, (int, float)) and value > 0


def validate_price_data(value: Any) -> bool:
    """Backward compatible name for is_valid_price.
    
    Args:
        value: Value to check
        
    Returns:
        True if value is a positive number, False otherwise
    """
    return is_valid_price(value)


# Tuple-returning versions for compatibility with ValidationService
def validate_ticker_tuple(ticker: str, strict: bool = True) -> Tuple[bool, Optional[str]]:
    """Validate ticker format returning tuple (compatibility version).
    
    Args:
        ticker: Ticker symbol to validate
        strict: If True, use comprehensive regex. If False, use basic format only.
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    result = validate_ticker_with_message(ticker, strict=strict)
    return result.valid, result.error_message


def validate_shares_tuple(shares: Union[int, float]) -> Tuple[bool, Optional[str]]:
    """Validate shares returning tuple (compatibility version).
    
    Args:
        shares: Number of shares to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    result = validate_shares_with_message(shares)
    return result.valid, result.error_message


def validate_price_tuple(price: Union[Decimal, float, int, str]) -> Tuple[bool, Optional[str]]:
    """Validate price returning tuple (compatibility version).
    
    Args:
        price: Price value to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    result = validate_price_with_message(price)
    return result.valid, result.error_message