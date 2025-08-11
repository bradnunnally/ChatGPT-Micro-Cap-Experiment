import pandas as pd
import pytest

from services.core.portfolio_service import (
    apply_buy,
    apply_sell,
    calculate_pnl,
    calculate_position_value,
    compute_snapshot,
)


def test_apply_buy_new_and_update():
    df = pd.DataFrame(columns=["ticker", "shares", "buy_price", "cost_basis", "stop_loss"])
    out = apply_buy(df, "AAPL", shares=10, price=100.0, stop_loss=90.0)
    assert len(out) == 1
    assert out.iloc[0]["ticker"] == "AAPL"
    assert out.iloc[0]["shares"] == 10
    assert out.iloc[0]["buy_price"] == 100.0
    assert out.iloc[0]["cost_basis"] == 1000.0

    out2 = apply_buy(out, "AAPL", shares=5, price=200.0)
    assert len(out2) == 1
    assert out2.iloc[0]["shares"] == 15
    # Weighted average price = (1000 + 1000) / 15 = 133.33...
    assert round(out2.iloc[0]["buy_price"], 2) == 133.33
    assert round(out2.iloc[0]["cost_basis"], 2) == 2000.0


def test_apply_sell_and_pnl():
    df = pd.DataFrame([
        {"ticker": "AAPL", "shares": 10.0, "buy_price": 100.0, "cost_basis": 1000.0}
    ])
    out, pnl = apply_sell(df, "AAPL", shares=4, price=150.0)
    assert pnl == pytest.approx(200.0)
    assert out.iloc[0]["shares"] == 6.0
    assert out.iloc[0]["cost_basis"] == pytest.approx(600.0)

    out2, pnl2 = apply_sell(out, "AAPL", shares=6, price=90.0)
    assert pnl2 == pytest.approx(-60.0)
    assert out2.empty


def test_compute_snapshot_and_helpers():
    df = pd.DataFrame([
        {"ticker": "AAPL", "shares": 10.0, "buy_price": 100.0, "stop_loss": 90.0},
        {"ticker": "MSFT", "shares": 5.0, "buy_price": 200.0, "stop_loss": 180.0},
    ])
    prices = {"AAPL": 110.0, "MSFT": 150.0}
    snap = compute_snapshot(df, prices, cash=1000.0, date="2025-08-11")

    assert set(snap.columns) == {
        "Date", "Ticker", "Shares", "Cost Basis", "Stop Loss", "Current Price",
        "Total Value", "PnL", "Action", "Cash Balance", "Total Equity"
    }
    total_row = snap[snap["Ticker"] == "TOTAL"].iloc[0]
    assert total_row["Total Value"] == pytest.approx(10*110 + 5*150)
    assert total_row["Total Equity"] == pytest.approx(total_row["Total Value"] + 1000.0)

    assert calculate_position_value(3, 7.5) == 22.5
    assert calculate_pnl(100.0, 110.0, 10) == 100.0
