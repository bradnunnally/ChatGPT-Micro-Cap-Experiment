import pytest

from micro_config import resolve_env, get_provider


def test_env_selection_default_production(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    assert resolve_env() == "production"


def test_env_invalid(monkeypatch):
    monkeypatch.setenv("APP_ENV", "nope")
    with pytest.raises(ValueError):
        resolve_env()


def test_provider_dev_stage_without_key(monkeypatch):
    monkeypatch.setenv("APP_ENV", "dev_stage")
    p = get_provider()
    assert p.__class__.__name__.endswith("SyntheticDataProviderExt")


def test_provider_production_requires_key(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("FINNHUB_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        get_provider()
