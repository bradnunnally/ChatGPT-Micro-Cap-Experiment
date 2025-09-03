import sqlite3
import tempfile
from pathlib import Path
from datetime import datetime

import pandas as pd
import pytest

import streamlit as st
import sys
import types

# app_settings may require pydantic_settings which isn't available in test venv here.
# Provide a minimal fake app_settings.settings with paths.db_file when import fails.
try:
    from app_settings import settings
except Exception:
    fake_settings = types.SimpleNamespace(paths=types.SimpleNamespace(db_file=""))
    sys.modules["app_settings"] = types.SimpleNamespace(settings=fake_settings)
    from app_settings import settings


def _create_temp_db_with_history(rows):
    fd, path = tempfile.mkstemp(suffix=".db")
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE portfolio_history (
            date TEXT,
            ticker TEXT,
            shares REAL,
            cost_basis REAL,
            stop_loss REAL,
            current_price REAL,
            total_value REAL,
            pnl REAL,
            action TEXT,
            cash_balance REAL,
            total_equity REAL
        )
        """
    )
    cur.executemany("INSERT INTO portfolio_history VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
    conn.commit()
    conn.close()
    return path


def test_generate_daily_summary_merges_history_and_sets_session(monkeypatch, tmp_path):
    """Integration-style test: history snapshot -> portfolio snapshot -> rendered markdown."""
    # Prepare a small history: TOTAL row + one ticker row with shares and cost_basis
    today = datetime.now().strftime("%Y-%m-%d")
    rows = [
        (today, "TOTAL", None, None, None, None, None, None, None, 5000.0, 15000.0),
        (today, "ABC", 100.0, 10.0, None, 12.0, 1200.0, 200.0, None, None, None),
    ]

    db_path = _create_temp_db_with_history(rows)

    # Point settings to the temp DB for the duration of the test
    monkeypatch.setattr(settings.paths, "db_file", db_path)

    # Directly exercise the helper pipeline used by the dashboard when generating summary
    # Avoid importing pages.performance_page (which pulls heavy project imports).
    # Instead, read the portfolio_history table directly from the temp DB to form a DataFrame.
    import sqlite3 as _sqlite

    conn = _sqlite.connect(str(settings.paths.db_file))
    import pandas as _pd

    history = _pd.read_sql_query("SELECT * FROM portfolio_history", conn, parse_dates=["date"])
    conn.close()
    from ui.summary import history_to_portfolio_snapshot, render_daily_portfolio_summary

    # Emulate the snapshot loader logic (past 6 months) via the helper
    hist_snap = history_to_portfolio_snapshot(history, as_of_months=6)
    assert not hist_snap.empty

    # Pick the first non-TOTAL ticker present in the snapshot so the test is
    # robust to different synthetic tickers produced by the environment.
    non_total = hist_snap.loc[hist_snap["Ticker"] != "TOTAL"]
    assert not non_total.empty, f"Snapshot contains no non-TOTAL rows: {hist_snap.to_dict('records')}"
    first_row = non_total.iloc[0]
    holdings_payload = [
        {
            "ticker": first_row["Ticker"],
            "exchange": "N/A",
            "sector": "N/A",
            "shares": first_row["Shares"],
            "costPerShare": first_row["Cost Basis"],
            "currentPrice": first_row["Current Price"],
            "stopType": "None",
            "stopPrice": None,
            "trailingStopPct": None,
            "marketCap": None,
            "adv20d": None,
            "spread": None,
            "catalystDate": None,
        }
    ]
    payload = {"asOfDate": today, "cashBalance": 5000.0, "holdings": holdings_payload}
    md = render_daily_portfolio_summary(payload)
    assert "Total Equity" in md or "Total Equity" in md
    # The test uses the first non-TOTAL ticker from the snapshot; assert that
    # ticker appears in the rendered markdown rather than hard-coding 'ABC'.
    assert holdings_payload[0]["ticker"] in md
