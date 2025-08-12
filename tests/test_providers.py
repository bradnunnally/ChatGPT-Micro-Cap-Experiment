from datetime import date, timedelta
import pandas as pd

from data_providers import SyntheticDataProvider, YFinanceDataProvider


def test_synthetic_provider_determinism():
    start = date.today() - timedelta(days=10)
    end = date.today()
    p1 = SyntheticDataProvider(seed=999)
    p2 = SyntheticDataProvider(seed=999)
    df1 = p1.get_history("AAPL", start, end)
    df2 = p2.get_history("AAPL", start, end)
    assert not df1.empty and not df2.empty
    pd.testing.assert_series_equal(df1["close"], df2["close"])
    assert set(["open", "high", "low", "close", "volume"]).issubset(df1.columns)


def test_yfinance_provider_cache(monkeypatch, tmp_path):
    # Simulate yfinance download and ensure cache reuse
    calls = {"count": 0}
    start = date(2024, 1, 1)
    end = date(2024, 1, 10)

    import pandas as pd
    import numpy as np
    import importlib

    def fake_download(ticker, start=None, end=None, auto_adjust=True, progress=False):
        calls["count"] += 1
        dates = pd.date_range(start=start, end=end, freq="B")
        return pd.DataFrame(
            {
                "Date": dates,
                "Open": np.linspace(10, 20, len(dates)),
                "High": np.linspace(11, 21, len(dates)),
                "Low": np.linspace(9, 19, len(dates)),
                "Close": np.linspace(10.5, 20.5, len(dates)),
                "Volume": np.random.randint(1000, 5000, len(dates)),
            }
        ).set_index("Date")

    yf = importlib.import_module("yfinance")
    monkeypatch.setattr(yf, "download", fake_download)

    provider = YFinanceDataProvider(cache_dir=tmp_path)
    df_first = provider.get_history("AAPL", start, end, force_refresh=False)
    assert calls["count"] == 1
    df_second = provider.get_history("AAPL", start, end, force_refresh=False)
    assert calls["count"] == 1  # cache hit
    pd.testing.assert_frame_equal(df_first, df_second)
    provider.get_history("AAPL", start, end, force_refresh=True)
    assert calls["count"] == 2
