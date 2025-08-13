from datetime import date, timedelta
import pandas as pd

from data_providers import SyntheticDataProvider


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


## Removed yfinance provider cache test after migration to Finnhub-only architecture.
