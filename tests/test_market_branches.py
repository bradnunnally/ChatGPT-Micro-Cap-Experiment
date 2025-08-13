import os
import types
import pandas as pd
import numpy as np
import services.market as market

# Helper to build Close DataFrame for download path

def _close_df(prices):
    return pd.DataFrame({"Close": prices})


def test_fetch_price_info_path(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test_fetch_price_info_path")

    class FakeTicker:
        info = {"regularMarketPrice": 123.45}
        def history(self, *a, **k):
            return pd.DataFrame()
    monkeypatch.setattr(market, "_get_yf_ticker", lambda symbol: FakeTicker())
    # Ensure download not used
    import sys
    yf_module = types.SimpleNamespace(download=lambda *a, **k: pd.DataFrame())
    monkeypatch.setitem(sys.modules, "yfinance", yf_module)

    price = market.fetch_price("INFO1")
    assert price == 123.45


def test_fetch_price_download_path(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test_fetch_price_download_path")

    class FakeTicker:
        info = {}  # forces skip info path
        def history(self, *a, **k):
            return pd.DataFrame()
    monkeypatch.setattr(market, "_get_yf_ticker", lambda symbol: FakeTicker())

    import sys
    df = _close_df([10.0, 11.0, 12.0])
    yf_module = types.SimpleNamespace(download=lambda *a, **k: df)
    monkeypatch.setitem(sys.modules, "yfinance", yf_module)

    price = market.fetch_price("DLONLY")
    assert price == 12.0


def test_fetch_price_history_fallback(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test_fetch_price_history_fallback")

    called = {"download": 0, "history": 0}

    class FakeHistoryTicker:
        info = {}
        def history(self, *a, **k):
            called["history"] += 1
            return _close_df([5.0, 6.0])
    def fake_get(symbol):
        return FakeHistoryTicker()
    monkeypatch.setattr(market, "_get_yf_ticker", fake_get)

    import sys
    yf_module = types.SimpleNamespace(download=lambda *a, **k: pd.DataFrame())
    monkeypatch.setitem(sys.modules, "yfinance", yf_module)

    price = market.fetch_price("HISTFB")
    assert price == 6.0
    assert called["history"] == 1


def test_get_day_high_low_intraday(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    class FakeTicker:
        def history(self, period="1d", interval="5m"):
            if interval == "5m":
                return pd.DataFrame({
                    "High": [10, 11, 12],
                    "Low": [9, 8, 7],
                })
            return pd.DataFrame()
    monkeypatch.setattr(market, "_get_yf_ticker", lambda s: FakeTicker())
    import sys
    yf_module = types.SimpleNamespace(download=lambda *a, **k: pd.DataFrame())
    monkeypatch.setitem(sys.modules, "yfinance", yf_module)

    hi, lo = market.get_day_high_low("INTRA")
    assert hi == 12
    assert lo == 7


def test_get_day_high_low_daily_fallback(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    class FakeTicker:
        def history(self, period="1d", interval="5m"):
            return pd.DataFrame()  # intraday empty
    monkeypatch.setattr(market, "_get_yf_ticker", lambda s: FakeTicker())
    import sys
    daily_df = pd.DataFrame({"High": [15], "Low": [14]})
    def fake_download(*a, **k):
        return daily_df
    yf_module = types.SimpleNamespace(download=fake_download)
    monkeypatch.setitem(sys.modules, "yfinance", yf_module)

    hi, lo = market.get_day_high_low("DAILY")
    assert hi == 15 and lo == 14


def test_get_day_high_low_5d_fallback(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    class FakeTicker:
        def __init__(self):
            self.calls = 0
        def history(self, period="1d", interval="5m"):
            if period == "1d" and interval == "5m":
                return pd.DataFrame()  # intraday empty
            if period == "5d":
                return pd.DataFrame({"High": [20, 22], "Low": [18, 17]})
            return pd.DataFrame()
    fake_ticker = FakeTicker()
    monkeypatch.setattr(market, "_get_yf_ticker", lambda s: fake_ticker)
    import sys
    yf_module = types.SimpleNamespace(download=lambda *a, **k: pd.DataFrame())
    monkeypatch.setitem(sys.modules, "yfinance", yf_module)

    hi, lo = market.get_day_high_low("FIVED")
    assert hi == 22 and lo == 17


def test_get_day_high_low_current_price_fallback(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")

    class FakeTicker:
        def history(self, *a, **k):
            return pd.DataFrame()  # force deeper fallbacks
    monkeypatch.setattr(market, "_get_yf_ticker", lambda s: FakeTicker())

    import sys
    yf_module = types.SimpleNamespace(download=lambda *a, **k: pd.DataFrame())
    monkeypatch.setitem(sys.modules, "yfinance", yf_module)

    # Force fetch_price to return a known value for buffer fallback
    monkeypatch.setattr(market, "fetch_price", lambda t: 100.0)

    hi, lo = market.get_day_high_low("CURFB")
    assert hi == 105.0 and lo == 95.0


def test_fetch_prices_multi_index(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    import sys
    # Build MultiIndex DataFrame like yfinance returns
    tuples = [("Close", "AAA"), ("Close", "BBB")]
    idx = pd.MultiIndex.from_tuples(tuples, names=[None, None])
    data = pd.DataFrame([[10.0, 20.0]], columns=idx)
    def fake_download(tickers, *a, **k):  # noqa: D401
        return data
    yf_module = types.SimpleNamespace(download=fake_download)
    monkeypatch.setitem(sys.modules, "yfinance", yf_module)
    # Patch session to avoid real request path
    monkeypatch.setattr(market, "_get_session", lambda: None)  # noqa: ARG005
    df = market.fetch_prices(["AAA", "BBB"])
    assert set(df.ticker) == {"AAA", "BBB"}
    assert set(df.current_price) == {10.0, 20.0}


def test_get_cached_price(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    # Provide deterministic current price path
    calls = {"count": 0}
    def fake_get_current(t):
        calls["count"] += 1
        return 50.0
    monkeypatch.setattr(market, "get_current_price", fake_get_current)

    p1 = market.get_cached_price("CACHE1", ttl_seconds=5)
    p2 = market.get_cached_price("CACHE1", ttl_seconds=5)
    assert p1 == p2 == 50.0
    assert calls["count"] == 1  # second call cached
