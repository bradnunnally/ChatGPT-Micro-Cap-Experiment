#!/usr/bin/env python3
"""Simple script to clear the trading database and reset to default state."""

import os
import sqlite3
from pathlib import Path

from config.settings import settings
from infra.logging import get_logger, new_correlation_id

logger = get_logger(__name__)


def clear_database() -> None:
    db_path = str(settings.paths.db_file)

    if not os.path.exists(db_path):
        logger.error(
            "Database file not found.",
            extra={"event": "db_clear", "status": "missing", "db_path": db_path},
        )
        return

    logger.info(
        "Clearing database", extra={"event": "db_clear", "status": "starting", "db_path": db_path}
    )

    try:
        # Ensure directory and connect
        Path(settings.paths.data_dir).mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Clear all tables
        tables = ["portfolio", "cash", "trade_log", "portfolio_history"]

        for table in tables:
            try:
                cursor.execute(f"DELETE FROM {table}")
                rows_deleted = cursor.rowcount
                logger.info(
                    "Cleared table",
                    extra={"event": "db_clear", "table": table, "rows_deleted": rows_deleted},
                )
            except sqlite3.Error as e:
                logger.error(
                    "Error clearing table",
                    extra={"event": "db_clear", "table": table, "error": str(e)},
                )

        # Insert default cash balance of $10,000
        try:
            cursor.execute("INSERT INTO cash (balance) VALUES (?)", (10000.0,))
            logger.info("Set initial cash balance", extra={"event": "db_clear", "cash": 10000.0})
        except sqlite3.Error as e:
            logger.error("Error setting cash balance", extra={"event": "db_clear", "error": str(e)})

        # Commit changes
        conn.commit()
        conn.close()

        logger.info(
            "Database cleared successfully", extra={"event": "db_clear", "status": "success"}
        )
        logger.info(
            "Ready to start fresh - you can now run the app!",
            extra={"event": "db_clear", "next": "run_app"},
        )

    except sqlite3.Error as e:
        logger.error("Database error", extra={"event": "db_clear", "error": str(e)})
    except Exception as e:
        logger.error("Unexpected error", extra={"event": "db_clear", "error": str(e)})


if __name__ == "__main__":
    with new_correlation_id():
        clear_database()
