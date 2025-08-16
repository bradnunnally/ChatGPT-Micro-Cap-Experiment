"""Governance & Compliance foundational services (Phase 10 Step 1).

Provides:
- PolicyRule CRUD and seeding
- Append-only hash chained audit log
- Config snapshot storage (hash chained)
- Breach logging for rule violations
- Chain verification utilities

All tables created in migration 0002_governance.sql.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any
import json
import hashlib
from contextlib import contextmanager

from data.db import get_connection, transaction

# ------------------------- Data Models -------------------------

@dataclass
class PolicyRule:
    id: Optional[int]
    code: str
    rule_type: str
    threshold: Optional[float] = None
    severity: str = "warn"
    active: bool = True
    params_json: Optional[str] = None
    updated_at: Optional[str] = None

    def params(self) -> Dict[str, Any]:
        if self.params_json:
            try:
                return json.loads(self.params_json)
            except json.JSONDecodeError:
                return {}
        return {}

@dataclass
class AuditEvent:
    id: Optional[int]
    ts: Optional[str]
    category: str
    ref_type: Optional[str]
    ref_id: Optional[str]
    payload_json: str
    hash: str
    prev_hash: Optional[str]

@dataclass
class ConfigSnapshot:
    id: Optional[int]
    ts: Optional[str]
    kind: str
    content_json: str
    hash: str
    prev_hash: Optional[str]

@dataclass
class BreachLog:
    id: Optional[int]
    ts: Optional[str]
    rule_code: str
    severity: str
    context_json: str
    status: str
    auto_action: Optional[str]

# ------------------------- Hash Helpers -------------------------

def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode('utf-8')).hexdigest()

# ------------------------- Policy Rules -------------------------

DEFAULT_RULES: List[Dict[str, Any]] = [
    {
        "code": "MAX_POSITION_WEIGHT",
        "rule_type": "position_weight",
        "threshold": 0.10,
        "severity": "error",
        "params": {"basis": "portfolio_equity"},
    },
    {
        "code": "DAILY_TURNOVER_LIMIT",
        "rule_type": "turnover",
        "threshold": 0.25,
        "severity": "warn",
        "params": {"window": "1d"},
    },
]

def seed_default_rules() -> None:
    with transaction() as conn:
        cur = conn.cursor()
        for rule in DEFAULT_RULES:
            params_json = json.dumps(rule.get("params", {}), sort_keys=True)
            cur.execute(
                """
                INSERT INTO policy_rule (code, rule_type, threshold, severity, active, params_json)
                VALUES (?, ?, ?, ?, 1, ?)
                ON CONFLICT(code) DO UPDATE SET
                    rule_type=excluded.rule_type,
                    threshold=excluded.threshold,
                    severity=excluded.severity,
                    params_json=excluded.params_json,
                    updated_at=datetime('now')
                """,
                (rule["code"], rule["rule_type"], rule.get("threshold"), rule["severity"], params_json),
            )

def get_rule_by_code(code: str) -> Optional[PolicyRule]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, code, rule_type, threshold, severity, active, params_json, updated_at FROM policy_rule WHERE code=?",
            (code,),
        ).fetchone()
        if row:
            return PolicyRule(*row)
    return None

def list_active_rules() -> List[PolicyRule]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, code, rule_type, threshold, severity, active, params_json, updated_at FROM policy_rule WHERE active=1"
        ).fetchall()
        return [PolicyRule(*r) for r in rows]

# ------------------------- Audit Chain -------------------------

def _get_last_audit_hash(conn) -> Optional[str]:
    row = conn.execute("SELECT hash FROM audit_event ORDER BY id DESC LIMIT 1").fetchone()
    return row[0] if row else None

def log_audit_event(category: str, payload: Dict[str, Any], ref_type: Optional[str] = None, ref_id: Optional[str] = None) -> AuditEvent:
    payload_json = json.dumps(payload, sort_keys=True)
    with transaction() as conn:
        prev_hash = _get_last_audit_hash(conn)
        base = f"{prev_hash or ''}|{category}|{ref_type or ''}|{ref_id or ''}|{payload_json}"
        h = _sha256(base)
        cur = conn.execute(
            """
            INSERT INTO audit_event (category, ref_type, ref_id, payload_json, hash, prev_hash)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (category, ref_type, ref_id, payload_json, h, prev_hash),
        )
        new_id = cur.lastrowid
        row = conn.execute("SELECT id, ts, category, ref_type, ref_id, payload_json, hash, prev_hash FROM audit_event WHERE id=?", (new_id,)).fetchone()
        return AuditEvent(*row)

