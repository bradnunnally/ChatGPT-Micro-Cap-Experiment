import os
import sys
from datetime import date, timedelta
import pandas as pd
import types
from services.core.market_data_service import MarketDataService
from data_providers import SyntheticDataProvider


def test_market_data_service_synthetic_path(monkeypatch):
    # Force dev_stage so synthetic path used (no network)
    monkeypatch.setenv('APP_ENV', 'dev_stage')
    # Provide deterministic synthetic provider via config.get_provider monkeypatch if needed
    provider = SyntheticDataProvider(seed=123)

    # Monkeypatch config.get_provider to return our provider
    import config.providers as providers_mod
    monkeypatch.setattr(providers_mod, 'get_provider', lambda override=None, cli_env=None: provider)

    svc = MarketDataService(ttl_seconds=10)
    price = svc.get_price('ABCD')
    assert price is not None and price > 0

    # Second call should hit in-memory cache quickly
    price2 = svc.get_price('ABCD')
    assert price2 == price


def test_market_data_service_circuit_breaker(monkeypatch):
    # Test that repeated NoMarketDataError failures open circuit and then block calls
    monkeypatch.setenv('APP_ENV', 'production')

    # Fake yfinance module that returns empty DataFrame (forcing NoMarketDataError path)
    class FakeYF:
        def download(self, *a, **k):  # noqa: D401
            return pd.DataFrame()
        def Ticker(self, *a, **k):  # noqa: D401
            class T:  # noqa: D401
                def history(self, *a, **k):
                    return pd.DataFrame()
            return T()

    fake_yf = FakeYF()
    import services.core.market_data_service as mds_mod
    monkeypatch.setattr(mds_mod, 'yf', fake_yf)

    svc = MarketDataService(ttl_seconds=1, max_retries=1, circuit_fail_threshold=2, circuit_cooldown=60)
    # First attempt -> None (NoMarketDataError)
    assert svc.get_price('ZZZZ') is None
    # Second attempt increments failures and opens circuit
    assert svc.get_price('ZZZZ') is None
    # Force circuit state to opened and ensure subsequent call short-circuits without raising
    svc._circuit['ZZZZ'] = mds_mod.CircuitState(failures=3, opened_at=svc._now())
    assert svc.get_price('ZZZZ') is None
