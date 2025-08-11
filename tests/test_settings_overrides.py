from __future__ import annotations

import importlib
from pathlib import Path


def test_settings_env_overrides(tmp_path, monkeypatch):
    # Point data dir to a temp path via env
    tmp_data = tmp_path / "datax"
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_data))
    monkeypatch.setenv("APP_DB_FILE", "datax/custom.db")  # relative to base dir

    # Import app_settings freshly with env applied
    settings_mod = importlib.import_module("app_settings")
    importlib.reload(settings_mod)

    s = settings_mod.settings
    # Ensure paths are resolved correctly
    assert Path(s.paths.data_dir) == tmp_data
    assert str(s.paths.db_file).endswith("datax/custom.db")
