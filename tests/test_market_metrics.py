import pandas as pd
import time
from unittest.mock import patch

from services.market import (
    fetch_prices_v2,
    get_metrics,
    reset_metrics,
    get_circuit_breaker_state,
)
from typer.testing import CliRunner
from cli.main import app as cli_app


def test_metrics_increment_and_reset(monkeypatch):
    reset_metrics()

    class DummyProv:
        def get_quote(self, t):
            if t == "BAD":
                raise RuntimeError("boom")
            return {"price": 10.0, "percent": 1.0}

    # Force micro path
    monkeypatch.setenv("DISABLE_MICRO_PROVIDERS", "0")
    monkeypatch.setenv("APP_ENABLE_MICRO_PROVIDERS", "1")

    with patch("services.market._get_micro_provider", return_value=DummyProv()):
        df = fetch_prices_v2(["GOOD", "BAD", "GOOD2"])  # one failure
        assert len(df) == 3

    m = get_metrics()
    assert m["price_fetch_bulk_success"] >= 2
    assert m["price_fetch_bulk_failure"] >= 1

    reset_metrics()
    m2 = get_metrics()
    assert m2["price_fetch_bulk_success"] == 0
    assert get_circuit_breaker_state()["state"] == "CLOSED"


def test_circuit_breaker_trips_and_recovers(monkeypatch):
    reset_metrics()
    from services.market import _micro_cb  # type: ignore
    # Force breaker open
    for _ in range(_micro_cb.failure_threshold):
        _micro_cb.record_failure()
    assert get_circuit_breaker_state()["state"] == "OPEN"
    # Directly simulate half-open trial and success without time dependency
    _micro_cb.state = "HALF_OPEN"
    _micro_cb.record_success()
    assert get_circuit_breaker_state()["state"] == "CLOSED"


def test_circuit_half_open_transition(monkeypatch):
    from services.market import _micro_cb
    # Force open state
    _micro_cb.state = "OPEN"
    _micro_cb.opened_at = time.time() - _micro_cb.reset_timeout - 0.1
    assert _micro_cb.allow()  # should transition to HALF_OPEN allowance
    assert _micro_cb.state == "HALF_OPEN"
    # Record success should fully close
    _micro_cb.record_success()
    assert _micro_cb.state == "CLOSED"


def test_retry_decorator(monkeypatch):
    from services.market import retry
    calls = {"n": 0}

    @retry(attempts=3, base_delay=0.01)
    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("boom")
        return 42

    assert flaky() == 42
    assert calls["n"] == 3  # retried twice then success


def test_fetch_prices_v2_circuit_open_fallback(monkeypatch):
    reset_metrics()
    # Force circuit open so micro provider path is skipped
    from services.market import _micro_cb  # type: ignore
    _micro_cb.state = "OPEN"
    _micro_cb.opened_at = time.time()  # recent so still open

    # Patch legacy fetch_prices to confirm fallback used
    import services.market as m
    def fake_fetch_prices(tickers):
        import pandas as pd
        return pd.DataFrame({"ticker": tickers, "current_price": [1.23]*len(tickers), "pct_change": [0.0]*len(tickers)})
    monkeypatch.setattr(m, "fetch_prices", fake_fetch_prices)

    df = m.fetch_prices_v2(["AAA","BBB"])  # should hit fallback
    assert list(df["current_price"]) == [1.23, 1.23]


def test_cli_metrics_command(monkeypatch):
    reset_metrics()
    runner = CliRunner()
    result = runner.invoke(cli_app, ["metrics"])  # should not raise
    assert result.exit_code == 0
    # Contains at least one known key
    assert "circuit_state" in result.stdout


def test_metrics_persistence(tmp_path, monkeypatch):
    # Point data dir to tmp for isolated persistence test
    from services import market as market_mod
    state_file = tmp_path / "metrics_state.json"
    circuit_file = tmp_path / "circuit_state.json"
    # Monkeypatch paths
    market_mod._METRICS_FILE = state_file  # type: ignore
    market_mod._CIRCUIT_STATE_FILE = circuit_file  # type: ignore
    market_mod._persist_metrics()
    reset_metrics()
    # Bump counters
    market_mod._metrics["price_fetch_bulk_success"] = 7
    market_mod._persist_metrics()
    # Zero then reload
    market_mod._metrics["price_fetch_bulk_success"] = 0
    market_mod._load_metrics()
    assert market_mod._metrics["price_fetch_bulk_success"] == 7
