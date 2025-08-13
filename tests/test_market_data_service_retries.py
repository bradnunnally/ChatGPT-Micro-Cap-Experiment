import types
import pandas as pd
import pytest
from services.core.market_data_service import MarketDataService, MarketDataDownloadError

class DummyYF:
    def __init__(self, seq):
        self._seq = iter(seq)
    def download(self, symbol, period="1d", progress=False, auto_adjust=True):  # type: ignore
        val = next(self._seq)
        if isinstance(val, Exception):
            raise val
        # Return DataFrame or empty based on sentinel
        if val == "empty":
            return pd.DataFrame()
        if isinstance(val, pd.DataFrame):
            return val
        return pd.DataFrame({"Close": [val]})
    class TickerCls:
        def __init__(self, seq):
            self._seq = iter(seq)
        def history(self, period="5d"):
            val = next(self._seq)
            if isinstance(val, Exception):
                raise val
            if val == "empty":
                return pd.DataFrame()
            if isinstance(val, pd.DataFrame):
                return val
            return pd.DataFrame({"Close": [val]})
    def Ticker(self, symbol):  # type: ignore
        return DummyYF.TickerCls(["empty", 123.0])

def test_retry_then_success():
    # Inject a flaky price provider directly
    class Flaky:
        def __init__(self):
            self.calls = 0
        def __call__(self, ticker):
            self.calls += 1
            if self.calls < 3:
                raise Exception("boom")
            return 111.0
    flaky = Flaky()
    svc = MarketDataService(max_retries=3, backoff_base=0.0, ttl_seconds=0, price_provider=flaky)
    price = svc.get_price("ZZZTMP1")
    assert price == 111.0


def test_no_market_data_returns_none():
    # Provider always raises -> after retries raise MarketDataDownloadError
    class AlwaysFail:
        def __call__(self, t):
            raise Exception("no data")
    svc = MarketDataService(max_retries=1, backoff_base=0.0, ttl_seconds=0, price_provider=AlwaysFail())
    with pytest.raises(MarketDataDownloadError):
        svc.get_price("ZZZTMP2")


def test_retry_exhaustion_raises():
    class AlwaysFail:
        def __init__(self):
            self.calls = 0
        def __call__(self, t):
            self.calls += 1
            raise Exception("boom")
    svc = MarketDataService(max_retries=2, backoff_base=0.0, ttl_seconds=0, price_provider=AlwaysFail())
    with pytest.raises(MarketDataDownloadError):
        svc.get_price("ZZZTMP3")
