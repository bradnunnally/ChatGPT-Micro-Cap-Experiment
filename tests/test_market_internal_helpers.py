import pandas as pd
import services.market as market
import time

def test_internal_rate_limit(monkeypatch):
    calls = {"sleep": 0}
    def fake_sleep(x):
        calls["sleep"] += 1
    monkeypatch.setattr(market.time, "sleep", fake_sleep)
    market._last_request_time = time.time() - 0.1
    market._rate_limit()
    assert calls["sleep"] == 1

def test_internal_session_cache():
    s1 = market._get_session()
    s2 = market._get_session()
    assert s1 is s2

def test_internal_download_helper_removed():
    price, had_exc, had_nonempty = market._download_close_price("ABC", legacy=False)
    assert price is None and had_exc is False
