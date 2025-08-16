import sqlite3
from services import risk_monitor
from services.governance import evaluate_pre_trade_rules, PolicyRule
from app_settings import settings
from data import db as dbmod


def test_compute_snapshot_handles_empty_db(tmp_path):
    db_file = tmp_path / "test.db"
    with sqlite3.connect(db_file) as conn:
        conn.execute("CREATE TABLE portfolio (ticker TEXT, shares REAL, buy_price REAL)")
        conn.execute("CREATE TABLE portfolio_history (date TEXT, total_equity REAL)")
        conn.execute("CREATE TABLE cash (id INTEGER PRIMARY KEY, balance REAL)")
    snap = risk_monitor.compute_snapshot(db_path=str(db_file))
    assert snap.equity == 0.0
    assert snap.top1_concentration_pct == 0.0


def test_emit_risk_events_logs(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    with sqlite3.connect(db_file) as conn:
        conn.execute("CREATE TABLE risk_event (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT DEFAULT CURRENT_TIMESTAMP, event_type TEXT NOT NULL, severity TEXT NOT NULL, payload_json TEXT, hash TEXT, prev_hash TEXT)")
        conn.execute("CREATE TABLE audit_event (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT DEFAULT CURRENT_TIMESTAMP, category TEXT, ref_type TEXT, ref_id TEXT, payload_json TEXT, hash TEXT, prev_hash TEXT)")
    # patch DB_FILE constant used by governance -> data.db.get_connection
    monkeypatch.setattr(dbmod, "DB_FILE", str(db_file))

    snap = risk_monitor.RiskSnapshot(1000, 100, 50, 70, 40, -20, 6)
    risk_monitor.emit_risk_events(snap)

    with sqlite3.connect(db_file) as conn:
        rows = conn.execute("SELECT event_type, severity FROM risk_event ORDER BY id").fetchall()
    types = [r[0] for r in rows]
    assert "concentration_top1" in types
    assert "concentration_top3" in types
    assert "drawdown" in types
    assert "volatility" in types
    assert "var95" in types


def test_exposure_scalar():
    scalar = risk_monitor.compute_exposure_scalar({"bear": 0.5, "high_vol": 0.3}, open_breaches=2)
    assert 0.4 <= scalar < 1.0
    assert scalar == max(0.4, scalar)


def test_new_rule_types_sector_and_notional(monkeypatch):
    import pandas as pd
    df = pd.DataFrame([
        {"ticker": "AAA", "shares": 10, "buy_price": 10.0},
        {"ticker": "BBB", "shares": 5, "buy_price": 20.0},
    ])
    rules = [
        PolicyRule(id=None, code="NOTIONAL", rule_type="max_trade_notional_pct", threshold=0.10, severity="error"),
        PolicyRule(id=None, code="SECTOR", rule_type="sector_aggregate_weight", threshold=0.40, severity="error"),
    ]
    sector_map = {"AAA": "TECH", "BBB": "TECH", "CCC": "TECH"}
    # Order that breaches both (large notional & sector concentration)
    result = evaluate_pre_trade_rules(df, cash=1000, order={"ticker": "CCC", "side": "BUY"}, exec_price=100, shares=10, rules=rules, sector_map=sector_map)
    reasons = {b['reason'] for b in result['breaches']}
    assert 'trade_notional_exceeded' in reasons
    assert 'sector_weight_exceeded' in reasons
