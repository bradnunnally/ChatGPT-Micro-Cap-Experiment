from datetime import date, timedelta
import pandas as pd

from micro_data_providers import SyntheticDataProviderExt


def test_synthetic_shapes_and_determinism():
    start = date.today() - timedelta(days=30)
    end = date.today()
    p1 = SyntheticDataProviderExt(seed=123)
    p2 = SyntheticDataProviderExt(seed=123)
    df1 = p1.get_daily_candles("AAA", start, end)
    df2 = p2.get_daily_candles("AAA", start, end)
    assert set(["date", "open", "high", "low", "close", "volume"]).issubset(df1.columns)
    assert len(df1) == len(df2) and not df1.empty
    pd.testing.assert_series_equal(df1["close"], df2["close"], check_names=False)
