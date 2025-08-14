from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP, getcontext
from typing import Any, Union

getcontext().prec = 28

Number = Union[int, float, Decimal, "Money"]
TWOPLACES = Decimal("0.01")


@dataclass(frozen=True)
class Money:
    """Value object for currency-safe arithmetic & formatting."""

    value: Decimal

    # --- factories ---
    @classmethod
    def from_raw(cls, v: Any) -> "Money":
        if isinstance(v, Money):
            return v
        if isinstance(v, Decimal):
            return cls(v)
        return cls(Decimal(str(v)))

    # --- arithmetic (closed) ---
    def _op(self, other: Any, fn) -> "Money":
        o = Money.from_raw(other)
        return Money(fn(self.value, o.value))

    def __add__(self, other: Any) -> "Money":  # pragma: no cover - simple delegate
        return self._op(other, lambda a, b: a + b)

    def __sub__(self, other: Any) -> "Money":  # pragma: no cover
        return self._op(other, lambda a, b: a - b)

    def __mul__(self, other: Any) -> "Money":  # pragma: no cover
        return self._op(other, lambda a, b: a * b)

    # --- utilities ---
    def quantize(self) -> "Money":
        return Money(self.value.quantize(TWOPLACES, rounding=ROUND_HALF_UP))

    def to_float(self) -> float:
        return float(self.value)

    def __str__(self) -> str:  # pragma: no cover - formatting exercised indirectly
        return f"{self.quantize().value:.2f}"


def format_money(value: Number, with_symbol: bool = True) -> str:
    try:
        m = Money.from_raw(value).quantize()
        return f"${m.value:.2f}" if with_symbol else f"{m.value:.2f}"
    except Exception:  # pragma: no cover - defensive fallback
        if isinstance(value, (int, float)):
            return f"${value:.2f}" if with_symbol else f"{value:.2f}"
        return str(value)
