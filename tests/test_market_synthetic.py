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


def test_fetch_price_synthetic():
    from services.market import fetch_price
    p = fetch_price("AAPL")
    assert p is None or p > 0


def test_fetch_prices_synthetic():
    from services.market import fetch_prices
    df = fetch_prices(["AAPL", "MSFT"])  # synthetic/micro path
    assert "ticker" in df.columns


def test_get_current_price_synthetic():
    from services.market import get_current_price
    price = get_current_price("MSFT")
    assert price is None or price > 0


def test_get_day_high_low_synthetic():
    from services.market import get_day_high_low
    hi, lo = get_day_high_low("NVDA")
    assert isinstance(hi, (int, float)) and isinstance(lo, (int, float))
