-- 0002_governance.sql
-- Phase 10 Step 1: Governance & Compliance base schema
BEGIN;

CREATE TABLE IF NOT EXISTS policy_rule (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    rule_type TEXT NOT NULL,
    threshold REAL,
    severity TEXT NOT NULL DEFAULT 'warn',
    active INTEGER NOT NULL DEFAULT 1,
    params_json TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_policy_rule_active ON policy_rule(active);

CREATE TABLE IF NOT EXISTS audit_event (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL DEFAULT (datetime('now')),
    category TEXT NOT NULL,
    ref_type TEXT,
    ref_id TEXT,
    payload_json TEXT NOT NULL,
    hash TEXT NOT NULL,
    prev_hash TEXT
);
CREATE INDEX IF NOT EXISTS idx_audit_event_category_ts ON audit_event(category, ts);

CREATE TABLE IF NOT EXISTS config_snapshot (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL DEFAULT (datetime('now')),
    kind TEXT NOT NULL,
    content_json TEXT NOT NULL,
    hash TEXT NOT NULL,
    prev_hash TEXT
);
CREATE INDEX IF NOT EXISTS idx_config_snapshot_kind_ts ON config_snapshot(kind, ts);

CREATE TABLE IF NOT EXISTS breach_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL DEFAULT (datetime('now')),
    rule_code TEXT NOT NULL,
    severity TEXT NOT NULL,
    context_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    auto_action TEXT
);
CREATE INDEX IF NOT EXISTS idx_breach_log_rule_ts ON breach_log(rule_code, ts);

-- Record migration
INSERT OR IGNORE INTO schema_version(version) VALUES ('0002');
COMMIT;
