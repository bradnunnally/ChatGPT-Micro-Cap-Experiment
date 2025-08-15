import math
from services.turnover_budget import (
    TurnoverBudgetConfig,
    init_turnover_budget,
    record_trade_notional,
    get_window_usage,
    load_turnover_config,
    evaluate_turnover,
    clear_turnover_ledger,
)


def test_init_and_load(tmp_path, monkeypatch):
    # Use actual DB; assuming get_connection points to project DB, so just initialize
    init_turnover_budget(TurnoverBudgetConfig(window_days=10, max_pct=0.5))
    cfg = load_turnover_config()
    assert cfg.window_days == 10
    assert math.isclose(cfg.max_pct, 0.5, rel_tol=1e-6)


def test_record_and_enforce_budget():
    init_turnover_budget(TurnoverBudgetConfig(window_days=30, max_pct=0.25))
    clear_turnover_ledger()
    # Simulate trades with equity 1000
    equity = 1000.0
    # First trade 100 notional -> 10% if avg equity=1000
    res1 = record_trade_notional("AAA", "BUY", 100.0, equity)
    assert res1["blocked"] is False
    assert 0.09 < res1["window_pct"] < 0.11
    # Second trade pushes to 20%
    res2 = record_trade_notional("BBB", "SELL", 100.0, equity)
    assert res2["blocked"] is False
    # Third trade breaches 25% -> blocked flag on last trade
    res3 = record_trade_notional("CCC", "BUY", 200.0, equity)
    assert res3["blocked"] is True
    usage = get_window_usage()
    assert usage["used_pct"] >= res3["window_pct"]
    assert usage["remaining_pct"] <= 0.0 or usage["remaining_pct"] < 0.01


def test_evaluate_turnover_prediction():
    init_turnover_budget(TurnoverBudgetConfig(window_days=30, max_pct=0.30))
    clear_turnover_ledger()
    equity = 1000.0
    record_trade_notional("AAA", "BUY", 100.0, equity)  # 10%
    pred = evaluate_turnover(150.0, equity)  # would bring total to 25%
    assert pred["will_block"] is False
    assert 0.24 < pred["predicted_pct"] < 0.26
    pred2 = evaluate_turnover(250.0, equity)  # would bring to 35% -> block
    assert pred2["will_block"] is True
