"""Persistence utilities for saving/loading backtest runs.

Stores each run under data/backtests/<run_id>/ with:
  meta.json  -> parameters, metrics, identifiers
  equity.csv -> date,equity
  trades.csv -> optional trade/signal detail (can be large)

Design goals:
  * Pure stdlib + pandas (already a dependency)
  * Append-only; easy manual pruning
  * Robust to partial writes (write temp then atomic replace)
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Dict, Any
import json
import time
import uuid

import pandas as pd

from app_settings import settings
from services.backtest import BacktestResult
import glob


def load_grid_leaderboard(max_files: int = 10) -> pd.DataFrame:
    """Load recent SMA grid summary CSVs produced by scheduler.

    Returns a concatenated DataFrame with file timestamp & rank, limited to max_files most recent.
    Missing directory or no files -> empty DataFrame.
    """
    sched_dir = Path(settings.paths.data_dir) / "scheduler" / "grid_summaries"
    if not sched_dir.exists():
        return pd.DataFrame()
    files = sorted(sched_dir.glob("sma_grid_*.csv"), reverse=True)[:max_files]
    rows = []
    for f in files:
        try:
            df = pd.read_csv(f)
            df["_file"] = f.name
            # derive timestamp from filename pattern sma_grid_YYYYMMDD-HHMMSS.csv
            ts_part = f.stem.replace("sma_grid_", "")
            df["_ts"] = pd.to_datetime(ts_part, format="%Y%m%d-%H%M%S", errors="coerce")
            rows.append(df)
        except Exception:
            continue
    if not rows:
        return pd.DataFrame()
    out = pd.concat(rows, ignore_index=True)
    return out


def _root() -> Path:
    root = Path(settings.paths.data_dir) / "backtests"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _atomic_write(path: Path, data: str | bytes, mode: str = "w") -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, mode) as f:  # type: ignore[arg-type]
        f.write(data)  # type: ignore[arg-type]
    tmp.replace(path)


def generate_run_id(label: str | None = None) -> str:
    ts = time.strftime("%Y%m%d-%H%M%S")
    short = uuid.uuid4().hex[:6]
    if label:
        safe = "".join(c for c in label.strip().replace(" ", "_") if c.isalnum() or c in ("-", "_"))[:40]
        if safe:
            return f"{ts}_{safe}_{short}"
    return f"{ts}_{short}"


def save_backtest(result: BacktestResult, label: str | None = None) -> str:
    run_id = generate_run_id(label)
    run_dir = _root() / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # Meta (json)
    meta: Dict[str, Any] = {
        "run_id": run_id,
        "timestamp": time.time(),
        "label": label,
        "ticker": result.ticker,
        "strategy": result.strategy_name or "unknown",
        "params": result.params or {},
        "metrics": result.metrics,
    }
    _atomic_write(run_dir / "meta.json", json.dumps(meta, indent=2))

    # Equity curve
    ec = result.equity_curve.reset_index()
    ec.columns = ["date", "equity"]
    _atomic_write(run_dir / "equity.csv", ec.to_csv(index=False))

    # Trades (optional; skip if empty)
    if not result.trades.empty:
        _atomic_write(run_dir / "trades.csv", result.trades.to_csv(index=False))
    return run_id


def list_runs(limit: int | None = None) -> pd.DataFrame:
    rows = []
    for meta_path in sorted(_root().glob("*/meta.json")):
        try:
            meta = json.loads(meta_path.read_text())
            rows.append(meta)
        except Exception:
            continue
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = df.sort_values("timestamp", ascending=False)
    if limit:
        df = df.head(limit)
    return df


def load_run(run_id: str) -> BacktestResult:
    run_dir = _root() / run_id
    meta_path = run_dir / "meta.json"
    if not meta_path.exists():
        raise FileNotFoundError(f"Unknown backtest run_id {run_id}")
    meta = json.loads(meta_path.read_text())
    equity_path = run_dir / "equity.csv"
    trades_path = run_dir / "trades.csv"
    equity_df = pd.read_csv(equity_path, parse_dates=["date"]).set_index("date")
    trades_df = pd.read_csv(trades_path) if trades_path.exists() else pd.DataFrame()
    res = BacktestResult(
        equity_curve=equity_df["equity"],
        trades=trades_df,
        metrics=meta.get("metrics", {}),
        params=meta.get("params"),
        ticker=meta.get("ticker"),
        strategy_name=meta.get("strategy"),
    )
    return res


def load_runs(run_ids: Iterable[str]) -> dict[str, BacktestResult]:
    out = {}
    for r in run_ids:
        try:
            out[r] = load_run(r)
        except Exception:
            continue
    return out
