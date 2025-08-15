from datetime import datetime, timedelta, timezone


def test_benchmark_load_series_invalid_json(monkeypatch, tmp_path):
    from services import benchmark
    cache_dir = tmp_path / "benchmarks"
    cache_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(benchmark, "_CACHE_DIR", cache_dir)
    bad_file = cache_dir / "BAD.json"
    bad_file.write_text("not-json")
    data = benchmark.load_series("BAD")
    assert data == []


def test_benchmark_save_series_exception(monkeypatch, tmp_path):
    from services import benchmark
    dir_path = tmp_path / "benchmarks"
    dir_path.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(benchmark, "_CACHE_DIR", dir_path)
    monkeypatch.setattr(benchmark, "_cache_file", lambda symbol: dir_path)  # force directory
    benchmark.save_series("SPY", [{"date": "2024-01-01", "close": 1.0}])  # should not raise


def test_get_benchmark_series_triggers_refresh(monkeypatch):
    from services import benchmark
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    stale = [{"date": yesterday, "close": 10.0}]
    updated = stale + [{"date": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "close": 11.0}]
    monkeypatch.setattr(benchmark, "load_series", lambda symbol: stale)
    monkeypatch.setattr(benchmark, "update_benchmark", lambda symbol: updated)
    series = benchmark.get_benchmark_series("SPY")
    assert series[-1]["close"] == 11.0


def test_latest_close_empty(monkeypatch):
    from services import benchmark
    monkeypatch.setattr(benchmark, "get_benchmark_series", lambda symbol: [])
    assert benchmark.latest_close("SPY") is None
