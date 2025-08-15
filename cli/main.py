#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import pandas as pd
import typer

# Local imports
from app_settings import settings
from data import portfolio as portfolio_data
from data.db import get_connection, init_db
from infra.logging import get_logger, new_correlation_id
from services.time import TradingCalendar, get_clock
from services.risk import attribute_pnl
from services.backtest import run_backtest, simple_moving_average_strategy
from services.benchmark import update_benchmark, get_benchmark_series, BENCHMARK_SYMBOL_DEFAULT
from services.risk_free import get_risk_free_rate
from services.scheduler import build_default_scheduler, Scheduler

app = typer.Typer(help="CLI tools for portfolio operations (snapshots, rebalance, import, export)")

logger = get_logger(__name__)


def _ensure_db_selected(db_file: Optional[Path]):
    if db_file:
        try:
            from data import db as db_module

            db_module.DB_FILE = Path(db_file)
        except Exception:
            pass


@app.command()
def snapshot(
    db_file: Optional[Path] = typer.Option(None, help="Path to SQLite DB file"),
    force: bool = typer.Option(False, help="Force snapshot even on non-trading days"),
    holidays: Optional[Path] = typer.Option(
        None, help="Optional path to JSON file with holiday dates ['YYYY-MM-DD', ...]"
    ),
):
    """Create and persist today's snapshot if a trading day.

    Skips weekends and optionally provided holidays, unless --force.
    """
    _ensure_db_selected(db_file)
    init_db()

    clock = get_clock()
    cal = TradingCalendar(clock=clock)
    if holidays and Path(holidays).exists():
        try:
            with open(holidays, "r") as f:
                cal.holidays = set(json.load(f))  # type: ignore[attr-defined]
        except Exception:
            pass
    elif settings.trading_holidays:
        try:
            cal.holidays = set(settings.trading_holidays)  # type: ignore[attr-defined]
        except Exception:
            pass

    today = clock.today().strftime("%Y-%m-%d")
    if not force and not cal.is_trading_day():
        typer.echo(f"Skipping snapshot: {today} is not a trading day")
        raise typer.Exit(code=0)

    # Load current state
    res = portfolio_data.load_portfolio()
    portfolio_df, cash, _ = res
    df = portfolio_data.save_portfolio_snapshot(portfolio_df, float(cash))

    # Also return/save snapshot info
    typer.echo(f"Snapshot created for {today} with {len(df)} rows (incl. TOTAL)")
    # Quick attribution summary if columns present
    if {"pnl_price", "pnl_position", "pnl_total_attr"}.issubset(set(df.columns)):
        try:
            by = df[df["ticker"] != "TOTAL"]["pnl_total_attr"].sum()
            typer.echo(f"Attribution total (sum pnl_total_attr across positions): {by:.2f}")
        except Exception:
            pass


@app.command()
def metrics():
    """Print in-process market data metrics & circuit breaker state."""
    try:
        from services.market import get_metrics
        m = get_metrics()
        for k, v in sorted(m.items()):
            typer.echo(f"{k}: {v}")
    except Exception as e:  # pragma: no cover - defensive
        typer.echo(f"metrics_error: {e}")


@app.command("metrics-reset")
def metrics_reset():
    """Reset metrics and circuit breaker state."""
    try:
        from services.market import reset_metrics, get_metrics
        reset_metrics()
        typer.echo("metrics_reset: ok")
        for k, v in sorted(get_metrics().items()):
            typer.echo(f"{k}: {v}")
    except Exception as e:  # pragma: no cover
        typer.echo(f"metrics_reset_error: {e}")


@app.command()
def rebalance(
    db_file: Optional[Path] = typer.Option(None, help="Path to SQLite DB file"),
    target_cash: Optional[float] = typer.Option(None, help="Optional target cash to maintain"),
):
    """Placeholder: Perform a simple rebalance policy.

    Currently a no-op scaffold that validates DB access and prints portfolio metrics.
    """
    _ensure_db_selected(db_file)
    init_db()
    with get_connection() as conn:
        # Simple metrics from portfolio
        try:
            df = pd.read_sql_query("SELECT * FROM portfolio", conn)
        except Exception:
            rows = conn.execute(
                "SELECT ticker, shares, stop_loss, buy_price, cost_basis FROM portfolio"
            ).fetchall()
            df = pd.DataFrame(
                rows, columns=["ticker", "shares", "stop_loss", "buy_price", "cost_basis"]
            )

    holdings = int(0 if df.empty else df.shape[0])
    total_cost = float(df["cost_basis"].sum()) if not df.empty else 0.0
    typer.echo(
        json.dumps(
            {
                "event": "rebalance-summary",
                "holdings": holdings,
                "total_cost_basis": round(total_cost, 2),
                "target_cash": target_cash,
            }
        )
    )


