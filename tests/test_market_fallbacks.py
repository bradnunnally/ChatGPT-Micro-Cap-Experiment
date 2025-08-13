import os
import pandas as pd
import pytest


@pytest.fixture(autouse=True)
def _prod_env(monkeypatch):
    # Force production to exercise yfinance fallback branches (with mocks)
    monkeypatch.delenv("APP_ENV", raising=False)


def test_fetch_price_fallback_download_then_history(monkeypatch):
    # Force info fetch failure and first download empty then history success
    import importlib
    import types

    # Patch _get_yf_ticker to raise on info, then provide history later
    import services.market as m

    class BadTicker:
        def __init__(self, symbol):
            self.info = {}
        def history(self, period="5d", interval="1d"):
            # Provide a simple history fallback
            return pd.DataFrame({"Close": [100.0, 101.0]})

    monkeypatch.setattr(m, "_get_yf_ticker", lambda s: BadTicker(s))

    # download returns empty first (so fallback to history path)
    yf = importlib.import_module("yfinance")
    monkeypatch.setattr(yf, "download", lambda *a, **k: pd.DataFrame())

    m.fetch_price.clear()
    price = m.fetch_price("AAPL")
    assert price == 101.0


def test_get_day_high_low_all_fallbacks(monkeypatch):
    import importlib
    import services.market as m

    class FailTicker:
        def __init__(self, symbol):
            self.info = {}
        def history(self, period="1d", interval="5m"):
            raise Exception("intraday fail")

    class SecondTicker(FailTicker):
        def history(self, period="5d", interval="1d"):
            return pd.DataFrame({"High": [10, 11], "Low": [9, 9.5]})

    seq = {"stage": 0}
    def fake_get(symbol):
        if seq["stage"] == 0:
            seq["stage"] = 1
            return FailTicker(symbol)
        return SecondTicker(symbol)

    monkeypatch.setattr(m, "_get_yf_ticker", fake_get)

    import yfinance as yf
    # First download attempt raises, second returns empty -> forces deeper fallback
    def fake_download(*a, **k):
        if seq["stage"] == 1:
            seq["stage"] = 2
            raise Exception("download fail")
        return pd.DataFrame()

    monkeypatch.setattr(yf, "download", fake_download)

    hi, lo = m.get_day_high_low("AAPL")
    assert hi == 11 and lo == 9.5
