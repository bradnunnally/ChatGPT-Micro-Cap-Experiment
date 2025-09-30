"""Pure utility helpers extracted from service modules for easier unit testing."""
from __future__ import annotations
from dataclasses import dataclass


def _safe_cast(value: float | int | None) -> float | None:
    try:
        return float(value) if value is not None else None
    except Exception:  # pragma: no cover - defensive
        return None


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
    low = _safe_cast(day_low)
    high = _safe_cast(day_high)
    if low is None or high is None:
        return PriceValidationResult(True)
    if high < low:
        low, high = high, low

    try:
        price_val = float(price)
    except Exception:
        return PriceValidationResult(False, "Invalid price value")

    tolerance = max(0.05 * max(price_val, high), 0.25)
    if (low - tolerance) <= price_val <= (high + tolerance):
        return PriceValidationResult(True)

    if price_val > 0 and low > 0:
        largest = max(price_val, high)
        smallest = min(price_val, low)
        if smallest > 0 and largest / smallest >= 25:
            note = (
                "Provider range appears stale; proceeding with manual price "
                f"(provider range {low:.2f}-{high:.2f})."
            )
            return PriceValidationResult(True, note)

    return PriceValidationResult(
        False,
        f"Price outside today's range {low:.2f}-{high:.2f}",
    )
