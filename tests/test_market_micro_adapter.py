import os
import pandas as pd
import pytest


@pytest.fixture(autouse=True)
def clear_env(monkeypatch):
    monkeypatch.delenv("ENABLE_MICRO_PROVIDERS", raising=False)
    monkeypatch.delenv("APP_USE_FINNHUB", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    yield


def test_fetch_price_v2_fallback_to_legacy(monkeypatch):
    import services.market as m

    # Ensure flag disabled
    monkeypatch.delenv("ENABLE_MICRO_PROVIDERS", raising=False)
    m._micro_provider_cache = None  # type: ignore
    # track legacy call
    called = {}

    def fake_legacy(t):
        called['ticker'] = t
        return 123.45

    monkeypatch.setattr(m, 'fetch_price', fake_legacy)
    monkeypatch.setattr(m, '_get_micro_provider', lambda: None)

    val = m.fetch_price_v2('ABC')
    assert val == 123.45
    assert called['ticker'] == 'ABC'


def test_fetch_price_v2_micro_enabled(monkeypatch):
    import services.market as m

    monkeypatch.setenv("ENABLE_MICRO_PROVIDERS", "1")
    m._micro_provider_cache = None  # type: ignore

    class FakeProv:
        def get_quote(self, ticker):
            return {"price": 9.87, "percent": 1.23}

    monkeypatch.setattr(m, '_get_micro_provider', lambda: FakeProv())
    # legacy should not be called; make it fail if used
    monkeypatch.setattr(m, 'fetch_price', lambda t: (_ for _ in ()).throw(RuntimeError("legacy called")))

    val = m.fetch_price_v2('DEF')
    assert val == 9.87


def test_fetch_prices_v2_micro_enabled(monkeypatch):
    import services.market as m

    monkeypatch.setenv("ENABLE_MICRO_PROVIDERS", "1")
    m._micro_provider_cache = None  # type: ignore

    class FakeProv:
        def __init__(self):
            self.calls = []
        def get_quote(self, ticker):
            self.calls.append(ticker)
            base = 10.0 + len(self.calls)
            return {"price": base, "percent": 0.5}

    fake = FakeProv()
    monkeypatch.setattr(m, '_get_micro_provider', lambda: fake)
    monkeypatch.setattr(m, 'fetch_prices', lambda tickers: pd.DataFrame())  # legacy bypass

    df = m.fetch_prices_v2(['AAA','BBB'])
    assert list(df['ticker']) == ['AAA','BBB']
    assert df['current_price'].tolist() == [11.0, 12.0]
    assert df['pct_change'].tolist() == [0.5, 0.5]


def test_fetch_price_v2_micro_error_fallback(monkeypatch):
    import services.market as m

    monkeypatch.setenv("ENABLE_MICRO_PROVIDERS", "1")
    m._micro_provider_cache = None  # type: ignore

    class BadProv:
        def get_quote(self, ticker):
            raise RuntimeError("boom")

    monkeypatch.setattr(m, '_get_micro_provider', lambda: BadProv())
    monkeypatch.setattr(m, 'fetch_price', lambda t: 55.5)

    assert m.fetch_price_v2('XYZ') == 55.5
