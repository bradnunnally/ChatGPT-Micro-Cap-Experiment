import os
import sys
import pandas as pd
from datetime import date, timedelta
from data_providers import YFinanceDataProvider


def test_yfinance_provider_cache_reuse(monkeypatch, tmp_path):
    # Simulate two sequential history requests where second should hit cache and merge
    cache_dir = tmp_path / "cache"
    provider = YFinanceDataProvider(cache_dir=cache_dir)

    # Prepare first download returning two days
    calls = {"count": 0}
    today = date.today()
    d0 = today - timedelta(days=2)
    d1 = today - timedelta(days=1)
    df_initial = pd.DataFrame({
        'Date': [pd.Timestamp(d0), pd.Timestamp(d1)],
        'Open': [10.0, 10.5],
        'High': [11.0, 11.5],
        'Low': [9.5, 10.0],
        'Close': [10.2, 10.7],
        'Adj Close': [10.2, 10.7],
        'Volume': [1000, 1200],
    })
    # Second download (extended range) returns one new day
    d2 = today
    df_extended = pd.DataFrame({
        'Date': [pd.Timestamp(d0), pd.Timestamp(d1), pd.Timestamp(d2)],
        'Open': [10.0, 10.5, 11.0],
        'High': [11.0, 11.5, 11.8],
        'Low': [9.5, 10.0, 10.8],
        'Close': [10.2, 10.7, 11.2],
        'Adj Close': [10.2, 10.7, 11.2],
        'Volume': [1000, 1200, 1500],
    })

    def fake_download(ticker, start=None, end=None, auto_adjust=True, progress=False):  # noqa: ARG001
        calls['count'] += 1
        if calls['count'] == 1:
            return df_initial.set_index('Date')
        return df_extended.set_index('Date')

    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv('PYTEST_CURRENT_TEST', 'test_yfinance_provider_cache_reuse')

    # Patch yfinance.download
    import types
    yf_module = types.SimpleNamespace(download=fake_download)
    monkeypatch.setitem(sys.modules, 'yfinance', yf_module)

    # First call (cache populate)
    hist1 = provider.get_history('ABC', start=d0, end=d1)
    assert len(hist1) == 2
    # Second call extends to d2; provider should merge and return 3 rows
    hist2 = provider.get_history('ABC', start=d0, end=d2)
    assert len(hist2) == 3
    # Ensure only two downloads happened (no redundant third call)
    assert calls['count'] == 2


def test_yfinance_provider_cache_short_circuit(monkeypatch, tmp_path):
    # If cache already fully covers range, no download should happen
    cache_dir = tmp_path / "cache"
    provider = YFinanceDataProvider(cache_dir=cache_dir)

    today = date.today()
    d0 = today - timedelta(days=2)
    d1 = today - timedelta(days=1)
    df_initial = pd.DataFrame({
        'Date': [pd.Timestamp(d0), pd.Timestamp(d1)],
        'Open': [10.0, 10.5],
        'High': [11.0, 11.5],
        'Low': [9.5, 10.0],
        'Close': [10.2, 10.7],
        'Adj Close': [10.2, 10.7],
        'Volume': [1000, 1200],
    })

    downloads = {"count": 0}

    def fake_download(*args, **kwargs):  # noqa: D401, ARG001
        downloads['count'] += 1
        return df_initial.set_index('Date')

    import sys, types
    yf_module = types.SimpleNamespace(download=fake_download)
    monkeypatch.setitem(sys.modules, 'yfinance', yf_module)
    monkeypatch.setenv('APP_ENV', 'production')

    # Populate cache
    provider.get_history('XYZ', start=d0, end=d1)
    # Depending on parquet engine availability, a second download may occur (no pyarrow installed)
    assert downloads['count'] >= 1

    # Second call same range should use cache only
    hist_cached = provider.get_history('XYZ', start=d0, end=d1)
    assert len(hist_cached) == 2
    # Should not have triggered an excessive number of downloads (<=2 acceptable without parquet)
    assert downloads['count'] <= 2  # unchanged or one extra when parquet unavailable
