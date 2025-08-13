# Use the central settings and DB helpers
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import Optional

import pandas as pd

from app_settings import settings
from data.db import get_connection, init_db
from infra.logging import get_logger, new_correlation_id
from services.time import get_clock

# Ensure repository root is on sys.path for local execution
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    # Lower, strip, replace spaces and dashes with underscores
    rename = {c: c.strip().lower().replace(" ", "_").replace("-", "_") for c in df.columns}
    return df.rename(columns=rename)


def migrate_portfolio_csv(csv_path: Path, conn) -> dict:
    if not csv_path.exists():
        return {"skipped": True, "reason": "missing"}

    raw = pd.read_csv(csv_path)
    if raw.empty:
        return {"skipped": True, "reason": "empty"}

    df = _normalize_columns(raw)

    # Expected snapshot columns in CSV form; provide safe defaults
    for col, default in [
        ("date", ""),
        ("ticker", ""),
        ("shares", 0.0),
        ("cost_basis", 0.0),
        ("stop_loss", 0.0),
        ("current_price", 0.0),
        ("total_value", 0.0),
        ("pnl", 0.0),
        ("action", ""),
        ("cash_balance", 0.0),
        ("total_equity", 0.0),
    ]:
        if col not in df.columns:
            df[col] = default

    # Truncate and load full history to match CSV contents exactly
    conn.execute("DELETE FROM portfolio_history")
    try:
        df[
            [
                "date",
                "ticker",
                "shares",
                "cost_basis",
                "stop_loss",
                "current_price",
                "total_value",
                "pnl",
                "action",
                "cash_balance",
                "total_equity",
            ]
        ].to_sql("portfolio_history", conn, if_exists="append", index=False)
    except Exception:
        insert_hist = (
            "INSERT INTO portfolio_history (date, ticker, shares, cost_basis, stop_loss, current_price, total_value, pnl, action, cash_balance, total_equity) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )
        for _, r in df.iterrows():
            conn.execute(
                insert_hist,
                (
                    str(r.get("date", "")),
                    str(r.get("ticker", "")),
                    float(r.get("shares", 0.0) or 0.0),
                    float(r.get("cost_basis", 0.0) or 0.0),
                    float(r.get("stop_loss", 0.0) or 0.0),
                    float(r.get("current_price", 0.0) or 0.0),
                    float(r.get("total_value", 0.0) or 0.0),
                    float(r.get("pnl", 0.0) or 0.0),
                    str(r.get("action", "")),
                    float(r.get("cash_balance", 0.0) or 0.0),
                    float(r.get("total_equity", 0.0) or 0.0),
                ),
            )

    # Derive current holdings for the portfolio table from last snapshot date
    # If multiple dates exist, pick the latest by string sort (YYYY-MM-DD expected)
    latest_date: Optional[str] = None
    if "date" in df.columns and df["date"].notna().any():
        latest_date = sorted([str(d) for d in df["date"].dropna().unique()])[-1]

    if latest_date:
        snap = df[df["date"] == latest_date].copy()
    else:
        snap = df.copy()

    # Exclude TOTAL row; portfolio.csv stores TOTAL in ticker column
    holdings = snap[snap["ticker"].str.upper() != "TOTAL"].copy()
    # Truncate portfolio and insert fresh
    conn.execute("DELETE FROM portfolio")
    insert_port = "INSERT INTO portfolio (ticker, shares, stop_loss, buy_price, cost_basis) VALUES (?, ?, ?, ?, ?)"
    for _, r in holdings.iterrows():
        ticker = str(r.get("ticker", "")).strip().upper()
        if not ticker:
            continue
        shares = float(r.get("shares", 0.0) or 0.0)
        stop_loss = float(r.get("stop_loss", 0.0) or 0.0)
        cost_basis = float(r.get("cost_basis", 0.0) or 0.0)
        # We don't have separate buy_price vs cost_basis in the CSV snapshots; set both to cost_basis
        conn.execute(insert_port, (ticker, shares, stop_loss, cost_basis, cost_basis))

    # Cash balance from TOTAL row of the latest snapshot
    cash_val = 0.0
    total_rows = (
        snap[snap["ticker"].str.upper() == "TOTAL"]
        if "ticker" in snap.columns
        else pd.DataFrame([])
    )
    if not total_rows.empty and "cash_balance" in total_rows.columns:
        try:
            cash_val = float(total_rows.iloc[-1]["cash_balance"] or 0.0)
        except Exception:
            cash_val = 0.0
    conn.execute("INSERT OR REPLACE INTO cash (id, balance) VALUES (0, ?)", (float(cash_val),))

    return {
        "skipped": False,
        "rows_history": int(df.shape[0]),
        "rows_portfolio": int(holdings.shape[0]),
        "cash": float(cash_val),
    }


def migrate_trade_log_csv(csv_path: Path, conn) -> dict:
    if not csv_path.exists():
        return {"skipped": True, "reason": "missing"}

    raw = pd.read_csv(csv_path)
    if raw.empty:
        return {"skipped": True, "reason": "empty"}

    df = _normalize_columns(raw)
    # Map common legacy column names to DB columns
    rename_map = {
        "date": "date",
        "ticker": "ticker",
        "shares_bought": "shares_bought",
        "buy_price": "buy_price",
        "cost_basis": "cost_basis",
        "pnl": "pnl",
        "reason": "reason",
        "shares_sold": "shares_sold",
        "sell_price": "sell_price",
        # Potential variants
        "shares": "shares_bought",  # if legacy file used a single "shares" for buys
    }
    for src, dst in list(rename_map.items()):
        if src in df.columns and dst not in df.columns:
            df[dst] = df[src]

    # Ensure all required columns exist
    for col, default in [
        ("date", ""),
        ("ticker", ""),
        ("shares_bought", 0.0),
        ("buy_price", 0.0),
        ("cost_basis", 0.0),
        ("pnl", 0.0),
        ("reason", ""),
        ("shares_sold", 0.0),
        ("sell_price", 0.0),
    ]:
        if col not in df.columns:
            df[col] = default

    # Truncate and load
    conn.execute("DELETE FROM trade_log")
    try:
        df[
            [
                "date",
                "ticker",
                "shares_bought",
                "buy_price",
                "cost_basis",
                "pnl",
                "reason",
                "shares_sold",
                "sell_price",
            ]
        ].to_sql("trade_log", conn, if_exists="append", index=False)
    except Exception:
        insert_log = (
            "INSERT INTO trade_log (date, ticker, shares_bought, buy_price, cost_basis, pnl, reason, shares_sold, sell_price) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )
        for _, r in df.iterrows():
            conn.execute(
                insert_log,
                (
                    str(r.get("date", "")),
                    str(r.get("ticker", "")),
                    float(r.get("shares_bought", 0.0) or 0.0),
                    float(r.get("buy_price", 0.0) or 0.0),
                    float(r.get("cost_basis", 0.0) or 0.0),
                    float(r.get("pnl", 0.0) or 0.0),
                    str(r.get("reason", "")),
                    float(r.get("shares_sold", 0.0) or 0.0),
                    float(r.get("sell_price", 0.0) or 0.0),
                ),
            )

    return {"skipped": False, "rows": int(df.shape[0])}


def backup_files(files: list[Path], backup_root: Path) -> list[Path]:
    timestamp = get_clock().now().strftime("%Y%m%d_%H%M%S")
    dest_dir = backup_root / f"migration_{timestamp}"
    dest_dir.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []
    for f in files:
        if f.exists():
            target = dest_dir / f.name
            shutil.copy2(f, target)
            copied.append(target)
    return copied


def main():
    parser = argparse.ArgumentParser(
        description="Migrate legacy CSV data into SQLite DB and back up CSVs."
    )
    parser.add_argument(
        "--portfolio-csv",
        type=Path,
        default=settings.paths.portfolio_csv,
        help="Path to portfolio CSV snapshot",
    )
    parser.add_argument(
        "--trade-log-csv",
        type=Path,
        default=settings.paths.trade_log_csv,
        help="Path to trade log CSV",
    )
    parser.add_argument(
        "--db-file", type=Path, default=settings.paths.db_file, help="Path to SQLite DB file"
    )
    parser.add_argument(
        "--backup-dir",
        type=Path,
        default=settings.paths.data_dir / "backups",
        help="Directory to write CSV backups",
    )
    args = parser.parse_args()

    # Ensure DB points to the requested file and has schema
    try:
        from data import db as db_module  # late import to avoid circulars

        db_module.DB_FILE = Path(args.db_file)
    except Exception:
        pass
    init_db()
    with get_connection() as conn:
        results = {}
        results["portfolio"] = migrate_portfolio_csv(Path(args.portfolio_csv), conn)
        results["trade_log"] = migrate_trade_log_csv(Path(args.trade_log_csv), conn)

    # Back up the CSVs that were actually present
    to_backup = [Path(args.portfolio_csv), Path(args.trade_log_csv)]
    copied = backup_files(to_backup, Path(args.backup_dir))

    # Summary output (JSON)
    logger = get_logger(__name__)
    logger.info(
        "Migration complete",
        extra={
            "event": "csv_to_sqlite_migration",
            "results": results,
            "backups": [str(p) for p in copied],
        },
    )


if __name__ == "__main__":
    with new_correlation_id():
        main()
