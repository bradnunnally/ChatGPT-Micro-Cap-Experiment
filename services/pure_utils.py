"""Pure utility helpers extracted from service modules for easier unit testing."""
from __future__ import annotations
from dataclasses import dataclass


def within_range(value: float, low: float | None, high: float | None) -> bool:
    if low is None or high is None:
        return True
    return low <= value <= high


def compute_cost(shares: float, price: float) -> float:
    return float(shares) * float(price)


@dataclass(slots=True)
class PriceValidationResult:
    valid: bool
    reason: str | None = None


def validate_buy_price(price: float, day_low: float | None, day_high: float | None) -> PriceValidationResult:
    if day_low is None or day_high is None:
        return PriceValidationResult(True)
    if day_low <= price <= day_high:
        return PriceValidationResult(True)
    return PriceValidationResult(False, f"Price outside today's range {day_low:.2f}-{day_high:.2f}")
