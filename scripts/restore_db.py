#!/usr/bin/env python3
from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

from app_settings import settings
from infra.logging import get_logger, new_correlation_id


def restore(backup_path: str) -> None:
    src = Path(backup_path)
    if not src.exists():
        raise FileNotFoundError(f"Backup not found: {backup_path}")

    db_path = Path(settings.paths.db_file)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with sqlite3.connect(str(src)) as bkp, sqlite3.connect(str(db_path)) as dst:
            # Replace database by restoring .backup onto destination
            bkp.backup(dst)
    except Exception:
        shutil.copy2(src, db_path)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        logger = get_logger(__name__)
        logger.error(
            "Usage: restore_db.py /path/to/backup.sqlite",
            extra={"event": "db_restore", "status": "usage_error"},
        )
        raise SystemExit(2)
    logger = get_logger(__name__)
    with new_correlation_id():
        restore(sys.argv[1])
        logger.info(
            "Restore complete",
            extra={"event": "db_restore", "status": "success", "backup": sys.argv[1]},
        )
