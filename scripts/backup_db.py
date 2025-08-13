#!/usr/bin/env python3
from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

from app_settings import settings
from infra.logging import get_logger, new_correlation_id
from services.time import get_clock


def backup(dst_dir: str | None = None) -> Path:
    data_dir = Path(settings.paths.data_dir)
    db_path = Path(settings.paths.db_file)
    out_dir = Path(dst_dir) if dst_dir else data_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = get_clock().now().strftime("%Y%m%d_%H%M%S")
    backup_path = out_dir / f"trading_backup_{stamp}.sqlite"

    try:
        with sqlite3.connect(str(db_path)) as src, sqlite3.connect(str(backup_path)) as dst:
            src.backup(dst)
    except Exception:
        shutil.copy2(db_path, backup_path)
    return backup_path


if __name__ == "__main__":
    logger = get_logger(__name__)
    with new_correlation_id():
        path = backup()
        logger.info("Backup created", extra={"event": "db_backup", "path": str(path)})
