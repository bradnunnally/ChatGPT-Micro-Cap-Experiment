import json

from portfolio import (
    SCHEMA_VERSION,
    load_portfolio_state,
    save_portfolio_state,
    PORTFOLIO_STATE_FILE,
)


def test_portfolio_state_migration(tmp_path, monkeypatch):
    # Simulate legacy file without schema_version
    legacy = {"tickers": ["ABC", "XYZ"]}
    legacy_path = tmp_path / "portfolio.json"
    legacy_path.write_text(json.dumps(legacy))
    # Patch global path used by module to point to temp file
    monkeypatch.setattr("portfolio.PORTFOLIO_STATE_FILE", legacy_path)

    tickers = load_portfolio_state()
    assert tickers == ["ABC", "XYZ"]
    # After load, file should be upgraded when we save again
    save_portfolio_state(tickers)
    upgraded = json.loads(legacy_path.read_text())
    assert upgraded["schema_version"] == SCHEMA_VERSION
    assert upgraded["tickers"] == ["ABC", "XYZ"]


def test_portfolio_state_save_sets_version(tmp_path, monkeypatch):
    path = tmp_path / "portfolio.json"
    monkeypatch.setattr("portfolio.PORTFOLIO_STATE_FILE", path)
    save_portfolio_state(["ONE"])
    data = json.loads(path.read_text())
    assert data["schema_version"] == SCHEMA_VERSION
    assert data["tickers"] == ["ONE"]
