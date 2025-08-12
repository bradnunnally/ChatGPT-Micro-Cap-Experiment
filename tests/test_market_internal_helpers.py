import pandas as pd
import services.market as market
from unittest.mock import patch


def test_get_synthetic_close(monkeypatch):
    monkeypatch.setenv('APP_ENV', 'dev_stage')
    class FakeProvider:
        def get_history(self, ticker, start, end, force_refresh=False):  # noqa: D401
            return pd.DataFrame({'date': [start, end], 'close': [10.0, 11.0]})
    monkeypatch.setattr(market, 'get_provider', lambda: FakeProvider())
    price = market._get_synthetic_close('TEST')
    assert price == 11.0


def test_download_close_price_legacy(monkeypatch):
    monkeypatch.setenv('PYTEST_CURRENT_TEST', 'tests/test_market.py::legacy')
    import sys, types
    df = pd.DataFrame({'Close': [1.0, 2.0, 3.0]})
    yf_module = types.SimpleNamespace(download=lambda *a, **k: df)
    monkeypatch.setitem(sys.modules, 'yfinance', yf_module)
    price, had_exc, had_nonempty = market._download_close_price('ABC', legacy=True)
    assert price == 3.0 and had_nonempty is True and had_exc is False


def test_download_close_price_info_path(monkeypatch):
    class FakeTicker:
        info = {'regularMarketPrice': 42.5}
        def history(self, *a, **k):
            return pd.DataFrame({'Close': [5.0]})
    monkeypatch.setattr(market, '_get_yf_ticker', lambda t: FakeTicker())
    import sys, types
    df = pd.DataFrame({'Close': [10.0]})
    yf_module = types.SimpleNamespace(download=lambda *a, **k: df)
    monkeypatch.setitem(sys.modules, 'yfinance', yf_module)
    price, had_exc, had_nonempty = market._download_close_price('ZZZ', legacy=False)
    assert price == 42.5 and had_nonempty is True
