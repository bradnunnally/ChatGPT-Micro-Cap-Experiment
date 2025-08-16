-- 0003_phase11_risk_governance.sql
-- Phase 11: Risk monitor & extended governance schema adjustments
BEGIN;

-- Add optional category to policy_rule if not exists
ALTER TABLE policy_rule ADD COLUMN category TEXT DEFAULT 'governance'; -- ignore error if already exists

-- Add notes column to breach_log if not exists
ALTER TABLE breach_log ADD COLUMN notes TEXT; -- ignore error if already exists

-- Risk event table (separate hash chain)
CREATE TABLE IF NOT EXISTS risk_event (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL DEFAULT (datetime('now')),
    event_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    hash TEXT NOT NULL,
    prev_hash TEXT
);
CREATE INDEX IF NOT EXISTS idx_risk_event_type_ts ON risk_event(event_type, ts);

INSERT OR IGNORE INTO schema_version(version) VALUES ('0003');
COMMIT;
