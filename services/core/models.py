"""Strongly-typed, immutable core models.

These models use Decimal for all monetary values to avoid floating-point
rounding issues and are validated at construction time using centralized
validators in ``services.core.validation``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional

from services.core.validation import validate_price, validate_shares, validate_ticker


@dataclass(frozen=True, slots=True)
class Position:
    ticker: str
    shares: int
    buy_price: Decimal
    stop_loss: Decimal
    cost_basis: Decimal
    timestamp: Optional[datetime] = None

    def __post_init__(self) -> None:
        validate_ticker(self.ticker)
        validate_shares(self.shares)
        validate_price(self.buy_price)
        # stop_loss may be zero (not set) or a valid positive price
        if self.stop_loss != Decimal("0"):
            validate_price(self.stop_loss)
        validate_price(self.cost_basis)


TradeSide = Literal["BUY", "SELL"]


@dataclass(frozen=True, slots=True)
class Trade:
    ticker: str
    side: TradeSide
    shares: int
    price: Decimal
    timestamp: datetime

    def __post_init__(self) -> None:
        validate_ticker(self.ticker)
        validate_shares(self.shares)
        validate_price(self.price)


@dataclass(frozen=True, slots=True)
class PortfolioSnapshot:
    date: date
    ticker: str
    shares: int
    cost_basis: Decimal
    stop_loss: Decimal
    current_price: Decimal
    total_value: Decimal
    pnl: Decimal
    action: str
    cash_balance: Decimal
    total_equity: Decimal

    def __post_init__(self) -> None:
        validate_ticker(self.ticker)
        validate_shares(self.shares)
        for value in (
            self.cost_basis,
            self.stop_loss,
            self.current_price,
            self.total_value,
            self.pnl,
            self.cash_balance,
            self.total_equity,
        ):
            # stop_loss may be 0 per usage; treat zero as allowed
            if value is self.stop_loss and value == Decimal("0"):
                continue
            validate_price(value)
