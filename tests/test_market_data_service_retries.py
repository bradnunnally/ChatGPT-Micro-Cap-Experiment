import types
import pandas as pd
import pytest
from services.core.market_data_service import MarketDataService, NoMarketDataError, MarketDataDownloadError

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

def test_retry_then_success(monkeypatch):
    # Enable dev stage but return empty history so code proceeds to network path with pd bound
    monkeypatch.setattr("services.core.market_data_service.is_dev_stage", lambda: True)
    class EmptyProvider:
        def get_history(self, *a, **k):
            import pandas as _pd
            return _pd.DataFrame()
    monkeypatch.setattr("services.core.market_data_service.get_provider", lambda: EmptyProvider())
    monkeypatch.setattr("services.core.market_data_service.time", types.SimpleNamespace(time=lambda: 0, sleep=lambda s: None))
    # First two attempts raise generic exceptions, third returns price
    seq = [Exception("net"), Exception("net2"), 111.0]
    dummy = DummyYF(seq)
    monkeypatch.setattr("services.core.market_data_service.yf", dummy)

    monkeypatch.setattr("services.core.market_data_service.MarketDataService._load_disk_cache", lambda self, p: {})
    svc = MarketDataService(max_retries=3, backoff_base=0.0, ttl_seconds=0)
    price = svc.get_price("ZZZTMP1")
    assert price == 111.0


def test_no_market_data_returns_none(monkeypatch):
    monkeypatch.setattr("services.core.market_data_service.is_dev_stage", lambda: True)
    class EmptyProvider:
        def get_history(self, *a, **k):
            import pandas as _pd
            return _pd.DataFrame()
    monkeypatch.setattr("services.core.market_data_service.get_provider", lambda: EmptyProvider())
    monkeypatch.setattr("services.core.market_data_service.time", types.SimpleNamespace(time=lambda: 0, sleep=lambda s: None))
    from services.core.market_data_service import NoMarketDataError
    # Force download empty then history empty -> NoMarketDataError -> returns None
    class YFEmpty:
        def download(self, *a, **k):
            return pd.DataFrame()
        class TickerCls:
            def history(self, period="5d"):
                return pd.DataFrame()
        def Ticker(self, symbol):
            return YFEmpty.TickerCls()
    monkeypatch.setattr("services.core.market_data_service.yf", YFEmpty())
    monkeypatch.setattr("services.core.market_data_service.MarketDataService._load_disk_cache", lambda self, p: {})
    svc = MarketDataService(max_retries=1, backoff_base=0.0, ttl_seconds=0)
    price = svc.get_price("ZZZTMP2")
    assert price is None


def test_retry_exhaustion_raises(monkeypatch):
    monkeypatch.setattr("services.core.market_data_service.is_dev_stage", lambda: True)
    class EmptyProvider:
        def get_history(self, *a, **k):
            import pandas as _pd
            return _pd.DataFrame()
    monkeypatch.setattr("services.core.market_data_service.get_provider", lambda: EmptyProvider())
    monkeypatch.setattr("services.core.market_data_service.time", types.SimpleNamespace(time=lambda: 0, sleep=lambda s: None))
    # All attempts raise generic exception -> MarketDataDownloadError
    class YFFail:
        def download(self, *a, **k):
            raise Exception("boom")
        class TickerCls:
            def history(self, period="5d"):
                raise Exception("boom2")
        def Ticker(self, symbol):
            return YFFail.TickerCls()
    monkeypatch.setattr("services.core.market_data_service.yf", YFFail())
    monkeypatch.setattr("services.core.market_data_service.MarketDataService._load_disk_cache", lambda self, p: {})
    svc = MarketDataService(max_retries=2, backoff_base=0.0, ttl_seconds=0)
    with pytest.raises(MarketDataDownloadError):
        svc.get_price("ZZZTMP3")
