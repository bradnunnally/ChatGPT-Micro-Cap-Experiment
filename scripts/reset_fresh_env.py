#!/usr/bin/env python3
"""Reset the trading database to a pristine empty state (no positions, zero cash).

Usage:
  NO_DEV_SEED=1 python scripts/reset_fresh_env.py
or
  NO_DEV_SEED=1 make reset-fresh  (if you add a Makefile target)

This differs from clear_db.py which seeds $10,000.00. Here we explicitly want a
blank starting point for experiments or screenshots.
"""
from __future__ import annotations
import os
import sqlite3
from config.settings import settings
from data.db import init_db
from infra.logging import get_logger, new_correlation_id

logger = get_logger(__name__)

def reset(empty_cash: bool = True) -> None:
    db_path = settings.paths.db_file
    os.environ['NO_DEV_SEED'] = '1'  # ensure portfolio.load_portfolio doesn't auto-seed

    # Ensure schema exists
    init_db()
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        # Wipe relevant tables
        for table in ("portfolio", "cash", "trade_log", "portfolio_history"):
            try:
                cur.execute(f"DELETE FROM {table}")
            except Exception as e:  # pragma: no cover
                logger.error("table_clear_failed", extra={"table": table, "error": str(e)})
        if not empty_cash:
            # Optionally seed a starting cash (rare use; default is zero cash)
            cur.execute("INSERT OR REPLACE INTO cash (id, balance) VALUES (0, ?)", (0.0,))
        conn.commit()
        logger.info("fresh_reset_complete", extra={"cash_seeded": not empty_cash})
    finally:
        conn.close()

if __name__ == '__main__':
    with new_correlation_id():
        reset(empty_cash=True)
