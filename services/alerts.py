"""Alert evaluation utilities.

Supports:
  * Drawdown threshold (TOTAL equity)
  * Top1 concentration threshold
  * 95% VaR threshold (historical, excess returns)

Writes alert events to data/alerts/alerts.log (JSON lines) and latest snapshot to alerts_state.json.
"""
from __future__ import annotations

from pathlib import Path
import json
import time
import pandas as pd
from app_settings import settings
from services.risk import compute_risk_block
import dataclasses

ALERTS_DIR = settings.paths.data_dir / "alerts"
ALERTS_DIR.mkdir(parents=True, exist_ok=True)
ALERT_LOG = ALERTS_DIR / "alerts.log"
ALERT_STATE = ALERTS_DIR / "alerts_state.json"

def _append_event(event: dict) -> None:  # pragma: no cover - simple IO
    try:
        with open(ALERT_LOG, "a") as f:
            f.write(json.dumps(event) + "\n")
    except Exception:
        pass

def _write_state(state: dict) -> None:  # pragma: no cover - simple IO
    try:
        ALERT_STATE.write_text(json.dumps(state, indent=2))
    except Exception:
        pass

def evaluate_alerts(history_df: pd.DataFrame) -> list[dict]:
    events: list[dict] = []
    if history_df.empty:
        return events
    risk = compute_risk_block(history_df, use_cache=False)
    now_ts = time.time()
    # Drawdown: risk.max_drawdown_pct negative
    if abs(risk.max_drawdown_pct) >= settings.alert_drawdown_pct:
        events.append({
            "type": "drawdown_threshold",
            "value_pct": risk.max_drawdown_pct,
            "threshold_pct": -settings.alert_drawdown_pct,
            "ts": now_ts,
        })
    if risk.concentration_top1_pct >= settings.alert_concentration_top1_pct:
        events.append({
            "type": "concentration_top1",
            "value_pct": risk.concentration_top1_pct,
            "threshold_pct": settings.alert_concentration_top1_pct,
            "ts": now_ts,
        })
    if getattr(risk, "var_95_pct", 0.0) >= settings.alert_var95_pct:
        events.append({
            "type": "var95",
            "value_pct": getattr(risk, "var_95_pct", 0.0),
            "threshold_pct": settings.alert_var95_pct,
            "ts": now_ts,
        })
    if events:
        for e in events:
            _append_event(e)
    state = {
        "last_eval_ts": now_ts,
        "risk_snapshot": dataclasses.asdict(risk),
        "open_events": events,
    }
    _write_state(state)
    return events

def load_alert_state() -> dict:
    if ALERT_STATE.exists():
        try:
            return json.loads(ALERT_STATE.read_text())
        except Exception:
            return {}
    return {}

__all__ = ["evaluate_alerts", "load_alert_state"]
