#!/usr/bin/env python3
"""Apply pending SQL migrations in the migrations/ folder.

Simple, dependency-free alternative to Alembic suitable for this app.
Tracks applied versions in a schema_version table.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from app_settings import settings

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def ensure_schema_version(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """
    )


def get_applied_versions(conn: sqlite3.Connection) -> set[str]:
    ensure_schema_version(conn)
    cur = conn.execute("SELECT version FROM schema_version")
    return {row[0] for row in cur.fetchall()}


def apply_migration(conn: sqlite3.Connection, path: Path) -> None:
    with path.open("r", encoding="utf-8") as f:
        sql = f.read()
    conn.executescript(sql)


def main() -> None:
    db_path = settings.paths.db_file
    conn = sqlite3.connect(str(db_path))
    # Enable WAL/synchronous for safety
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=3000;")
    except Exception:
        pass

    try:
        applied = get_applied_versions(conn)
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            version = path.stem.split("_")[0]
            if version not in applied:
                apply_migration(conn, path)
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
