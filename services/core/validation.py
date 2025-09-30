"""Centralized validation functions for tickers, shares, and prices.

These are simple, focused validators designed to be used both by the UI
and by immutable dataclass models in services.core.models.

NOTE: This module now re-exports functions from core.validation for 
backward compatibility while consolidating validation logic.
"""

from __future__ import annotations

# Re-export consolidated validation functions
from core.validation import (
    validate_ticker,
    validate_shares,
    validate_price,
    ValidationResult,
)
