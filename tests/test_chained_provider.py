import sys
import types
from datetime import date

import pandas as pd
import pytest

import micro_config


def _sample_df():
    idx = pd.date_range(end=pd.Timestamp.utcnow().normalize(), periods=5, freq="D")
    df = pd.DataFrame(
        {
            "Open": [10, 11, 12, 13, 14],
            "High": [11, 12, 13, 14, 15],
            "Low": [9, 10, 11, 12, 13],
            "Close": [10.5, 11.5, 12.5, 13.5, 14.5],
            "Volume": [100, 200, 150, 300, 250],
        },
        index=idx,
    )
    df.index.name = "Date"
    return df


def test_dev_stage_returns_synthetic_provider():
    p = micro_config.get_provider(cli_env="dev_stage")
    # class name may be SyntheticDataProviderExt
    assert p is not None
    df = p.get_daily_candles("AAPL", date.today() - pd.Timedelta(days=5), date.today())
    assert isinstance(df, pd.DataFrame)


def test_production_falls_back_to_yfinance(monkeypatch):
    # Make Finnhub provider raise so chain moves to yfinance
    class DummyFinnhub:
        def __init__(self, *a, **k):
            pass

        def get_daily_candles(self, *a, **k):
            raise RuntimeError("finnhub down")

    monkeypatch.setenv("FINNHUB_API_KEY", "dummy")
    monkeypatch.setattr(micro_config, "FinnhubDataProvider", DummyFinnhub)

    # Inject fake yfinance module
    yf_mod = types.ModuleType("yfinance")

    class DummyTicker:
        def __init__(self, ticker):
            self.ticker = ticker

        def history(self, start=None, end=None):
            return _sample_df()

    yf_mod.Ticker = DummyTicker
    monkeypatch.setitem(sys.modules, "yfinance", yf_mod)

    provider = micro_config.get_provider(cli_env="production")
    df = provider.get_daily_candles("AAPL", date.today() - pd.Timedelta(days=5), date.today())
    assert isinstance(df, pd.DataFrame)
    assert not df.empty


def test_production_falls_back_to_stooq_when_yf_empty(monkeypatch):
    # Finnhub fails
    class DummyFinnhub:
        def __init__(self, *a, **k):
            pass

        def get_daily_candles(self, *a, **k):
            raise RuntimeError("finnhub down")

    monkeypatch.setenv("FINNHUB_API_KEY", "dummy")
    monkeypatch.setattr(micro_config, "FinnhubDataProvider", DummyFinnhub)

    # yfinance returns empty
    yf_mod = types.ModuleType("yfinance")

    class DummyTickerEmpty:
        def __init__(self, ticker):
            pass

        def history(self, start=None, end=None):
            return pd.DataFrame()

    yf_mod.Ticker = DummyTickerEmpty
    monkeypatch.setitem(sys.modules, "yfinance", yf_mod)

    # Inject pandas_datareader.data.DataReader
    pdr_mod = types.ModuleType("pandas_datareader")
    data_mod = types.ModuleType("pandas_datareader.data")

    def DataReader(ticker, source, start, end):
        return _sample_df()

    data_mod.DataReader = DataReader
    pdr_mod.data = data_mod
    monkeypatch.setitem(sys.modules, "pandas_datareader", pdr_mod)
    monkeypatch.setitem(sys.modules, "pandas_datareader.data", data_mod)

    provider = micro_config.get_provider(cli_env="production")
    df = provider.get_daily_candles("AAPL", date.today() - pd.Timedelta(days=5), date.today())
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
