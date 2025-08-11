import pytest
import pandas as pd
from services.core.portfolio_service import PortfolioService, Position, PortfolioMetrics
from services.core.validation_service import ValidationService


def test_portfolio_service_basic():
    """Test basic portfolio service functionality."""
    service = PortfolioService()

    # Test empty portfolio
    metrics = service.get_metrics()
    assert metrics.total_value == 0
    assert metrics.holdings_count == 0

    # Test adding position
    position = Position(ticker="AAPL", shares=100, price=150.0, cost_basis=14000.0)
    service.add_position(position)

    # Test metrics after adding position
    metrics = service.get_metrics()
    assert metrics.total_value == 15000.0  # 100 * 150
    assert metrics.total_gain == 1000.0  # 15000 - 14000
    assert metrics.holdings_count == 1


def test_portfolio_dataframe():
    """Test portfolio to DataFrame conversion."""
    service = PortfolioService()

    # Test empty DataFrame
    df = service.to_dataframe()
    assert df.empty
    assert "ticker" in df.columns

    # Test with data
    service.add_position(Position("AAPL", 100, 150.0, 14000.0))
    df = service.to_dataframe()

    assert len(df) == 1
    assert df.iloc[0]["ticker"] == "AAPL"
    assert df.iloc[0]["shares"] == 100


def test_validation_service():
    """Test validation service methods."""
    # Test ticker validation
    valid, error = ValidationService.validate_ticker("AAPL")
    assert valid is True
    assert error is None

    valid, error = ValidationService.validate_ticker("")
    assert valid is False
    assert "empty" in error

    # Test shares validation
    valid, error = ValidationService.validate_shares(100)
    assert valid is True
    assert error is None

    valid, error = ValidationService.validate_shares(-10)
    assert valid is False
    assert "positive" in error

    # Test price validation
    valid, error = ValidationService.validate_price(150.0)
    assert valid is True
    assert error is None

    valid, error = ValidationService.validate_price(-10.0)
    assert valid is False
    assert "positive" in error
