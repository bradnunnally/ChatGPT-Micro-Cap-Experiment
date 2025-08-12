import pandas as pd
from unittest.mock import patch, MagicMock

from data.portfolio import save_portfolio_snapshot


def _portfolio_df():
    return pd.DataFrame({
        "ticker": ["AAPL", "MSFT"],
        "shares": [10, 5],
        "stop_loss": [90.0, 180.0],
        "buy_price": [100.0, 200.0],
        "cost_basis": [1000.0, 1000.0],
    })

@patch("data.portfolio.get_connection")
@patch("data.portfolio.init_db")
@patch("data.portfolio.fetch_prices")
@patch("services.market.get_current_price")
@patch("services.manual_pricing.get_manual_price")
def test_snapshot_individual_then_manual_fallback(mock_manual, mock_get_price, mock_fetch_prices, mock_init_db, mock_get_conn):
    # Bulk fetch returns DataFrame but zeros -> triggers individual fallback
    mock_fetch_prices.return_value = pd.DataFrame({"ticker": ["AAPL", "MSFT"], "current_price": [0.0, 0.0]})
    mock_get_conn.return_value.__enter__.return_value = MagicMock()
    # Manual price only for MSFT
    mock_manual.side_effect = lambda t: 250.0 if t == "MSFT" else None
    # API individual price only for AAPL
    mock_get_price.side_effect = lambda t: 120.0 if t == "AAPL" else None

    result = save_portfolio_snapshot(_portfolio_df(), 500.0)
    aapl = result[result["ticker"] == "AAPL"].iloc[0]
    msft = result[result["ticker"] == "MSFT"].iloc[0]
    assert aapl["current_price"] == 120.0
    assert msft["current_price"] == 250.0

@patch("data.portfolio.get_connection")
@patch("data.portfolio.init_db")
@patch("data.portfolio.fetch_prices")
@patch("services.market.get_current_price")
@patch("services.manual_pricing.get_manual_price")
def test_snapshot_bulk_empty_skips_individual(mock_manual, mock_get_price, mock_fetch_prices, mock_init_db, mock_get_conn):
    # Bulk fetch returns empty -> should NOT attempt individual fallback
    mock_fetch_prices.return_value = pd.DataFrame()
    mock_get_conn.return_value.__enter__.return_value = MagicMock()

    result = save_portfolio_snapshot(_portfolio_df(), 0.0)
    # All current prices should be 0.0
    assert set(result[result["ticker"].isin(["AAPL","MSFT"] )]["current_price"]) == {0.0}
    mock_manual.assert_not_called()
    mock_get_price.assert_not_called()
