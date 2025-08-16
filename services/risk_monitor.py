"""Risk Monitor (Phase 11)

Computes periodic risk snapshots and emits hash-chained risk events.
Designed for on-demand invocation (no background thread).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, Optional
import sqlite3
import statistics as stats

from app_settings import settings
from services.governance import log_risk_event


@dataclass
class RiskSnapshot:
    equity: float
    cash: float
    top1_concentration_pct: float
    top3_concentration_pct: float
    rolling_20d_vol_pct: float
    max_drawdown_pct: float
    var_95_pct: float


def _load_portfolio(conn: sqlite3.Connection) -> Dict[str, float]:
    rows = conn.execute("SELECT ticker, shares, buy_price FROM portfolio").fetchall()
    out = {}
    for t, sh, bp in rows:
        try:
            out[str(t).upper()] = float(sh) * float(bp)
        except Exception:
            continue
    return out


def _equity_cash_history(conn: sqlite3.Connection):
    rows = conn.execute(
        "SELECT date, total_equity FROM portfolio_history WHERE total_equity != '' ORDER BY date DESC LIMIT 40"
    ).fetchall()
    return [float(r[1]) for r in rows if r[1] not in (None, "")]  # newest first


def compute_snapshot(db_path: Optional[str | None] = None) -> RiskSnapshot:
    """Compute a point-in-time snapshot.

    Accepts optional db_path to facilitate isolated unit tests without monkeypatching
    global settings. When not provided falls back to settings.paths.db_file.
    """
    db_path = db_path or str(settings.paths.db_file)
    with sqlite3.connect(db_path) as conn:
        pos_values = _load_portfolio(conn)
        total_equity_rows = _equity_cash_history(conn)
        equity = total_equity_rows[0] if total_equity_rows else 0.0
        # Est cash (fallback 0) from cash table if present
        try:
            cash_row = conn.execute("SELECT balance FROM cash WHERE id=0").fetchone()
        except sqlite3.OperationalError:
            cash_row = None
        cash = float(cash_row[0]) if cash_row and cash_row[0] not in (None, "") else 0.0

    if equity <= 0:
        return RiskSnapshot(0.0, cash, 0.0, 0.0, 0.0, 0.0, 0.0)

    # Concentration
    vals = sorted(pos_values.values(), reverse=True)
    top1 = (vals[0] / equity * 100.0) if vals else 0.0
    top3 = (sum(vals[:3]) / equity * 100.0) if vals else 0.0

    # Rolling vol approximation (std of last 20 daily equity returns)
    returns = []
    if len(total_equity_rows) > 1:
        eq_list = list(reversed(total_equity_rows))  # oldest first
        for a, b in zip(eq_list, eq_list[1:]):
            if a > 0:
                returns.append((b / a) - 1)
    rolling_20d_vol_pct = (stats.pstdev(returns[-20:]) * (252 ** 0.5) * 100.0) if len(returns) >= 2 else 0.0

    # Max drawdown (approx from list)
    draw = 0.0
    peak = 0.0
    for v in reversed(total_equity_rows):  # chronological
        peak = max(peak, v)
        if peak > 0:
            dd = (v / peak - 1) * 100.0
            draw = min(draw, dd)
    max_drawdown_pct = draw

    # Simplistic VaR95 (quantile of returns *100)
    var_95_pct = 0.0
    if returns:
        sorted_r = sorted(returns)
        idx = int(0.05 * len(sorted_r))
        idx = min(max(idx, 0), len(sorted_r) - 1)
        var_95_pct = -sorted_r[idx] * 100.0

    return RiskSnapshot(equity, cash, top1, top3, rolling_20d_vol_pct, max_drawdown_pct, var_95_pct)


def emit_risk_events(snapshot: RiskSnapshot) -> None:
    # Threshold heuristics (can be rule-driven later)
    if snapshot.top1_concentration_pct > 40:
        log_risk_event("concentration_top1", "warn", {"value": snapshot.top1_concentration_pct})
    if snapshot.top3_concentration_pct > 60:
        log_risk_event("concentration_top3", "warn", {"value": snapshot.top3_concentration_pct})
    if snapshot.max_drawdown_pct < -15:
        log_risk_event("drawdown", "warn", {"value": snapshot.max_drawdown_pct})
    if snapshot.rolling_20d_vol_pct > 35:
        log_risk_event("volatility", "warn", {"value": snapshot.rolling_20d_vol_pct})
    if snapshot.var_95_pct > 5:
        log_risk_event("var95", "warn", {"value": snapshot.var_95_pct})


__all__ = ["RiskSnapshot", "compute_snapshot", "emit_risk_events"]


def compute_exposure_scalar(regime_probs: Optional[Dict[str, float]], open_breaches: int) -> float:
        """Blend regime probabilities & governance pressure into a gross exposure scalar.

        Heuristic:
            - Base scalar 1.00
            - Bear prob reduces: scalar -= 0.4 * bear_prob
            - High_vol prob reduces: scalar -= 0.3 * high_vol_prob
            - Cap at minimum 0.4
            - Additional reduction 0.05 per open breach (capped 0.25)
        """
        scalar = 1.0
        if regime_probs:
                bear = regime_probs.get("bear", 0.0)
                high_vol = regime_probs.get("high_vol", 0.0)
                scalar -= 0.4 * bear
                scalar -= 0.3 * high_vol
        scalar -= min(open_breaches * 0.05, 0.25)
        return max(0.4, round(scalar, 4))

__all__.append("compute_exposure_scalar")
