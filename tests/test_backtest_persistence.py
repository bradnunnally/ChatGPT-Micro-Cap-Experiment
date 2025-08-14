import pandas as pd
from services.backtest import simple_moving_average_strategy
from services.backtest_store import save_backtest, list_runs, load_run
from app_settings import settings


def test_backtest_save_and_load(tmp_path, monkeypatch):
    orig = settings.data_dir
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    prices = pd.Series([100 + i for i in range(50)], index=pd.date_range("2024-01-01", periods=50, freq="D"))
    res = simple_moving_average_strategy(prices, fast=3, slow=10)
    res.ticker = "TEST"
    run_id = save_backtest(res, label="unit_test")
    runs = list_runs()
    assert not runs.empty
    assert run_id in runs.run_id.values
    loaded = load_run(run_id)
    assert abs(loaded.metrics["total_return_pct"] - res.metrics["total_return_pct"]) < 1e-9
    # Allow extra cost params added later; ensure core params match
    assert {k: loaded.params[k] for k in ("fast","slow")} == {"fast": 3, "slow": 10}
    assert len(loaded.equity_curve) == len(res.equity_curve)
    monkeypatch.setattr(settings, "data_dir", orig)
