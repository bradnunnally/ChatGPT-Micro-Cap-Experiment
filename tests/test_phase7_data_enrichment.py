import json
from datetime import datetime, timezone


def test_benchmark_update_merge(monkeypatch, tmp_path):
    from services import benchmark
    cache_dir = tmp_path / "benchmarks"
    cache_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(benchmark, "_CACHE_DIR", cache_dir)
    existing = [
        {"date": "2024-01-01", "close": 100.0},
        {"date": "2024-01-02", "close": 101.0},
    ]
    (cache_dir / "SPY.json").write_text(json.dumps(existing))
    fresh = existing + [{"date": "2024-01-03", "close": 102.0}]
    monkeypatch.setattr(benchmark, "fetch_stooq_daily", lambda symbol: fresh)
    merged = benchmark.update_benchmark("SPY")
    assert len(merged) == 3 and merged[-1]["close"] == 102.0


def test_get_benchmark_series_refresh(monkeypatch):
    from services import benchmark
    monkeypatch.setattr(benchmark, "load_series", lambda symbol: [])
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    dataset = [{"date": today, "close": 200.0}]
    monkeypatch.setattr(benchmark, "update_benchmark", lambda symbol: dataset)
    series = benchmark.get_benchmark_series("SPY")
    assert series and series[-1]["close"] == 200.0


def test_factors_fetch_and_cache(monkeypatch, tmp_path):
    from services import factors
    from services import benchmark  # reuse save_series impl
    cache_dir = tmp_path / "benchmarks"
    cache_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(benchmark, "_CACHE_DIR", cache_dir)
    sample = [
        {"date": "2024-01-01", "close": 50.0},
        {"date": "2024-01-02", "close": 55.0},
    ]
    monkeypatch.setattr(factors, "fetch_stooq_daily", lambda symbol: sample)
    rows = factors.fetch_and_cache_factor("QUAL")
    assert rows and (cache_dir / "QUAL.json").exists()
    closes = factors.get_factor_closes(["QUAL"])  # should load from cache
    assert "QUAL" in closes and closes["QUAL"].iloc[-1] == 55.0


def test_scheduler_run_all_jobs(monkeypatch):
    monkeypatch.setattr("services.benchmark.update_benchmark", lambda symbol: [])
    monkeypatch.setattr("services.risk_free.get_risk_free_rate", lambda : 0.025)
    monkeypatch.setattr("services.fundamentals.batch_get_fundamentals", lambda tickers: {})
    monkeypatch.setattr("strategies.grid.run_sma_grid", lambda series, fast_values, slow_values: {})
    import pandas as pd
    monkeypatch.setattr("strategies.grid.summarize_results", lambda results: pd.DataFrame())
    monkeypatch.setattr("services.alerts.evaluate_alerts", lambda df: None)
    monkeypatch.setattr("services.market.rollup_daily_prices", lambda : 0)
    monkeypatch.setattr("data.portfolio.load_portfolio", lambda : (pd.DataFrame({"shares": []}), 0.0, []))
    from services import scheduler
    sched = scheduler.build_default_scheduler()
    executed = sched.run_pending()
    assert executed >= 7
