import tempfile
from pathlib import Path
import pandas as pd

from config.providers import is_dev_stage
from data import portfolio as portfolio_mod


def test_dev_stage_seeding_with_history(monkeypatch):
    """Ensure dev_stage seeding includes historical data for portfolio tracking."""
    monkeypatch.setenv("APP_ENV", "dev_stage")
    assert is_dev_stage()

    tmpdir = tempfile.TemporaryDirectory()
    db_path = Path(tmpdir.name) / "history_test.db"
    monkeypatch.setattr("data.db.DB_FILE", db_path)

    # Load portfolio (triggers seeding)
    result = portfolio_mod.load_portfolio()
    df = pd.DataFrame(result)
    
    # Verify base seeding
    tickers = set(df["ticker"].str.upper()) if "ticker" in df else set()
    assert {"SYNAAA", "SYNBBB"}.issubset(tickers)
    assert result.cash >= 10_000.0

    # Verify historical data exists
    from data.db import get_connection
    with get_connection() as conn:
        history_count = conn.execute("SELECT COUNT(*) FROM portfolio_history").fetchone()[0]
        unique_dates = conn.execute("SELECT COUNT(DISTINCT date) FROM portfolio_history").fetchone()[0]
    
    # Should have historical data spanning multiple days
    assert history_count > 10  # At least positions + TOTAL rows for multiple days
    assert unique_dates >= 15  # At least 15 days of history
    
    tmpdir.cleanup()


def test_dev_stage_seeding(monkeypatch):
    """Ensure an empty DB in dev_stage seeds synthetic positions and cash."""
    monkeypatch.setenv("APP_ENV", "dev_stage")
    assert is_dev_stage()

    tmpdir = tempfile.TemporaryDirectory()
    db_path = Path(tmpdir.name) / "seed_test.db"
    monkeypatch.setattr("data.db.DB_FILE", db_path)

    result = portfolio_mod.load_portfolio()
    df = pd.DataFrame(result)
    tickers = set(df["ticker"].str.upper()) if "ticker" in df else set()
    assert {"SYNAAA", "SYNBBB"}.issubset(tickers)
    assert result.cash >= 10_000.0

    from data.db import get_connection
    with get_connection() as conn:
        rows = conn.execute("SELECT COUNT(*) FROM portfolio_history").fetchone()[0]
    assert rows > 0
    
    tmpdir.cleanup()
