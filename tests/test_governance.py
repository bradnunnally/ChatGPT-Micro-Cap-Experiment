import json

from services.governance import (
    seed_default_rules,
    list_active_rules,
    get_rule_by_code,
    log_audit_event,
    verify_audit_chain,
    save_config_snapshot,
    log_breach,
    upsert_policy_rule,
    list_breaches,
    update_breach_status,
)
from data.db import get_connection
import pandas as pd
from services.rebalance import execute_orders


def test_governance_block_position_weight():
    seed_default_rules()  # Ensure rules present
    # Adjust rule threshold lower for test to force block (direct DB update)
    with get_connection() as conn:
        conn.execute("UPDATE policy_rule SET threshold=0.05 WHERE code='MAX_POSITION_WEIGHT'")
    # Start with small existing position to avoid initial seeding bypass logic
    pf = pd.DataFrame([
        {"ticker": "ABC", "shares": 10.0, "buy_price": 100.0, "cost_basis": 1000.0, "stop_loss": 0.0}
    ])
    cash = 10000.0
    # Large order pushing projected weight > 5%
    orders = [
        {"ticker": "ABC", "side": "BUY", "shares": 200.0, "est_price": 100.0}
    ]
    pf2, cash2, rep = execute_orders(
        pf, cash, orders, commit=True, enforce_governance=True, enforce_turnover_budget=False
    )
    row = rep.iloc[0]
    assert row.status == "blocked_governance"
    # Ensure no position size change
    assert float(pf2.loc[pf2.ticker == 'ABC', 'shares'].iloc[0]) == 10.0


def test_seed_and_load_rules():
    seed_default_rules()
    rules = list_active_rules()
    codes = {r.code for r in rules}
    assert "MAX_POSITION_WEIGHT" in codes
    assert "DAILY_TURNOVER_LIMIT" in codes
    r = get_rule_by_code("MAX_POSITION_WEIGHT")
    assert r is not None
    assert r.threshold == 0.10


def test_audit_event_chain_integrity():
    e1 = log_audit_event("test", {"n": 1})
    e2 = log_audit_event("test", {"n": 2})
    assert e1.hash != e2.hash
    assert verify_audit_chain()


def test_config_snapshot_chain():
    s1 = save_config_snapshot("risk_config", {"a": 1})
    s2 = save_config_snapshot("risk_config", {"a": 2})
    assert s1.hash != s2.hash


def test_breach_logging():
    b = log_breach("MAX_POSITION_WEIGHT", "error", {"pos": "XYZ", "weight": 0.2})
    assert b.rule_code == "MAX_POSITION_WEIGHT"
    with get_connection() as conn:
        row = conn.execute("SELECT COUNT(*) FROM breach_log").fetchone()
        assert row[0] >= 1


def test_rule_upsert_and_breach_status_update():
    # Upsert a new rule
    r = upsert_policy_rule("TEST_RULE", "position_weight", 0.05, "warn", True, {"note": 1})
    assert r.code == "TEST_RULE"
    # Create breach manually
    br = log_breach("TEST_RULE", "warn", {"w": 0.06})
    breaches = list_breaches(open_only=False)
    assert any(b.rule_code == "TEST_RULE" for b in breaches)
    update_breach_status(br.id, "acknowledged")
    breaches2 = list_breaches(open_only=False)
    updated = [b for b in breaches2 if b.id == br.id][0]
    assert updated.status == "acknowledged"
