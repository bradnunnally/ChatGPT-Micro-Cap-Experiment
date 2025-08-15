"""Turnover budget ledger service.

Purpose: enforce a rolling turnover budget limiting cumulative trade
notional over a window (default 30 days) to a fraction of average
portfolio equity, supporting adaptive risk discipline.

Design:
 - turnover_budget table stores single row config (id=0)
 - turnover_ledger records each executed trade notional and running window metric
 - API allows recording trades, computing remaining budget, and blocking new orders
 - Pure functions around DB to keep unit-testable; window computation in SQL + Python.
"""
from __future__ import annotations
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, List, Tuple, Dict, Any

from data.db import get_connection

@dataclass
class TurnoverBudgetConfig:
    window_days: int = 30
    max_pct: float = 0.80  # cumulative notional / avg equity cap


def init_turnover_budget(cfg: TurnoverBudgetConfig | None = None) -> None:
    cfg = cfg or TurnoverBudgetConfig()
    with get_connection() as conn:
        cur = conn.execute("SELECT 1 FROM turnover_budget WHERE id=0")
        if cur.fetchone() is None:
            conn.execute(
                "INSERT INTO turnover_budget(id, window_days, max_pct, reset_timestamp) VALUES (0,?,?,?)",
                (cfg.window_days, cfg.max_pct, datetime.now(timezone.utc).isoformat()),
            )
        else:
            conn.execute(
                "UPDATE turnover_budget SET window_days=?, max_pct=? WHERE id=0",
                (cfg.window_days, cfg.max_pct),
            )
        conn.commit()


def load_turnover_config() -> TurnoverBudgetConfig:
    with get_connection() as conn:
        cur = conn.execute("SELECT window_days, max_pct FROM turnover_budget WHERE id=0")
        row = cur.fetchone()
        if not row:
            return TurnoverBudgetConfig()
        return TurnoverBudgetConfig(window_days=int(row[0]), max_pct=float(row[1]))


def _window_bounds(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


def record_trade_notional(ticker: str, side: str, notional: float, equity_snapshot: float) -> Dict[str, Any]:
    cfg = load_turnover_config()
    cutoff = _window_bounds(cfg.window_days)
    now = datetime.now(timezone.utc)
    with get_connection() as conn:
        # Prune old rows (optional; kept simple)
        conn.execute("DELETE FROM turnover_ledger WHERE timestamp < ?", (cutoff.isoformat(),))
        # Insert new trade
        conn.execute(
            "INSERT INTO turnover_ledger(timestamp, ticker, side, notional, equity_snapshot, blocked) VALUES (?,?,?,?,?,0)",
            (now.isoformat(), ticker, side.upper(), float(notional), float(equity_snapshot)),
        )
        # Recompute cumulative window stats
        cur = conn.execute(
            "SELECT SUM(notional) as total_notional, AVG(equity_snapshot) as avg_eq FROM turnover_ledger"
        )
        total_notional, avg_eq = cur.fetchone()
        total_notional = float(total_notional or 0.0)
        avg_eq = float(avg_eq or 0.0)
        pct = total_notional / avg_eq if avg_eq > 0 else 0.0
        blocked = 1 if pct > cfg.max_pct else 0
        if blocked:
            # mark last row blocked
            conn.execute("UPDATE turnover_ledger SET blocked=1 WHERE id = (SELECT MAX(id) FROM turnover_ledger)")
        conn.commit()
        return {
            "window_days": cfg.window_days,
            "max_pct": cfg.max_pct,
            "total_notional": total_notional,
            "avg_equity": avg_eq,
            "window_pct": pct,
            "remaining_pct": max(0.0, cfg.max_pct - pct),
            "blocked": bool(blocked),
        }


def get_window_usage() -> Dict[str, float]:
    cfg = load_turnover_config()
    with get_connection() as conn:
        cur = conn.execute("SELECT SUM(notional), AVG(equity_snapshot) FROM turnover_ledger")
        total, avg_eq = cur.fetchone()
        total = float(total or 0.0)
        avg_eq = float(avg_eq or 0.0)
        pct = total / avg_eq if avg_eq > 0 else 0.0
        return {
            "window_days": cfg.window_days,
            "max_pct": cfg.max_pct,
            "used_pct": pct,
            "remaining_pct": max(0.0, cfg.max_pct - pct),
            "total_notional": total,
            "avg_equity": avg_eq,
        }


def evaluate_turnover(additional_notional: float, equity_snapshot: float) -> Dict[str, Any]:
    """Predict post-trade turnover metrics without mutating state using current avg equity.

    Conservative: does not assume equity snapshot changes average materially.
    """
    cfg = load_turnover_config()
    with get_connection() as conn:
        cur = conn.execute("SELECT SUM(notional), AVG(equity_snapshot) FROM turnover_ledger")
        total, avg_eq = cur.fetchone()
        total = float(total or 0.0)
        avg_eq = float(avg_eq or equity_snapshot)
        predicted_total = total + float(additional_notional)
        predicted_pct = predicted_total / avg_eq if avg_eq > 0 else 0.0
        will_block = predicted_pct > cfg.max_pct
        current_pct = total / avg_eq if avg_eq > 0 else 0.0
        return {
            "window_days": cfg.window_days,
            "max_pct": cfg.max_pct,
            "current_total": total,
            "current_avg_equity": avg_eq,
            "current_pct": current_pct,
            "predicted_total": predicted_total,
            "predicted_avg_equity": avg_eq,
            "predicted_pct": predicted_pct,
            "remaining_pct": max(0.0, cfg.max_pct - current_pct),
            "will_block": will_block,
        }


def clear_turnover_ledger() -> None:
    """Delete all rows from turnover_ledger (testing / reset utility)."""
    with get_connection() as conn:
        conn.execute("DELETE FROM turnover_ledger")
        conn.commit()


__all__ = [
    "TurnoverBudgetConfig",
    "init_turnover_budget",
    "record_trade_notional",
    "get_window_usage",
    "load_turnover_config",
    "evaluate_turnover",
    "clear_turnover_ledger",
]
