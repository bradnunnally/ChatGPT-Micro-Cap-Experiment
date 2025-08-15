import os

def test_quote_archive_and_rollup(monkeypatch, tmp_path):
    # Point APP_DB_FILE env so Settings resolves new db path
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("APP_DB_FILE", str(db_path))
    # Reload settings module to pick up override
    import importlib, app_settings
    importlib.reload(app_settings)
    from app_settings import settings
    # Initialize DB schema
    from data import db as dbmod
    dbmod.DB_FILE = settings.paths.db_file
    dbmod.init_db()
    import services.market as market

    # Archive a few quotes
    market._archive_quote("SPY", 100.0)
    market._archive_quote("SPY", 101.0)
    market._archive_quote("SPY", 99.5)

    count = market.rollup_daily_prices()
    assert count >= 1
    df = market.get_daily_price_series("SPY")
    assert not df.empty
    row = df.iloc[-1]
    assert row["high"] >= row["low"]
    assert row["open"] >= 0 and row["close"] >= 0


def test_factors_summary(monkeypatch, tmp_path):
    # Simulate factor JSON cache files with minimal data to avoid network
    import services.factors as factors
    import json
    from app_settings import settings
    # Create fake series for two factors
    data_dir = settings.paths.data_dir / "benchmarks"
    data_dir.mkdir(parents=True, exist_ok=True)
    sample = [{"date": "2024-01-01", "close": 100.0}, {"date": "2024-01-02", "close": 101.0}]
    (data_dir / "SPY.json").write_text(json.dumps(sample))
    (data_dir / "IWM.json").write_text(json.dumps(sample))
    summary = factors.factors_summary(["SPY", "IWM"])  # limit to avoid network
    assert "SPY" in summary and summary["SPY"]["points"] == 1  # returns have 1 point
    assert summary["SPY"]["mean_daily"] != 0


def test_daily_price_fallback_without_rollup(monkeypatch, tmp_path):
    # Fresh DB with only one quote, no rollup yet -> fallback path
    db_path = tmp_path / "fallback.db"
    monkeypatch.setenv("APP_DB_FILE", str(db_path))
    import importlib, app_settings
    importlib.reload(app_settings)
    from app_settings import settings
    from data import db as dbmod
    dbmod.DB_FILE = settings.paths.db_file
    dbmod.init_db()
    import services.market as market
    market._archive_quote("IWM", 55.0)
    df = market.get_daily_price_series("IWM")
    assert len(df) == 1
    r = df.iloc[0]
    assert r["open"] == r["close"] == 55.0


def test_rollup_empty_date(monkeypatch, tmp_path):
    # Calling rollup on a date with no quotes should return 0 and not error
    db_path = tmp_path / "empty.db"
    monkeypatch.setenv("APP_DB_FILE", str(db_path))
    import importlib, app_settings
    importlib.reload(app_settings)
    from app_settings import settings
    from data import db as dbmod
    dbmod.DB_FILE = settings.paths.db_file
    dbmod.init_db()
    import services.market as market
    cnt = market.rollup_daily_prices(for_date="1999-01-01")
    assert cnt == 0


def test_factor_returns_functions(monkeypatch, tmp_path):
    # Cover get_factor_closes/get_factor_returns with cached data
    import services.factors as factors
    from app_settings import settings
    import json
    data_dir = settings.paths.data_dir / "benchmarks"
    data_dir.mkdir(parents=True, exist_ok=True)
    sample = [
        {"date": "2024-01-01", "close": 100.0},
        {"date": "2024-01-02", "close": 102.0},
        {"date": "2024-01-03", "close": 101.0},
    ]
    (data_dir / "QUAL.json").write_text(json.dumps(sample))
    closes = factors.get_factor_closes(["QUAL"])  # should not fetch network
    assert "QUAL" in closes and not closes["QUAL"].empty
    returns = factors.get_factor_returns(["QUAL"])  # one shorter series
    assert returns["QUAL"].shape[0] == 2
