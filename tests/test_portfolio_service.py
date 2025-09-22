import pytest
from services.core.portfolio_service import PortfolioService, Position


def test_add_position():
    """Test adding a position to portfolio."""
    service = PortfolioService()
    position = Position(ticker="AAPL", shares=100, price=150.0, cost_basis=14000.0)

    service.add_position(position)
    df = service.to_dataframe()

    assert len(df) == 1
    assert df.iloc[0]["ticker"] == "AAPL"
    assert df.iloc[0]["shares"] == 100


def test_add_position_merges_existing_ticker():
    """Repeat buys should accumulate shares and cost basis instead of overwriting."""
    service = PortfolioService()
    service.add_position(Position("AAPL", 100, 150.0, 14000.0, stop_loss=120.0))
    service.add_position(Position("AAPL", 50, 155.0, 8000.0))

    df = service.to_dataframe()

    assert len(df) == 1
    assert df.iloc[0]["ticker"] == "AAPL"
    assert df.iloc[0]["shares"] == 150
    assert df.iloc[0]["cost_basis"] == 22000.0
    assert df.iloc[0]["price"] == 155.0
    assert df.iloc[0]["stop_loss"] == 120.0

    metrics = service.get_metrics()

    expected_total_value = 150 * 155.0
    expected_gain = expected_total_value - 22000.0

    assert metrics.total_value == expected_total_value
    assert metrics.total_gain == expected_gain
    assert metrics.holdings_count == 1


def test_portfolio_metrics():
    """Test portfolio metrics calculation."""
    service = PortfolioService()

    service.add_position(Position("AAPL", 100, 150.0, 14000.0))
    service.add_position(Position("MSFT", 50, 200.0, 9500.0))

    metrics = service.get_metrics()

    assert metrics.total_value == 25000.0  # (100 * 150) + (50 * 200)
    assert metrics.total_gain == 1500.0  # 25000 - 23500
    assert metrics.holdings_count == 2
    assert abs(metrics.total_return - 0.0638) < 0.001  # ~6.38%


def test_empty_portfolio():
    """Test metrics with empty portfolio."""
    service = PortfolioService()
    metrics = service.get_metrics()

    assert metrics.total_value == 0
    assert metrics.total_gain == 0
    assert metrics.total_return == 0
    assert metrics.holdings_count == 0


def test_remove_position():
    """Test removing a position."""
    service = PortfolioService()
    service.add_position(Position("AAPL", 100, 150.0, 14000.0))
    service.add_position(Position("MSFT", 50, 200.0, 9500.0))

    service.remove_position("AAPL")
    df = service.to_dataframe()

    assert len(df) == 1
    assert df.iloc[0]["ticker"] == "MSFT"
