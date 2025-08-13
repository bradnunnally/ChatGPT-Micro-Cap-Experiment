import services.market as market
import pandas as pd

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
