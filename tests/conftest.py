import pytest
import sqlite3
from contextlib import suppress
import pandas as pd
from tests.mock_streamlit import StreamlitMock


@pytest.fixture(autouse=True)
def cleanup_db():
    """Clean up any database connections."""
    yield
    # Close any connections without accessing private attributes
    with suppress(Exception):
        conn = sqlite3.connect(":memory:")
        conn.close()


@pytest.fixture
def mock_streamlit():
    """Create streamlit mock with session state."""
    return StreamlitMock()


@pytest.fixture
def mock_portfolio_data():
    """Create sample portfolio data with all required columns."""
    return pd.DataFrame(
        {
            "ticker": ["AAPL", "MSFT"],
            "shares": [100, 50],
            "price": [150.0, 200.0],
            "buy_price": [140.0, 190.0],
            "cost_basis": [14000.0, 9500.0],
            "market_value": [15000.0, 10000.0],
            "stop_loss": [135.0, 180.0],
            "Return %": [7.14, 5.26],
        }
    )


## Removed legacy yfinance fixture after migration to Finnhub/Synthetic providers.
