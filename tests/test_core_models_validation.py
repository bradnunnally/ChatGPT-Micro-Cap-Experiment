import pytest
from datetime import date, datetime
from decimal import Decimal

from services.core.models import Position, Trade, PortfolioSnapshot
from services.core.validation import validate_price, validate_shares, validate_ticker
from services.exceptions.validation import ValidationError


class TestValidationFunctions:
    def test_validate_ticker_valid(self):
        # Accepts standard, with dot, and alphanumeric
        for t in ["AAPL", "BRK.B", "MSFT1"]:
            validate_ticker(t)

    def test_validate_ticker_invalid(self):
        for t in ["", "123", "AAPL!", "TOOLONGSYMBL"]:
            with pytest.raises(ValidationError):
                validate_ticker(t)

    def test_validate_shares_valid(self):
        validate_shares(1)
        validate_shares(100)

    def test_validate_shares_invalid(self):
        for s in [0, -1]:
            with pytest.raises(ValidationError):
                validate_shares(s)
        with pytest.raises(ValidationError):
            validate_shares(1.5)  # type: ignore[arg-type]

    def test_validate_price_valid(self):
        validate_price(Decimal("1.00"))
        validate_price(Decimal("0.01"))

    def test_validate_price_invalid(self):
        for p in [Decimal("0"), Decimal("-1")]:
            with pytest.raises(ValidationError):
                validate_price(p)
        with pytest.raises(ValidationError):
            validate_price(1.0)  # type: ignore[arg-type]


class TestModels:
    def test_position_valid(self):
        pos = Position(
            ticker="AAPL",
            shares=10,
            buy_price=Decimal("150.00"),
            stop_loss=Decimal("0"),  # allowed
            cost_basis=Decimal("150.00"),
            timestamp=datetime.now(),
        )
        assert pos.ticker == "AAPL"
        assert pos.shares == 10
        assert pos.buy_price == Decimal("150.00")

    def test_position_invalid(self):
        with pytest.raises(ValidationError):
            Position(
                ticker="123",  # invalid
                shares=10,
                buy_price=Decimal("150.00"),
                stop_loss=Decimal("0"),
                cost_basis=Decimal("150.00"),
            )
        with pytest.raises(ValidationError):
            Position(
                ticker="AAPL",
                shares=0,  # invalid
                buy_price=Decimal("150.00"),
                stop_loss=Decimal("0"),
                cost_basis=Decimal("150.00"),
            )
        with pytest.raises(ValidationError):
            Position(
                ticker="AAPL",
                shares=10,
                buy_price=Decimal("0"),  # invalid
                stop_loss=Decimal("0"),
                cost_basis=Decimal("150.00"),
            )

    def test_trade_valid(self):
        tr = Trade(
            ticker="MSFT",
            side="BUY",
            shares=5,
            price=Decimal("320.10"),
            timestamp=datetime.now(),
        )
        assert tr.ticker == "MSFT"
        assert tr.side == "BUY"

    def test_trade_invalid(self):
        with pytest.raises(ValidationError):
            Trade(
                ticker="MSFT!",  # invalid
                side="SELL",
                shares=5,
                price=Decimal("320.10"),
                timestamp=datetime.now(),
            )
        with pytest.raises(ValidationError):
            Trade(
                ticker="MSFT",
                side="SELL",
                shares=0,  # invalid
                price=Decimal("320.10"),
                timestamp=datetime.now(),
            )
        with pytest.raises(ValidationError):
            Trade(
                ticker="MSFT",
                side="SELL",
                shares=5,
                price=Decimal("0"),  # invalid
                timestamp=datetime.now(),
            )

    def test_snapshot_valid(self):
        snap = PortfolioSnapshot(
            date=date.today(),
            ticker="AAPL",
            shares=10,
            cost_basis=Decimal("150.00"),
            stop_loss=Decimal("0"),  # allowed
            current_price=Decimal("160.00"),
            total_value=Decimal("1600.00"),
            pnl=Decimal("100.00"),
            action="HOLD",
            cash_balance=Decimal("900.00"),
            total_equity=Decimal("2500.00"),
        )
        assert snap.ticker == "AAPL"
        assert snap.total_value == Decimal("1600.00")

    def test_snapshot_invalid(self):
        with pytest.raises(ValidationError):
            PortfolioSnapshot(
                date=date.today(),
                ticker="AAPL",
                shares=10,
                cost_basis=Decimal("0"),  # invalid
                stop_loss=Decimal("0"),
                current_price=Decimal("160.00"),
                total_value=Decimal("1600.00"),
                pnl=Decimal("100.00"),
                action="HOLD",
                cash_balance=Decimal("900.00"),
                total_equity=Decimal("2500.00"),
            )
