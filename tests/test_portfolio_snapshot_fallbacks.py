import os
import pandas as pd
from datetime import datetime
import data.portfolio as portfolio_mod
from config import COL_TICKER, COL_SHARES, COL_STOP, COL_PRICE, COL_COST, TODAY


def test_save_portfolio_snapshot_individual_fallback(monkeypatch, tmp_path):
    # Prepare portfolio with two tickers
    portfolio_df = pd.DataFrame({
        COL_TICKER: ['AAA', 'BBB'],
        COL_SHARES: [10, 20],
        COL_STOP: [0.0, 0.0],
        COL_PRICE: [5.0, 7.0],
        COL_COST: [50.0, 140.0],
    })

    # Mock fetch_prices to return DataFrame with zeros (non-empty) -> triggers individual path
    def fake_fetch_prices(tickers):  # noqa: D401
        return pd.DataFrame({'ticker': tickers, 'current_price': [0.0 for _ in tickers], 'pct_change': [0.0 for _ in tickers]})

    # Mock manual pricing to provide one override
    def fake_get_manual_price(t):  # noqa: D401
        return 9.99 if t == 'AAA' else None

    # Mock get_current_price to provide price for BBB
    def fake_get_current_price(t):  # noqa: D401
        return 8.88 if t == 'BBB' else None

    monkeypatch.setenv('APP_ENV', 'production')

    # Monkeypatch the symbol imported in data.portfolio module
    monkeypatch.setattr(portfolio_mod, 'fetch_prices', fake_fetch_prices)
    import services.market as market_mod
    monkeypatch.setattr(market_mod, 'get_current_price', fake_get_current_price)

    import services.manual_pricing as manual_mod
    monkeypatch.setattr(manual_mod, 'get_manual_price', fake_get_manual_price)

    # Execute snapshot
    snapshot = portfolio_mod.save_portfolio_snapshot(portfolio_df, cash=100.0)

    # Verify prices applied via manual and API fallback
    rows = {row['ticker']: row for _, row in snapshot.iterrows()}
    assert rows['AAA']['current_price'] == 9.99
    assert rows['BBB']['current_price'] == 8.88

    # Ensure total equity reflects updated prices
    # At least one row should show positive total_equity after applying prices
    positive_equities = [
        float(v) for v in snapshot['total_equity'].tolist() if str(v).replace('.', '', 1).isdigit()
    ]
    assert any(val > 0 for val in positive_equities)
