import pandas as pd
from services.risk import drawdown_table, compute_drawdown_episodes


def test_drawdown_table_basic():
    # Create equity with two drawdowns
    eq = pd.Series(
        [100,110,120, 115,112,130, 125, 90, 92, 140],
        index=pd.date_range("2024-01-01", periods=10, freq="D")
    )
    table = drawdown_table(eq, top_n=5)
    assert not table.empty
    depths = table["Depth (%)"].astype(float)
    assert depths.min() < 0  # at least one negative depth


def test_drawdown_episodes_open_drawdown():
    eq = pd.Series([100, 105, 103, 101, 99, 98], index=pd.date_range("2024-01-01", periods=6, freq="D"))
    eps = compute_drawdown_episodes(eq)
    assert eps[-1]["open"] is True
    assert eps[-1]["recovery_date"] is None