def verify_audit_chain(limit: Optional[int] = None) -> bool:
    """Verify hash chain integrity. Returns True if intact."""
    query = "SELECT id, category, ref_type, ref_id, payload_json, hash, prev_hash FROM audit_event ORDER BY id ASC"
    if limit:
        query += f" LIMIT {int(limit)}"
    with get_connection() as conn:
        rows = conn.execute(query).fetchall()
    prev = None
    for row in rows:
        _id, category, ref_type, ref_id, payload_json, h, prev_hash = row
        base = f"{prev_hash or ''}|{category}|{ref_type or ''}|{ref_id or ''}|{payload_json}"
        calc = _sha256(base)
        if calc != h:
            return False
        if prev != prev_hash:
            return False
        prev = h
    return True

# ------------------------- Config Snapshots -------------------------

def _get_last_snapshot_hash(conn, kind: str) -> Optional[str]:
    row = conn.execute("SELECT hash FROM config_snapshot WHERE kind=? ORDER BY id DESC LIMIT 1", (kind,)).fetchone()
    return row[0] if row else None

def save_config_snapshot(kind: str, content: Dict[str, Any]) -> ConfigSnapshot:
    content_json = json.dumps(content, sort_keys=True)
    with transaction() as conn:
        prev_hash = _get_last_snapshot_hash(conn, kind)
        base = f"{prev_hash or ''}|{kind}|{content_json}"
        h = _sha256(base)
        cur = conn.execute(
            "INSERT INTO config_snapshot (kind, content_json, hash, prev_hash) VALUES (?, ?, ?, ?)",
            (kind, content_json, h, prev_hash),
        )
        new_id = cur.lastrowid
        row = conn.execute("SELECT id, ts, kind, content_json, hash, prev_hash FROM config_snapshot WHERE id=?", (new_id,)).fetchone()
        return ConfigSnapshot(*row)

# ------------------------- Breach Logging -------------------------

def log_breach(rule_code: str, severity: str, context: Dict[str, Any], auto_action: Optional[str] = None) -> BreachLog:
    context_json = json.dumps(context, sort_keys=True)
    with transaction() as conn:
        cur = conn.execute(
            """
            INSERT INTO breach_log (rule_code, severity, context_json, auto_action) VALUES (?, ?, ?, ?)
            """,
            (rule_code, severity, context_json, auto_action),
        )
        new_id = cur.lastrowid
        row = conn.execute(
            "SELECT id, ts, rule_code, severity, context_json, status, auto_action FROM breach_log WHERE id=?",
            (new_id,),
        ).fetchone()
        return BreachLog(*row)

# ------------------------- Initialization -------------------------

def initialize_governance() -> None:
    """Seed default rules and log an initialization event (idempotent)."""
    seed_default_rules()
    log_audit_event("governance_init", {"default_rules": [r["code"] for r in DEFAULT_RULES]})

__all__ = [
    "PolicyRule",
    "AuditEvent",
    "ConfigSnapshot",
    "BreachLog",
    "seed_default_rules",
    "get_rule_by_code",
    "list_active_rules",
    "log_audit_event",
    "verify_audit_chain",
    "save_config_snapshot",
    "log_breach",
    "initialize_governance",
]


# ------------------------- Pre-Trade Rule Evaluation (Step 2) -------------------------

