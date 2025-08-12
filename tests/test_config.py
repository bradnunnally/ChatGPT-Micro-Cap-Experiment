import pytest
from config import get_provider, resolve_environment


def test_env_default(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    assert resolve_environment() == "production"


def test_env_invalid(monkeypatch):
    monkeypatch.setenv("APP_ENV", "nope")
    with pytest.raises(ValueError):
        resolve_environment()


def test_provider_switch(monkeypatch):
    monkeypatch.setenv("APP_ENV", "dev_stage")
    assert get_provider().__class__.__name__ == "SyntheticDataProvider"
    monkeypatch.setenv("APP_ENV", "production")
    assert get_provider().__class__.__name__ == "YFinanceDataProvider"


def test_cli_override(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    # CLI override should take precedence and yield synthetic provider
    assert get_provider(cli_env="dev_stage").__class__.__name__ == "SyntheticDataProvider"
