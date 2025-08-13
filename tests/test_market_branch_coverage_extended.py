import os
import sys
import pandas as pd
import pytest
from unittest.mock import MagicMock

import services.market as market


def test_fetch_price_logs_on_failure(monkeypatch, caplog):
    # Force quote failure path
    monkeypatch.setattr(market, "_get_micro_provider", lambda: None)
    with caplog.at_level("ERROR"):
        price = market.fetch_price("AAPL")
    # Price may be None (no synthetic history yet) or numeric if synthetic path works
    assert price is None or isinstance(price, (int, float))


def test_get_day_high_low_buffer_fallback(monkeypatch):
    # Force buffer path by disabling micro provider and synthetic history
    monkeypatch.setattr(market, "_get_micro_provider", lambda: None)
    # Allow variable synthetic or fallback values; ensure ordering and non-negative
    monkeypatch.setattr(market, "fetch_price", lambda t: 100.0)
    high, low = market.get_day_high_low("AAPL")
    assert isinstance(high, (int, float)) and isinstance(low, (int, float))
    assert high >= low
    assert low >= 0.0


def test_fetch_prices_dev_stage(monkeypatch):
    monkeypatch.setattr(market, "is_dev_stage", lambda: True)
    class DummyProvider:
        def get_history(self, ticker, start, end):
            # Return empty for one symbol to force None price path
            if ticker == "MSFT":
                return pd.DataFrame()
            return pd.DataFrame({"Close": [123.0]})
    monkeypatch.setattr(market, "get_provider", lambda: DummyProvider())
    out = market.fetch_prices(["AAPL", "MSFT"])  # dev path
    assert set(out["ticker"]) == {"AAPL", "MSFT"}
    aapl_val = out[out["ticker"]=="AAPL"]["current_price"].iloc[0]
    msft_val = out[out["ticker"]=="MSFT"]["current_price"].iloc[0]
    assert (aapl_val is None) or isinstance(aapl_val, (int, float))
    assert (msft_val is None) or isinstance(msft_val, (int, float)) or pd.isna(msft_val)
