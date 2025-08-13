import pandas as pd
from unittest.mock import patch, MagicMock

from data.portfolio import load_portfolio

@patch("data.portfolio.get_connection")
@patch("data.portfolio.init_db")
@patch("data.portfolio.fetch_prices")
@patch("services.market.get_current_price")
def test_load_portfolio_individual_price_fallback(mock_get_current_price, mock_fetch_prices, mock_init_db, mock_get_conn):
    # Mock DB portfolio rows
    mock_conn = MagicMock()
    mock_get_conn.return_value.__enter__.return_value = mock_conn
    # Simulate read_sql_query fallback path raising then alternative cursor path returning rows
    with patch("pandas.read_sql_query", side_effect=Exception("boom")):
        # Cursor returns two rows
        mock_conn.execute.return_value.fetchall.return_value = [
            ("AAPL", 10, 90.0, 100.0, 1000.0),
            ("MSFT", 5, 180.0, 200.0, 1000.0),
        ]
        # Cash row
        mock_conn.execute.return_value.fetchone.return_value = [500.0]
        # Bulk fetch returns empty -> triggers individual fallback
        mock_fetch_prices.return_value = pd.DataFrame(columns=["ticker", "current_price", "pct_change"])
        # Individual prices: only one succeeds
        def _price(t):
            return 120.0 if t == "AAPL" else None
        mock_get_current_price.side_effect = _price

        portfolio, cash, is_first_time = load_portfolio()
        assert cash == 500.0
        assert is_first_time is False
        assert "current_price" in portfolio.columns
        aapl = portfolio[portfolio["ticker"]=="AAPL"].iloc[0]
        msft = portfolio[portfolio["ticker"]=="MSFT"].iloc[0]
        assert aapl["current_price"] == 120.0
        assert msft["current_price"] == 0.0