def evaluate_pre_trade_rules(
    portfolio_df,
    cash: float,
    order: Dict[str, Any],
    exec_price: float,
    shares: float,
    rules: Optional[List[PolicyRule]] = None,
    sector_map: Optional[Dict[str, str]] = None,
    pending_orders: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Evaluate active governance rules for a proposed order.

    Currently supports:
      - position_weight: blocks if projected weight > threshold (only if position exists already)

    Returns dict with keys:
      will_block: bool
      breaches: list of {rule_code, reason, details}
    """
    from pandas import DataFrame  # local import (tests may not have pandas early)

    pf = portfolio_df.copy() if isinstance(portfolio_df, DataFrame) else portfolio_df
    if rules is None:
        rules = list_active_rules()

    t = str(order.get("ticker", "")).upper()
    side = str(order.get("side", "")).upper()
    breaches: List[Dict[str, Any]] = []
    if side != "BUY":
        return {"will_block": False, "breaches": breaches}

    # Compute projected equity & position value
    # Existing position row
    mask = (pf.get("ticker") == t) if hasattr(pf, "get") else []
    existing_shares = 0.0
    if hasattr(pf, "loc") and mask is not None and getattr(mask, "any", lambda: False)():  # type: ignore
        try:
            existing_shares = float(pf.loc[mask, "shares"].iloc[0])
        except Exception:
            existing_shares = 0.0
    projected_shares = existing_shares + shares
    projected_pos_value = projected_shares * exec_price
    # Approx equity: current equity + cost (since cash outflow becomes position value)
    current_equity = cash + float((pf.get("shares", []) * pf.get("buy_price", [])).sum()) if hasattr(pf, "get") else cash
    projected_equity = current_equity if current_equity > 0 else exec_price * shares
    if projected_equity <= 0:
        projected_equity = exec_price * shares
    projected_equity = max(projected_equity, 1e-9)
    projected_weight = projected_pos_value / projected_equity

    # Pre-compute projected aggregated sector exposure if needed
    sector_exposure = {}
    if sector_map and hasattr(pf, 'iterrows'):
        try:
            for _, row in pf.iterrows():
                sec = sector_map.get(str(row.get('ticker','')).upper())
                if not sec:
                    continue
                val = float(row.get('shares',0)) * float(row.get('buy_price',0))
                sector_exposure[sec] = sector_exposure.get(sec, 0.0) + val
        except Exception:
            sector_exposure = {}

    for rule in rules:
        if not rule.active:
            continue
        if rule.rule_type == "position_weight" and rule.threshold is not None:
            # Allow initial seeding (no existing position and portfolio otherwise empty)
            if existing_shares <= 0 and projected_equity == projected_pos_value:
                continue
            if projected_weight > rule.threshold + 1e-12:
                reason = "position_weight_exceeded"
                detail = {
                    "ticker": t,
                    "projected_weight": projected_weight,
                    "threshold": rule.threshold,
                }
                breaches.append({"rule_code": rule.code, "reason": reason, "details": detail})

        if rule.rule_type == "max_trade_notional_pct" and rule.threshold is not None:
            # Approx notional as exec_price * shares; divide by equity
            notional = exec_price * shares
            equity_basis = current_equity if current_equity > 0 else notional
            if equity_basis > 0 and (notional / equity_basis) > rule.threshold + 1e-12:
                breaches.append({
                    "rule_code": rule.code,
                    "reason": "trade_notional_exceeded",
                    "details": {"notional": notional, "pct": notional / equity_basis, "threshold": rule.threshold},
                })
        if rule.rule_type == "sector_aggregate_weight" and rule.threshold is not None and sector_map:
            # Determine impacted sector and projected weight
            sec = sector_map.get(t)
            if sec:
                # Add projected pos value to sector exposure
                cur_val = sector_exposure.get(sec, 0.0)
                proj_sector_val = cur_val + projected_pos_value
                if projected_equity > 0 and (proj_sector_val / projected_equity) > rule.threshold + 1e-12:
                    breaches.append({
                        "rule_code": rule.code,
                        "reason": "sector_weight_exceeded",
                        "details": {"sector": sec, "projected_sector_weight": proj_sector_val / projected_equity, "threshold": rule.threshold},
                    })

    will_block = any(breaches)
    return {"will_block": will_block, "breaches": breaches}


def record_breaches(breaches: List[Dict[str, Any]], severity_override: Optional[str] = None) -> None:
    """Persist breach & audit records for each breach dict."""
    for b in breaches:
        rule_code = b.get("rule_code")
        details = b.get("details", {})
        severity = severity_override or "error"
        log_breach(rule_code, severity, details)
        log_audit_event("breach", {"rule_code": rule_code, **details})

__all__.extend(["evaluate_pre_trade_rules", "record_breaches"])


# ------------------------- Rule & Breach Management (Step 3) -------------------------

def upsert_policy_rule(
    code: str,
    rule_type: str,
    threshold: Optional[float] = None,
    severity: str = "warn",
    active: bool = True,
    params: Optional[Dict[str, Any]] = None,
) -> PolicyRule:
    """Create or update a policy rule by code."""
    params_json = json.dumps(params or {}, sort_keys=True)
    with transaction() as conn:
        conn.execute(
            """
            INSERT INTO policy_rule (code, rule_type, threshold, severity, active, params_json)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(code) DO UPDATE SET
              rule_type=excluded.rule_type,
              threshold=excluded.threshold,
              severity=excluded.severity,
              active=excluded.active,
              params_json=excluded.params_json,
              updated_at=datetime('now')
            """,
            (code, rule_type, threshold, severity, 1 if active else 0, params_json),
        )
        row = conn.execute(
            "SELECT id, code, rule_type, threshold, severity, active, params_json, updated_at FROM policy_rule WHERE code=?",
            (code,),
        ).fetchone()
    log_audit_event("rule_upsert", {"code": code, "rule_type": rule_type, "threshold": threshold, "active": active})
    return PolicyRule(*row)


def update_breach_status(breach_id: int, status: str) -> None:
    """Update breach status (e.g., open -> acknowledged / closed)."""
    with transaction() as conn:
        conn.execute("UPDATE breach_log SET status=? WHERE id=?", (status, breach_id))
    log_audit_event("breach_status_update", {"breach_id": breach_id, "status": status})


def list_breaches(limit: int = 100, open_only: bool = False) -> List[BreachLog]:
    sql = "SELECT id, ts, rule_code, severity, context_json, status, auto_action FROM breach_log"
    if open_only:
        sql += " WHERE status='open'"
    sql += " ORDER BY id DESC LIMIT ?"
    with get_connection() as conn:
        rows = conn.execute(sql, (limit,)).fetchall()
    return [BreachLog(*r) for r in rows]

__all__.extend(["upsert_policy_rule", "update_breach_status", "list_breaches"])


# ------------------------- Risk Event Logging (Phase 11) -------------------------

def _get_last_risk_event_hash(conn) -> Optional[str]:
    row = conn.execute("SELECT hash FROM risk_event ORDER BY id DESC LIMIT 1").fetchone()
    return row[0] if row else None


def log_risk_event(event_type: str, severity: str, payload: Dict[str, Any]) -> dict:
    payload_json = json.dumps(payload, sort_keys=True)
    with transaction() as conn:
        prev_hash = _get_last_risk_event_hash(conn)
        base = f"{prev_hash or ''}|{event_type}|{severity}|{payload_json}"
        h = _sha256(base)
        cur = conn.execute(
            "INSERT INTO risk_event (event_type, severity, payload_json, hash, prev_hash) VALUES (?, ?, ?, ?, ?)",
            (event_type, severity, payload_json, h, prev_hash),
        )
        rid = cur.lastrowid
        row = conn.execute(
            "SELECT id, ts, event_type, severity, payload_json, hash, prev_hash FROM risk_event WHERE id=?",
            (rid,),
        ).fetchone()
    log_audit_event("risk_event", {"event_type": event_type, "severity": severity, **payload})
    return {
        "id": row[0],
        "ts": row[1],
        "event_type": row[2],
        "severity": row[3],
        "payload_json": row[4],
        "hash": row[5],
        "prev_hash": row[6],
    }


def update_breach_notes(breach_id: int, notes: str) -> None:
    with transaction() as conn:
        conn.execute("UPDATE breach_log SET notes=? WHERE id=?", (notes, breach_id))
    log_audit_event("breach_notes_update", {"breach_id": breach_id, "notes_len": len(notes)})

__all__.extend(["log_risk_event", "update_breach_notes"])
