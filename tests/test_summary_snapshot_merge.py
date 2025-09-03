import pandas as pd
from datetime import datetime

from ui.summary import history_to_portfolio_snapshot


def _make_history_df():
    # Create history with TOTAL and two tickers with shares/costs
    rows = [
        {"date": pd.Timestamp("2025-02-01"), "ticker": "AAA", "shares": 100, "cost_basis": 5.0, "current_price": 6.0, "total_value": 600.0, "pnl": 100.0, "cash_balance": 1000.0, "total_equity": 1600.0},
        {"date": pd.Timestamp("2025-02-01"), "ticker": "BBB", "shares": 50, "cost_basis": 8.0, "current_price": 9.0, "total_value": 450.0, "pnl": 50.0, "cash_balance": "", "total_equity": ""},
        {"date": pd.Timestamp("2025-02-01"), "ticker": "TOTAL", "shares": "", "cost_basis": "", "current_price": "", "total_value": 1050.0, "pnl": 150.0, "cash_balance": 1000.0, "total_equity": 2050.0},
    ]
    return pd.DataFrame(rows)


def test_history_to_snapshot_includes_shares_and_costs():
    hist = _make_history_df()
    snap = history_to_portfolio_snapshot(hist, as_of_months=12)
    assert not snap.empty
    # Expect rows for AAA, BBB, TOTAL
    tickers = set(snap["Ticker"].tolist())
    assert {"AAA", "BBB", "TOTAL"}.issubset(tickers)
    aaa = snap[snap["Ticker"] == "AAA"].iloc[0]
    assert aaa["Shares"] == 100
    assert aaa["Cost Basis"] == 5.0
