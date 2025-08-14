import os
from pathlib import Path
import pandas as pd
import pytest

import importlib


class DummyResp:
    def __init__(self, text=None, json_data=None, status=200):
        self._text = text
        self._json = json_data
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("http error")

    @property
    def text(self):
        return self._text

    def json(self):
        return self._json


@pytest.fixture(autouse=True)
def _isolate_tmp_cache(tmp_path, monkeypatch):
    monkeypatch.setattr("app_settings.settings.paths.data_dir", tmp_path, raising=False)
    (tmp_path / "benchmarks").mkdir(parents=True, exist_ok=True)
    # Reload modules after patch so they pick up new path
    for mod in [m for m in list(globals().keys()) if m.startswith("services.")]:
        pass
    import services.benchmark as benchmark
    import services.risk_free as risk_free
    import services.risk as risk_mod
    importlib.reload(benchmark)
    importlib.reload(risk_free)
    importlib.reload(risk_mod)
    return tmp_path


def test_benchmark_fetch_and_cache(monkeypatch, tmp_path):
    import services.benchmark as benchmark
    csv = "Date,Open,High,Low,Close,Volume\n2024-01-02,1,1,1,10,100\n2024-01-03,1,1,1,11,120\n"
    monkeypatch.setattr("requests.get", lambda url, timeout=15: DummyResp(text=csv))
    sym = "SPY"
    series = benchmark.update_benchmark(sym)
    assert len(series) >= 2
    cache_file = Path(benchmark._CACHE_DIR) / f"{sym}.json"  # type: ignore[attr-defined]
    assert cache_file.exists()
    series2 = benchmark.get_benchmark_series(sym)
    assert len(series2) == len(series)


def test_risk_free_env_fallback(monkeypatch, tmp_path):
    import services.risk_free as risk_free
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    monkeypatch.setenv("RISK_FREE_ANNUAL", "0.0375")
    # Force module to use isolated cache file
    rf_file = tmp_path / "risk_free_env.json"
    monkeypatch.setattr(risk_free, "_CACHE_FILE", rf_file, raising=False)
    if rf_file.exists():
        rf_file.unlink()
    rate = risk_free.get_risk_free_rate()
    assert abs(rate - 0.0375) < 1e-9
    # Second call hits cache path
    rate2 = risk_free.get_risk_free_rate()
    assert rate2 == rate


def test_risk_free_fred_path(monkeypatch, tmp_path):
    import services.risk_free as risk_free
    # Provide fake FRED key + mocked response
    monkeypatch.setenv("FRED_API_KEY", "XYZ")
    monkeypatch.delenv("RISK_FREE_ANNUAL", raising=False)

    fred_json = {
        "observations": [
            {"value": "5.10"}
        ]
    }
    monkeypatch.setattr("requests.get", lambda url, timeout=10: DummyResp(json_data=fred_json))
    # Clear & patch cache file
    rf_file = tmp_path / "risk_free_fred.json"
    monkeypatch.setattr(risk_free, "_CACHE_FILE", rf_file, raising=False)
    if rf_file.exists():
        rf_file.unlink()
    rate = risk_free.get_risk_free_rate()
    assert abs(rate - 0.051) < 1e-9


def test_compute_risk_block_with_benchmark(monkeypatch):
    # Minimal synthetic history TOTAL rows
    dates = pd.date_range("2024-01-01", periods=8, freq="D")
    history = pd.DataFrame({
        "date": dates.astype(str),
        "ticker": ["TOTAL"] * len(dates),
        "total_equity": [10000 + i * 50 for i in range(len(dates))],
        "total_value": [i * 50 for i in range(len(dates))],
    })
    bench_series = [{"date": d.strftime("%Y-%m-%d"), "close": 400 + i} for i, d in enumerate(dates)]
    monkeypatch.setattr("services.risk.get_benchmark_series", lambda symbol: bench_series)
    monkeypatch.setattr("services.risk.get_risk_free_rate", lambda: 0.0)
    from services.risk import compute_risk_block
    metrics = compute_risk_block(history, use_cache=False)
    # Beta should be computable and not None (approx positive) with linear series
    assert metrics.beta_like >= 0.0
    assert metrics.sortino_like >= 0.0
