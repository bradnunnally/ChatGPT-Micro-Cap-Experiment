import os
import pandas as pd
import pytest
import time as _time

# Disable micro providers at import time so services.market loads without provider
os.environ["DISABLE_MICRO_PROVIDERS"] = "1"
import services.market as m  # noqa: E402


def setup_module(module):  # noqa: D401
    # Ensure caches cleared between test runs
    m._price_cache.clear()


def test_calculate_percentage_change_cases():
    # new None -> None
    assert m.calculate_percentage_change(10, None) is None
    # old <=0 -> 0.0
    assert m.calculate_percentage_change(0, 5) == 0.0
    assert m.calculate_percentage_change(-1, 5) == 0.0
    # normal percent change
    assert pytest.approx(m.calculate_percentage_change(100, 110), rel=1e-6) == 10.0


def test_validate_ticker_and_price_helpers():
    assert m.validate_ticker_format("AAPL")
    assert not m.validate_ticker_format("aapl")
    assert not m.validate_ticker_format("")
    assert m.is_valid_price(1.23)
    assert not m.is_valid_price(-1)
    # alias coverage
    assert m.validate_price_data(2.5) is True


def test_sanitize_market_data_imputation_and_filtering():
    df = pd.DataFrame([
        {"ticker": "AAPL", "price": None, "volume": 1000},  # imputed
        {"ticker": "BAD1", "price": 5, "volume": 10},      # filtered invalid format
        {"ticker": "MSFT", "price": 200, "volume": None},  # kept
    ])
    cleaned = m.sanitize_market_data(df)
    # BAD1 removed
    assert set(cleaned["ticker"]) == {"AAPL", "MSFT"}
    # AAPL imputed to 1.0
    assert float(cleaned.loc[cleaned["ticker"] == "AAPL", "price"].iloc[0]) == 1.0
    assert float(cleaned.loc[cleaned["ticker"] == "MSFT", "price"].iloc[0]) == 200.0


def test_retry_helper_and_cached_price(monkeypatch):
    calls = {"n": 0}
    def flaky():
        calls["n"] += 1
        if calls["n"] < 2:
            raise RuntimeError("fail once")
        return 42
    val = m._retry(flaky, attempts=3, base_delay=0.0)
    assert val == 42 and calls["n"] == 2

    # Failure path returns None
    always_fail = lambda: (_ for _ in ()).throw(RuntimeError("always fail"))  # generator trick to raise
    assert m._retry(always_fail, attempts=2, base_delay=0.0) is None

    # Test get_cached_price uses cache (monkeypatch get_current_price)
    m._price_cache.clear()
    prices = iter([10, 20, 30])
    monkeypatch.setattr(m, "get_current_price", lambda t: next(prices))
    p1 = m.get_cached_price("AAPL", ttl_seconds=60)
    p2 = m.get_cached_price("AAPL", ttl_seconds=60)
    assert p1 == 10 and p2 == 10  # second call cached

    # Expire TTL and ensure refresh takes next value
    # Monkeypatch time to simulate TTL expiry
    original_time = m.time.time
    base = original_time()
    monkeypatch.setattr(m.time, "time", lambda: base + 1000)
    p3 = m.get_cached_price("AAPL", ttl_seconds=1)
    assert p3 == 20
    # restore time
    monkeypatch.setattr(m.time, "time", original_time)


def test_get_day_high_low_final_fallback(monkeypatch):
    # Force fetch_price to return None to drive final deterministic fallback (0.0,0.0)
    monkeypatch.setattr(m, "fetch_price", lambda t: None)
    hi, lo = m.get_day_high_low("ZZZZ")
    assert isinstance(hi, (int, float)) and isinstance(lo, (int, float))
    assert hi >= lo
    assert lo >= 0.0
import math
import pandas as pd
import services.market as market


def test_market_helpers_basic():
    assert market.is_valid_price(10.5) is True
    assert market.is_valid_price(-1) is False
    assert market.calculate_percentage_change(100, 110) == 10.0
    assert market.calculate_percentage_change(0, 110) == 0.0
    assert market.validate_price_data(5.0) is True
    assert market.validate_price_data(-3) is False


def test_validate_ticker_format():
    assert market.validate_ticker_format('AAPL') is True
    assert market.validate_ticker_format('aapl') is False
    assert market.validate_ticker_format('1234') is False
    assert market.validate_ticker_format('') is False
    assert market.validate_ticker_format('BRK.B') is True


def test_sanitize_market_data_impute_branch():
    # Construct DataFrame where one valid row and one row with missing price but valid volume triggers imputation branch
    df = pd.DataFrame({
        'ticker': ['AAA', 'BBB'],
        'price': [10.0, None],
        'volume': [1000, 2000],
    })
    cleaned = market.sanitize_market_data(df)
    assert len(cleaned) == 2
    assert set(cleaned['ticker']) == {'AAA', 'BBB'}
    # Ensure the imputed price of 1.0 exists for BBB
    bbb_row = cleaned[cleaned['ticker'] == 'BBB'].iloc[0]
    assert math.isclose(float(bbb_row['price']), 1.0, rel_tol=1e-6)
