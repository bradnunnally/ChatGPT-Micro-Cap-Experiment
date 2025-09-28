import re

import pandas as pd
import pytest

from ui.summary import render_daily_portfolio_summary


@pytest.fixture(autouse=True)
def stub_market_history(monkeypatch):
    """Avoid external market calls by returning deterministic price history."""

    def _stub(symbol, months=3):  # pragma: no cover - simple fixture
        dates = pd.date_range(end="2025-08-06", periods=3, freq="D")
        closes = {
            "^GSPC": [4000.0, 4020.0, 4010.0],
        }.get(symbol, [100.0, 101.0, 102.0])
        volumes = {
            "^GSPC": [2_000_000_000, 2_200_000_000, 2_100_000_000],
        }.get(symbol, [1_000_000, 1_050_000, 990_000])
        return pd.DataFrame({"date": dates, "close": closes, "volume": volumes})

    monkeypatch.setattr("ui.summary.MARKET_SERVICE.fetch_history", _stub)
    return _stub


def _build_summary_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"Ticker": "AAA", "Shares": 10, "Buy Price": 5.00, "Cost Basis": 50.0, "Stop Loss": 1.50, "Total Equity": pd.NA},
            {"Ticker": "BBB", "Shares": 20, "Buy Price": 7.00, "Cost Basis": 140.0, "Stop Loss": 2.10, "Total Equity": pd.NA},
            {"Ticker": "TOTAL", "Shares": pd.NA, "Buy Price": pd.NA, "Cost Basis": pd.NA, "Stop Loss": pd.NA, "Total Equity": 4_040.30},
        ]
    )


def _build_history_frame() -> pd.DataFrame:
    dates = pd.date_range(end="2025-08-06", periods=5, freq="D")
    equity = [3_950.0, 3_980.0, 4_100.0, 3_980.0, 4_040.30]
    return pd.DataFrame({"date": dates, "ticker": "TOTAL", "total_equity": equity})


def _base_holdings() -> list[dict]:
    return [
        {
            "ticker": "AAA",
            "exchange": "NASDAQ",
            "sector": "Biotech",
            "shares": 10,
            "costPerShare": 5.00,
            "currentPrice": 57.37,
            "stopType": "None",
            "stopPrice": None,
            "trailingStopPct": None,
            "marketCap": 250_000_000,
            "adv20d": 200_000,
            "spread": 0.01,
            "catalystDate": None,
        },
        {
            "ticker": "BBB",
            "exchange": "NYSE",
            "sector": "AI",
            "shares": 20,
            "costPerShare": 7.00,
            "currentPrice": 168.33,
            "stopType": "None",
            "stopPrice": None,
            "trailingStopPct": None,
            "marketCap": 120_000_000,
            "adv20d": 300_000,
            "spread": 0.03,
            "catalystDate": None,
        },
    ]


def test_summary_renders_template_sections():
    data = {
        "asOfDate": "2025-08-06",
        "cashBalance": 100.00,
        "holdings": _base_holdings(),
        "summaryFrame": _build_summary_frame(),
        "history": _build_history_frame(),
    }

    md = render_daily_portfolio_summary(data)

    assert "Daily Results — 2025-08-06" in md
    assert "[ Price & Volume ]" in md
    assert "[ Risk & Return ]" in md
    assert "[ CAPM vs Benchmarks ]" in md
    assert "[ Snapshot ]" in md
    assert "[ Holdings ]" in md
    assert "[ Your Instructions ]" in md

    # Price & Volume uses holdings only (no external indices by default)
    assert "AAA" in md and "BBB" in md
    assert "^RUT" not in md and "IWO" not in md and "XBI" not in md

    # Snapshot section should surface equity and cash values with currency formatting
    assert "4,040.30" in md
    assert "100.00" in md
    assert "Latest Total Equity" in md
    assert "$100.0 in S&P 500" not in md

    # Holdings table should render both tickers with numeric columns
    assert re.search(r"Ticker\s+Shares\s+Buy Price\s+Cost Basis\s+Stop Loss", md)
    assert re.search(r"AAA\s+10\s+\$5.00\s+\$50.00\s+\$1.50", md)
    assert re.search(r"BBB\s+20\s+\$7.00\s+\$140.00\s+\$2.10", md)

    # Instructions are verbatim at the end
    assert md.strip().endswith("You are encouraged to use the internet to check current prices (and related up-to-date info) for potential buys.")


def test_summary_handles_empty_portfolio():
    data = {
        "asOfDate": "2025-08-06",
        "cashBalance": 0.0,
        "holdings": [],
    }

    md = render_daily_portfolio_summary(data)

    assert "Daily Results — 2025-08-06" in md
    assert "(no active holdings)" in md
    assert "(no symbols available)" in md


def test_summary_surfaces_risk_metrics_from_history():
    data = {
        "asOfDate": "2025-08-06",
        "cashBalance": 500.00,
        "holdings": _base_holdings(),
        "summaryFrame": _build_summary_frame(),
        "history": _build_history_frame(),
    }

    md = render_daily_portfolio_summary(data)

    assert re.search(r"Max Drawdown:\s+[-+\d\.]+%", md)
    assert re.search(r"Sharpe Ratio \(period\):\s+[-+\d\.]+", md)
    assert re.search(r"Beta \(daily\) vs \^GSPC:\s+[-+\d\.]+", md)
    assert re.search(r"Alpha \(annualized\) vs \^GSPC:\s+[-+\d\.]+%", md)
    assert re.search(r"R² \(fit quality\):\s+[-+\d\.]+\s+    Obs: \d+", md)
    assert "Note:" in md
