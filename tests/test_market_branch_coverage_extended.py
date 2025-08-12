import os
import sys
import pandas as pd
import pytest
from unittest.mock import patch, MagicMock

import services.market as market


def test_fetch_price_logs_on_failure(monkeypatch, caplog):
    # Force _download_close_price to return (None, had_exc=True, had_nonempty=True)
    monkeypatch.setattr(market, "_download_close_price", lambda t, legacy: (None, True, True))
    with caplog.at_level("ERROR"):
        price = market.fetch_price("AAPL")
    assert price is None
    assert any("Failed to fetch price" in rec.message for rec in caplog.records)


def test_get_day_high_low_buffer_fallback(monkeypatch):
    # Skip legacy
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "not_legacy::test")
    # Force dev stage false to avoid synthetic path interfering
    monkeypatch.setattr(market, "is_dev_stage", lambda: False)
    # Force all yfinance related attempts to fail
    # _get_yf_ticker returns object whose history always empty
    monkeypatch.setattr(market, "_get_yf_ticker", lambda t: MagicMock(info={}, history=lambda **k: pd.DataFrame()))
    # Patch yfinance.download used inside get_day_high_low fallback 1 to return empty
    import types
    dummy_yf = types.SimpleNamespace(download=lambda *a, **k: pd.DataFrame())
    monkeypatch.setitem(sys.modules, 'yfinance', dummy_yf)
    monkeypatch.setattr(market, "_rate_limit", lambda: None)
    # fetch_price will return a deterministic value used for buffer
    monkeypatch.setattr(market, "fetch_price", lambda t: 100.0)
    high, low = market.get_day_high_low("AAPL")
    assert high == pytest.approx(105.0)
    assert low == pytest.approx(95.0)


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
    assert out[out["ticker"]=="AAPL"]["current_price"].iloc[0] == 123.0
    assert pd.isna(out[out["ticker"]=="MSFT"]["current_price"].iloc[0])
