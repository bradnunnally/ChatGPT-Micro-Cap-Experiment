import re
from ui.summary import render_daily_portfolio_summary


def test_case_a_two_holdings_microcap():
    data = {
        "asOfDate": "2025-08-06",
        "cashBalance": 100.00,
        "holdings": [
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
        ],
    }
    md = render_daily_portfolio_summary(data)
    # Invested value = 10*57.37 + 20*168.33 = 573.70 + 3366.60 = 3,940.30
    assert "Invested Current Value (ex-cash): $3,940.30" in md
    # Largest position concentration BBB = 3366.60 / 3940.30 = 0.8545 -> 85.45%
    assert re.search(r"Largest Position Concentration: 85\.4[0-9]% of invested capital", md)
    # Micro-cap compliance Yes
    assert "Micro-cap Compliance: Yes" in md
    # Top Holdings show two lines
    assert md.count("- AAA:") == 1
    assert md.count("- BBB:") == 1


def test_case_b_over_300m_market_cap():
    data = {
        "asOfDate": "2025-08-06",
        "cashBalance": 0.0,
        "holdings": [
            {
                "ticker": "BIG",
                "exchange": "NYSE",
                "sector": "Tech",
                "shares": 5,
                "costPerShare": 10.0,
                "currentPrice": 12.0,
                "stopType": "None",
                "stopPrice": None,
                "trailingStopPct": None,
                "marketCap": 305_000_000,
                "adv20d": 100_000,
                "spread": 0.05,
                "catalystDate": None,
            }
        ],
    }
    md = render_daily_portfolio_summary(data)
    assert "Micro-cap Compliance: No" in md
    assert "Any holding ≥ $300M market cap: Yes" in md


def test_case_c_stop_rendering():
    data = {
        "asOfDate": "2025-08-06",
        "cashBalance": 0.0,
        "holdings": [
            {
                "ticker": "FIX",
                "exchange": "NASDAQ",
                "sector": "Energy",
                "shares": 10,
                "costPerShare": 2.0,
                "currentPrice": 1.7,
                "stopType": "Fixed",
                "stopPrice": 1.80,
                "trailingStopPct": None,
                "marketCap": 50_000_000,
                "adv20d": 50_000,
                "spread": 0.01,
                "catalystDate": None,
            },
            {
                "ticker": "TRL",
                "exchange": "NYSE",
                "sector": "Energy",
                "shares": 10,
                "costPerShare": 2.0,
                "currentPrice": 2.4,
                "stopType": "Trailing",
                "stopPrice": None,
                "trailingStopPct": 20,
                "marketCap": 75_000_000,
                "adv20d": 60_000,
                "spread": 0.02,
                "catalystDate": None,
            },
        ],
    }
    md = render_daily_portfolio_summary(data)
    assert "$1.80" in md
    assert "Trailing 20%" in md
    # FIX is below stop (1.7 <= 1.8)
    assert "Positions Below Stop Loss: 1" in md


def test_case_d_missing_optional_fields():
    data = {
        "asOfDate": "2025-08-06",
        "cashBalance": 0.0,
        "holdings": [
            {
                "ticker": "MISS",
                "exchange": "NYSE",
                "sector": "N/A",
                "shares": 0,
                "costPerShare": 0,
                "currentPrice": 0,
                "stopType": "None",
                "stopPrice": None,
                "trailingStopPct": None,
                "marketCap": None,
                # adv20d and spread intentionally missing
            }
        ],
    }
    md = render_daily_portfolio_summary(data)
    assert "N/A" in md  # several N/A fields present
    assert "Liquidity sanity (intended trade size < 10% of 20d ADV): N/A" in md
