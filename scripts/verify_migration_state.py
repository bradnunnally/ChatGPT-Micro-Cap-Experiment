"""Quick migration state verifier for release smoke.

Usage: python scripts/verify_migration_state.py
Exits 0 if expected tables/columns exist, non-zero otherwise.
"""
from __future__ import annotations
import sqlite3, sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from app_settings import settings

REQUIRED_TABLES = {
    'policy_rule', 'audit_event', 'config_snapshot', 'breach_log', 'risk_event',
    'turnover_budget', 'turnover_ledger'
}
REQUIRED_COLUMNS = {
    ('breach_log', 'notes'),
    ('policy_rule', 'rule_type'),
    ('risk_event', 'hash'),
}

def main() -> int:
    db = settings.paths.db_file
    missing_tables = []
    missing_columns = []
    with sqlite3.connect(db) as conn:
        existing = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for t in REQUIRED_TABLES:
            if t not in existing:
                missing_tables.append(t)
        for (table, column) in REQUIRED_COLUMNS:
            try:
                cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
                if column not in cols:
                    missing_columns.append(f"{table}.{column}")
            except Exception:
                missing_columns.append(f"{table}.{column}")
    if missing_tables or missing_columns:
        print("Migration verification FAILED")
        if missing_tables:
            print("Missing tables:", ", ".join(missing_tables))
        if missing_columns:
            print("Missing columns:", ", ".join(missing_columns))
        return 1
    print("Migration verification OK")
    return 0

if __name__ == '__main__':
    sys.exit(main())
