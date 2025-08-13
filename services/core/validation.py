"""Centralized validation functions for tickers, shares, and prices.

These are simple, focused validators designed to be used both by the UI
and by immutable dataclass models in services.core.models.
"""

from __future__ import annotations

import re
from decimal import Decimal

from services.exceptions.validation import ValidationError

_TICKER_RE = re.compile(r"^[A-Z][A-Z0-9\.]{0,9}$")


def validate_ticker(ticker: str) -> None:
    if not isinstance(ticker, str):
        raise ValidationError("Ticker must be a string.")
    t = ticker.strip().upper()
    if not _TICKER_RE.match(t):
        raise ValidationError("Invalid ticker format.")


def validate_shares(shares: int) -> None:
    if not isinstance(shares, int):
        raise ValidationError("Shares must be an integer.")
    if shares <= 0:
        raise ValidationError("Shares must be positive.")


def validate_price(price: Decimal) -> None:
    if not isinstance(price, Decimal):
        raise ValidationError("Price must be a Decimal.")
    if price <= Decimal("0"):
        raise ValidationError("Price must be positive.")
