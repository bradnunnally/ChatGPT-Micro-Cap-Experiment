"""Validation service using consolidated validation logic.

NOTE: This module now uses core.validation for consistency while 
maintaining the same API for backward compatibility.
"""

from typing import Optional, Tuple

from core.validation import (
    validate_ticker_tuple,
    validate_shares_tuple, 
    validate_price_tuple,
)


class ValidationService:
    @staticmethod
    def validate_ticker(ticker: str) -> Tuple[bool, Optional[str]]:
        """Validate ticker symbol format."""
        return validate_ticker_tuple(ticker, strict=False)  # Use basic validation for compatibility

    @staticmethod
    def validate_shares(shares: int) -> Tuple[bool, Optional[str]]:
        """Validate share quantity."""
        return validate_shares_tuple(shares)

    @staticmethod
    def validate_price(price: float) -> Tuple[bool, Optional[str]]:
        """Validate stock price."""
        return validate_price_tuple(price)