@app.command()
def export(
    out: Path = typer.Option(..., help="Output CSV file for portfolio history export"),
    db_file: Optional[Path] = typer.Option(None, help="Path to SQLite DB file"),
):
    """Export portfolio_history table to a CSV file."""
    _ensure_db_selected(db_file)
    init_db()
    with get_connection() as conn:
        df = pd.read_sql_query("SELECT * FROM portfolio_history ORDER BY date, ticker", conn)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    typer.echo(f"Exported {len(df)} rows to {out}")


@app.command()
def import_(
    csv: Path = typer.Option(..., help="CSV file with portfolio_history to import"),
    db_file: Optional[Path] = typer.Option(None, help="Path to SQLite DB file"),
):
    """Import portfolio_history from a CSV and derive current holdings and cash.

    This uses the same logic as the migrate_csv_to_sqlite script but scoped to a single CSV.
    """
    _ensure_db_selected(db_file)
    init_db()

    from scripts.migrate_csv_to_sqlite import migrate_portfolio_csv

    with get_connection() as conn:
        result = migrate_portfolio_csv(Path(csv), conn)
    typer.echo(json.dumps({"event": "import", "result": result}))


@app.command()
def backtest(
    db_file: Optional[Path] = typer.Option(None, help="Path to SQLite DB file"),
    ticker: str = typer.Option("TOTAL", help="Ticker to backtest (default uses TOTAL equity curve)"),
    fast: int = typer.Option(5, help="Fast moving average window"),
    slow: int = typer.Option(20, help="Slow moving average window"),
):
    """Run a simple SMA crossover backtest on historical prices/equity."""
    _ensure_db_selected(db_file)
    init_db()
    with get_connection() as conn:
        try:
            if ticker == "TOTAL":
                df = pd.read_sql_query(
                    "SELECT date, total_equity as price FROM portfolio_history WHERE ticker='TOTAL' ORDER BY date", conn,
                    parse_dates=["date"],
                )
            else:
                df = pd.read_sql_query(
                    "SELECT date, current_price as price FROM portfolio_history WHERE ticker=? ORDER BY date",
                    conn,
                    params=(ticker,),
                    parse_dates=["date"],
                )
        except Exception:
            typer.echo("backtest_error: unable to read history")
            raise typer.Exit(code=1)

    if df.empty:
        typer.echo("backtest_error: no data")
        raise typer.Exit(code=1)

    series = df.set_index("date")["price"].astype(float)
    def strat(prices):
        return simple_moving_average_strategy(prices, fast=fast, slow=slow)
    res = run_backtest(series, strat)  # type: ignore[arg-type]
    summary = {
        "event": "backtest",
        "ticker": ticker,
        "fast": fast,
        "slow": slow,
        **res.metrics,
        "final_equity_multiple": float(res.equity_curve.iloc[-1]),
        "num_trades": int(res.trades.shape[0]),
    }
    typer.echo(json.dumps(summary))


@app.command("benchmark-refresh")
def benchmark_refresh(symbol: str = typer.Option(BENCHMARK_SYMBOL_DEFAULT, help="Benchmark symbol (e.g. SPY)")):
    """Force a refresh of benchmark data from Stooq and print summary."""
    series = update_benchmark(symbol)
    last = series[-1]["date"] if series else "n/a"
    typer.echo(json.dumps({"event": "benchmark-refresh", "symbol": symbol, "points": len(series), "last_date": last}))


@app.command("risk-free")
def risk_free():
    """Show today's resolved risk-free annual rate (layered)."""
    rf = get_risk_free_rate()
    typer.echo(json.dumps({"event": "risk-free", "rate_annual": rf}))


@app.command("scheduler")
def scheduler(
    loop: bool = typer.Option(False, help="Run continuous loop"),
    iterations: int = typer.Option(1, help="Max iterations when not looping (each checks due jobs)"),
    sleep: float = typer.Option(1.0, help="Sleep seconds between iterations when looping"),
):
    """Run the default maintenance scheduler (benchmark, risk-free, snapshot).

    By default runs a single pass (once). Use --loop for continuous execution.
    """
    sched: Scheduler = build_default_scheduler()
    if loop:
        sched.run_loop(sleep_seconds=sleep)
    else:
        sched.run_loop(once=True, max_iterations=iterations)
    typer.echo(json.dumps({"event": "scheduler_state", "jobs": sched.jobs_state()}))


def main():
    with new_correlation_id():
        app()


if __name__ == "__main__":
    main()
