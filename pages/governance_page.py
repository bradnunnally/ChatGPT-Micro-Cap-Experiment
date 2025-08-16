import pandas as pd
import streamlit as st
from pathlib import Path

from components.nav import navbar
from services.governance import (
    list_active_rules,
    verify_audit_chain,
    save_config_snapshot,
    seed_default_rules,
    upsert_policy_rule,
    list_breaches,
    update_breach_status,
)
from data.db import get_connection

st.set_page_config(page_title="Governance", layout="wide", initial_sidebar_state="collapsed")
navbar(Path(__file__).name)

st.subheader("Governance & Compliance Console")

seed_default_rules()

col_rules, col_chain, col_snap = st.columns([2, 1.5, 1.5])

with col_rules:
    st.markdown("### Active Policy Rules")
    rules = list_active_rules()
    if not rules:
        st.info("No active rules.")
    else:
        df_rules = pd.DataFrame([
            {
                "Code": r.code,
                "Type": r.rule_type,
                "Threshold": r.threshold,
                "Severity": r.severity,
                "Active": r.active,
                "Params": r.params(),
            }
            for r in rules
        ])
        st.dataframe(df_rules, use_container_width=True)

    st.markdown("#### Add / Update Rule")
    with st.form("rule_form"):
        code = st.text_input("Code", value="MAX_POSITION_WEIGHT")
        rule_type = st.selectbox("Rule Type", ["position_weight"], index=0)
        threshold = st.number_input("Threshold", value=0.10, min_value=0.0, max_value=1.0, step=0.01, format="%.2f")
        severity = st.selectbox("Severity", ["warn", "error"], index=1)
        active = st.checkbox("Active", value=True)
        submitted = st.form_submit_button("Upsert Rule")
        if submitted:
            r = upsert_policy_rule(code, rule_type, threshold, severity, active)
            st.success(f"Rule {r.code} saved (threshold {r.threshold})")

    st.markdown("#### Simulate Config Snapshot")
    with st.form("snapshot_form"):
        kind = st.text_input("Kind", value="risk_config")
        content_raw = st.text_area("JSON Content", value='{"example": 1}', height=120)
        submit_snap = st.form_submit_button("Save Snapshot")
        if submit_snap:
            try:
                import json
                payload = json.loads(content_raw)
                snap = save_config_snapshot(kind, payload)
                st.success(f"Snapshot {snap.id} saved (hash {snap.hash[:10]}…)")
            except Exception as e:  # pragma: no cover - user input errors
                st.error(f"Invalid JSON: {e}")

with col_chain:
    st.markdown("### Audit Chain Integrity")
    if st.button("Verify Chain"):
        ok = verify_audit_chain()
        if ok:
            st.success("Audit hash chain intact ✅")
        else:
            st.error("Audit hash chain BROKEN ❌")

    st.markdown("#### Recent Audit Events")
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT ts, category, ref_type, ref_id, substr(hash,1,10) as hash, substr(prev_hash,1,10) as prev_hash FROM audit_event ORDER BY id DESC LIMIT 25"
        ).fetchall()
    if rows:
        st.dataframe(pd.DataFrame(rows, columns=["ts","category","ref_type","ref_id","hash","prev_hash"]))
    else:
        st.caption("No audit events yet.")

with col_snap:
    st.markdown("### Recent Config Snapshots")
    with get_connection() as conn:
        snaps = conn.execute(
            "SELECT ts, kind, substr(hash,1,10) as hash, substr(prev_hash,1,10) as prev_hash FROM config_snapshot ORDER BY id DESC LIMIT 15"
        ).fetchall()
    if snaps:
        st.dataframe(pd.DataFrame(snaps, columns=["ts","kind","hash","prev_hash"]))
    else:
        st.caption("No snapshots.")

    st.markdown("### Breaches")
    breaches = list_breaches(limit=50)
    if breaches:
        df_breach = pd.DataFrame([
            {
                "ID": b.id,
                "ts": b.ts,
                "rule_code": b.rule_code,
                "severity": b.severity,
                "status": b.status,
                "context": b.context_json[:80],
            }
            for b in breaches
        ])
        st.dataframe(df_breach, use_container_width=True)
        with st.form("breach_update"):
            breach_id = st.number_input("Breach ID", min_value=1, step=1)
            new_status = st.selectbox("New Status", ["open", "acknowledged", "closed"], index=1)
            upd = st.form_submit_button("Update Status")
            if upd:
                update_breach_status(int(breach_id), new_status)
                st.success(f"Breach {breach_id} -> {new_status}")
    else:
        st.caption("No breaches logged.")

    st.markdown("### Recent Risk Events")
    with get_connection() as conn:
        r_events = conn.execute(
            "SELECT ts, event_type, severity, substr(hash,1,10) as hash, substr(prev_hash,1,10) as prev_hash, substr(payload_json,1,60) as payload FROM risk_event ORDER BY id DESC LIMIT 25"
        ).fetchall()
    if r_events:
        st.dataframe(pd.DataFrame(r_events, columns=["ts","event_type","severity","hash","prev_hash","payload"]))
    else:
        st.caption("No risk events.")

st.divider()
st.markdown(
    """**Usage Notes:**
- Governance blocking is OFF by default in `execute_orders`; pass `enforce_governance=True` to enable pre-trade rule evaluation.
- Position weight rule blocks BUY orders that would exceed configured threshold (except initial single-position seeding).
- All breaches generate both a `breach_log` row and an `audit_event` with hash chaining.
- Config snapshots are independently hash-chained per `kind`.
"""
)
