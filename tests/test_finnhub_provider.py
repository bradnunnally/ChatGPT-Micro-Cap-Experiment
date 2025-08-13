from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from micro_data_providers import FinnhubDataProvider


class FakeClient:
    def __init__(self):
        self.calls = {"quote": 0, "stock_candles": 0, "company_profile2": 0, "company_basic_financials": 0, "company_news": 0, "earnings_calendar": 0}

    def quote(self, symbol):
        self.calls["quote"] += 1
        return {"c": 10.0, "pc": 9.5}

    def stock_candles(self, symbol, resol, _from, to):
        self.calls["stock_candles"] += 1
        # two days
        t0 = _from + 86400
        t1 = t0 + 86400
        return {"s": "ok", "t": [t0, t1], "o": [10, 11], "h": [11, 12], "l": [9, 10], "c": [10.5, 11.5], "v": [1000, 2000]}

    def company_profile2(self, symbol):
        self.calls["company_profile2"] += 1
        return {"exchange": "NASDAQ", "finnhubIndustry": "Technology"}

    def company_basic_financials(self, ticker, metric):
        self.calls["company_basic_financials"] += 1
        return {"metric": {"marketCapitalization": 123_456_789}}

    def company_news(self, symbol, _from, to):
        self.calls["company_news"] += 1
        return [{"headline": "Test headline"}]

    def earnings_calendar(self, _from, to, symbol=None):
        self.calls["earnings_calendar"] += 1
        return {"earningsCalendar": [{"symbol": symbol or "AAA", "date": _from}]}


def test_finnhub_mapping_and_cache(tmp_path, monkeypatch):
    provider = FinnhubDataProvider(api_key="x", cache_dir=tmp_path)
    fake = FakeClient()
    monkeypatch.setattr(provider, "_client", fake)
    # Quote
    q = provider.get_quote("AAA")
    assert q["price"] == 10.0 and q["change"] == 0.5 and round(q["percent"], 2) == 5.26
    # Cache hit
    q2 = provider.get_quote("AAA")
    assert fake.calls["quote"] == 1
    # Candles
    end = date.today()
    start = end - timedelta(days=3)
    df = provider.get_daily_candles("AAA", start, end)
    assert list(df.columns) == ["date", "open", "high", "low", "close", "volume"]
    assert len(df) == 2 and isinstance(df.loc[0, "date"], pd.Timestamp)
    # Profile
    prof = provider.get_company_profile("AAA")
    assert prof["exchange"] == "NASDAQ" and prof["sector"] == "Technology" and prof["marketCap"] == 123_456_789
    # News
    news = provider.get_company_news("AAA", start, end)
    assert news and news[0]["headline"].startswith("Test")
    # Earnings
    earn = provider.get_earnings_calendar("AAA", start, end)
    assert earn and earn[0]["symbol"] == "AAA"
