"""Lightweight in-process scheduler for recurring maintenance tasks.

Design goals:
  * No external dependencies (simple sleep loop)
  * Resilient to task exceptions (logs and moves on)
  * Observable state (job stats for UI / CLI)
  * Deterministic for tests (inject time / sleep functions)

Usage pattern:
  from services import scheduler
  sched = scheduler.Scheduler()
  sched.add_interval_job("benchmark_refresh", refresh_benchmark, seconds=86400)
  sched.run_loop(once=True)  # or loop

The loop is cooperative: each iteration checks due jobs and executes them sequentially.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, Any, List, Optional
import time
import traceback

try:  # reuse existing logging infra
    from infra.logging import get_logger
    logger = get_logger(__name__)
except Exception:  # pragma: no cover - fallback
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

TimeFn = Callable[[], float]
SleepFn = Callable[[float], None]
JobFn = Callable[[], Any]

@dataclass
class Job:
    name: str
    func: JobFn
    interval_seconds: float
    next_run: float
    last_run: Optional[float] = None
    last_status: Optional[str] = None  # 'ok' | 'error'
    last_error: Optional[str] = None
    run_count: int = 0
    total_duration: float = 0.0

    def due(self, now: float) -> bool:
        return now >= self.next_run

    def record(self, start: float, end: float, status: str, err: Optional[str]):
        self.last_run = start
        self.run_count += 1
        self.total_duration += (end - start)
        self.last_status = status
        self.last_error = err
        self.next_run = start + self.interval_seconds

    @property
    def avg_duration(self) -> float:
        return self.total_duration / self.run_count if self.run_count else 0.0

class Scheduler:
    def __init__(self, time_fn: TimeFn | None = None, sleep_fn: SleepFn | None = None):
        self._time = time_fn or time.time
        self._sleep = sleep_fn or time.sleep
        self._jobs: Dict[str, Job] = {}

    # Registration -------------------------------------------------
    def add_interval_job(self, name: str, func: JobFn, seconds: float, start_immediately: bool = True) -> None:
        if name in self._jobs:
            raise ValueError(f"Job '{name}' already registered")
        now = self._time()
        next_run = now if start_immediately else now + seconds
        self._jobs[name] = Job(name=name, func=func, interval_seconds=seconds, next_run=next_run)
        logger.info("scheduler_job_registered", extra={"job": name, "interval_sec": seconds})

    # Introspection ------------------------------------------------
    def jobs_state(self) -> List[Dict[str, Any]]:
        now = self._time()
        out: List[Dict[str, Any]] = []
        for j in self._jobs.values():
            out.append({
                "name": j.name,
                "interval_sec": j.interval_seconds,
                "next_run_in": max(0.0, j.next_run - now),
                "run_count": j.run_count,
                "avg_duration_ms": round(j.avg_duration * 1000, 2),
                "last_status": j.last_status,
                "last_error": j.last_error,
            })
        return out

    # Execution ----------------------------------------------------
    def run_pending(self) -> int:
        now = self._time()
        executed = 0
        for job in list(self._jobs.values()):
            if not job.due(now):
                continue
            start = self._time()
            err_txt = None
            status = "ok"
            try:
                job.func()
            except Exception:  # pragma: no cover
                status = "error"
                err_txt = traceback.format_exc(limit=3)
                logger.error("scheduler_job_error", extra={"job": job.name, "error": err_txt})
            end = self._time()
            job.record(start, end, status, err_txt)
            executed += 1
            logger.info("scheduler_job_run", extra={"job": job.name, "status": status, "duration_ms": round((end-start)*1000,2)})
        return executed

    def run_loop(self, sleep_seconds: float = 1.0, once: bool = False, max_iterations: int | None = None) -> None:
        iterations = 0
        while True:
            executed = self.run_pending()
            iterations += 1
            if once:
                break
            if max_iterations and iterations >= max_iterations:
                break
            self._sleep(0.01 if executed else sleep_seconds)

# Factory to build default scheduled tasks -----------------------------------
def build_default_scheduler() -> Scheduler:
    """Create scheduler with a richer set of maintenance jobs.

    Intervals are approximate; production could align to market calendar events.
    """
    from services.benchmark import update_benchmark, BENCHMARK_SYMBOL_DEFAULT
    from services.risk_free import get_risk_free_rate
    from data import portfolio as portfolio_data
    from services.fundamentals import batch_get_fundamentals
    from app_settings import settings
    from strategies.grid import run_sma_grid, summarize_results
    import pandas as pd
    import sqlite3

    sched = Scheduler()

    day = 86400
    hour = 3600
    fifteen_min = 900

    def benchmark_job():
        update_benchmark(BENCHMARK_SYMBOL_DEFAULT)

    def risk_free_job():
        get_risk_free_rate()

    def snapshot_job():
        res = portfolio_data.load_portfolio()
        portfolio_df, cash, _ = res
        portfolio_data.save_portfolio_snapshot(portfolio_df, float(cash))

    def fundamentals_job():
        # Refresh fundamentals for tickers currently held
        try:
            res = portfolio_data.load_portfolio()
            portfolio_df, _cash, _events = res
            tickers = portfolio_df.index.tolist()
            batch_get_fundamentals(tickers)
        except Exception:  # pragma: no cover - defensive
            pass

    def risk_metrics_job():
        # Placeholder: could compute rolling beta/vol and persist summary JSON
        # Kept lightweight to avoid duplication with on-demand computation.
        return

    def grid_backtest_job():
        # Run a tiny SMA grid on TOTAL equity and store summary CSV (rotating)
        try:
            db_path = settings.paths.db_file
            conn = sqlite3.connect(db_path)
            df = pd.read_sql_query("SELECT date, total_equity as price FROM portfolio_history WHERE ticker='TOTAL' ORDER BY date", conn, parse_dates=["date"])  # noqa: E501
            conn.close()
            if df.empty or len(df) < 50:
                return
            series = df.set_index("date")["price"].astype(float)
            results = run_sma_grid(series, fast_values=[3,5,8], slow_values=[15,25,40])
            summary = summarize_results(results)
            out_dir = (settings.paths.data_dir / "scheduler" / "grid_summaries")
            out_dir.mkdir(parents=True, exist_ok=True)
            ts = time.strftime("%Y%m%d-%H%M%S")
            summary.to_csv(out_dir / f"sma_grid_{ts}.csv", index=False)
            # Keep only latest N=10
            files = sorted(out_dir.glob("sma_grid_*.csv"))
            if len(files) > 10:
                for old in files[:-10]:
                    try: old.unlink()  # pragma: no cover - simple IO
                    except Exception: pass
        except Exception:  # pragma: no cover
            pass

    def alerts_job():
        # Evaluate alerts using full history frame
        try:
            from services.alerts import evaluate_alerts
            conn = sqlite3.connect(settings.paths.db_file)
            df = pd.read_sql_query("SELECT date, ticker, total_equity, total_value FROM portfolio_history ORDER BY date", conn, parse_dates=["date"])  # noqa: E501
            conn.close()
            evaluate_alerts(df)
        except Exception:  # pragma: no cover
            pass

    # Registration (stagger intervals)
    sched.add_interval_job("benchmark_refresh", benchmark_job, seconds=day)
    sched.add_interval_job("risk_free_refresh", risk_free_job, seconds=day)
    sched.add_interval_job("portfolio_snapshot", snapshot_job, seconds=day)
    sched.add_interval_job("fundamentals_refresh", fundamentals_job, seconds=day)
    sched.add_interval_job("risk_metrics_refresh", risk_metrics_job, seconds=hour)
    sched.add_interval_job("grid_sma_backtest", grid_backtest_job, seconds=hour * 6)
    sched.add_interval_job("alerts_eval", alerts_job, seconds=fifteen_min)

    return sched

__all__ = ["Scheduler", "build_default_scheduler"]
