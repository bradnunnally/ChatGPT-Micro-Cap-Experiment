def test_build_default_scheduler_jobs(monkeypatch):
    # Avoid network in benchmark update by monkeypatching update_benchmark
    monkeypatch.setattr("services.benchmark.update_benchmark", lambda symbol: [])
    # Avoid risk-free external calls
    monkeypatch.setattr("services.risk_free.get_risk_free_rate", lambda : 0.02)
    # Simplify fundamentals batch
    monkeypatch.setattr("services.fundamentals.batch_get_fundamentals", lambda tickers: {})
    from services import scheduler
    sched = scheduler.build_default_scheduler()
    state = {j['name'] for j in sched.jobs_state()}
    # Ensure new daily_price_rollup job registered
    assert 'daily_price_rollup' in state


def test_benchmark_latest_close(monkeypatch, tmp_path):
    # Patch load_series to return deterministic sample and prevent update path
    from services import benchmark
    monkeypatch.setattr(benchmark, "load_series", lambda symbol: [{"date": "2024-01-01", "close": 100.0}])
    monkeypatch.setattr(benchmark, "update_benchmark", lambda symbol: [{"date": "2024-01-01", "close": 100.0}])
    val = benchmark.latest_close("SPY")
    assert val == 100.0
