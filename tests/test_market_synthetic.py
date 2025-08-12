import os
from datetime import date, timedelta

import pandas as pd
import pytest

from config import resolve_environment
from data_providers import SyntheticDataProvider


@pytest.fixture(autouse=True)
def _set_dev_env(monkeypatch):
    monkeypatch.setenv("APP_ENV", "dev_stage")
    # Ensure streamlit cache isolation between tests
    try:
        from services.market import fetch_price, fetch_prices
        fetch_price.clear()
        fetch_prices.clear()
    except Exception:
        pass


def test_fetch_price_synthetic(monkeypatch):
    # Ensure yfinance.download would raise if accidentally used
    import importlib
    yf = importlib.import_module("yfinance")
    def boom(*a, **k):
        raise AssertionError("yfinance.download should not be called in dev_stage synthetic path")
    monkeypatch.setattr(yf, "download", boom)

    from services.market import fetch_price
    p = fetch_price("AAPL")
    assert p is not None and p > 0


def test_fetch_prices_synthetic(monkeypatch):
    import importlib
    yf = importlib.import_module("yfinance")
    monkeypatch.setattr(yf, "download", lambda *a, **k: pd.DataFrame())

    from services.market import fetch_prices
    df = fetch_prices(["AAPL", "MSFT"])  # synthetic path
    assert set(df["ticker"]) == {"AAPL", "MSFT"}
    assert "current_price" in df.columns
    assert df["current_price"].notna().any()


def test_get_current_price_synthetic(monkeypatch):
    import importlib
    yf = importlib.import_module("yfinance")
    monkeypatch.setattr(yf, "download", lambda *a, **k: pd.DataFrame())

    from services.market import get_current_price
    price = get_current_price("MSFT")
    assert price is not None and price > 0


def test_get_day_high_low_synthetic(monkeypatch):
    import importlib
    yf = importlib.import_module("yfinance")
    monkeypatch.setattr(yf, "download", lambda *a, **k: pd.DataFrame())
    from services.market import get_day_high_low
    hi, lo = get_day_high_low("NVDA")
    assert hi > lo > 0
