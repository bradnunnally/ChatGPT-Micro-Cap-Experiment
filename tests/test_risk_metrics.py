import pandas as pd
from services.risk import (
    compute_drawdown,
    max_drawdown,
    rolling_volatility,
    sharpe_like,
    concentration,
    compute_risk_block,
    attribute_pnl,
)


def test_drawdown_basic():
    eq = pd.Series([100, 110, 90, 95])
    dd = compute_drawdown(eq)
    # Max drawdown should be from 110 -> 90 = -18.18%
    assert round(dd.min(), 2) == -18.18
    assert max_drawdown(eq) < 0


def test_rolling_volatility_and_sharpe():
    # deterministic returns: alternating +-1%
    rets = pd.Series([0.01, -0.01] * 15)
    vol = rolling_volatility(rets, window=20)
    assert vol > 0
    sharpe = sharpe_like(rets)
    # With mean near 0 sharpe should be near 0
    assert abs(sharpe) < 0.5


def test_concentration():
    df = pd.DataFrame([
        {"date": "2024-01-01", "ticker": "A", "total_value": 60},
        {"date": "2024-01-01", "ticker": "B", "total_value": 30},
        {"date": "2024-01-01", "ticker": "C", "total_value": 10},
        {"date": "2024-01-01", "ticker": "TOTAL", "total_value": 100},
    ])
    c1, c3 = concentration(df)
    assert c1 == 60.0
    assert c3 == 100.0


def test_compute_risk_block():
    hist = pd.DataFrame([
        {"date": "2024-01-01", "ticker": "TOTAL", "total_equity": 100},
        {"date": "2024-01-02", "ticker": "TOTAL", "total_equity": 110},
        {"date": "2024-01-03", "ticker": "TOTAL", "total_equity": 90},
        {"date": "2024-01-03", "ticker": "A", "total_value": 60},
        {"date": "2024-01-03", "ticker": "B", "total_value": 30},
        {"date": "2024-01-03", "ticker": "C", "total_value": 10},
    ])
    metrics = compute_risk_block(hist)
    assert metrics.max_drawdown_pct < 0
    assert metrics.concentration_top1_pct == 60.0
    assert metrics.sharpe_like == metrics.sharpe  # canonical equality
    assert metrics.sharpe_like == metrics.sharpe  # stable


def test_attribute_pnl():
    prev = pd.DataFrame([
        {"ticker": "A", "shares": 10, "buy_price": 5},
        {"ticker": "B", "shares": 20, "buy_price": 2},
    ])
    cur = pd.DataFrame([
        {"ticker": "A", "shares": 15, "buy_price": 6},  # +5 shares at 6, price +1 on 10 existing
        {"ticker": "B", "shares": 10, "buy_price": 1.5},  # sold 10, price -0.5 on 20 existing
    ])
    out = attribute_pnl(cur, prev)
    a = out[out.ticker == "A"].iloc[0]
    # price pnl: (6-5)*10 = 10; position pnl: (15-10)*6 = 30
    assert a.pnl_position == 30
    b = out[out.ticker == "B"].iloc[0]
    # price pnl: (1.5-2)*20 = -10; position pnl: (10-20)*1.5 = -15
    assert b.pnl_price == -10
    assert b.pnl_position == -15
