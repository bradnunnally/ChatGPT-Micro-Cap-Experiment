"""Configuration package initializer.

This package coexists with a legacy top-level ``config.py`` module that defines
constants used widely across the codebase and tests (for example, ``COL_TICKER``,
``TODAY``, etc.). To preserve backward compatibility with imports like
``from config import COL_TICKER`` while also supporting ``from config.settings import settings``,
we dynamically load the top-level ``config.py`` and re-export its public names here.
"""

from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType
from typing import List

# Attempt to locate the top-level legacy_config.py beside the repository root.
_root = Path(__file__).resolve().parent.parent
_legacy_path = _root / "legacy_config.py"

__all__: List[str] = []
if _legacy_path.exists():
    _spec = spec_from_file_location("_legacy_config", _legacy_path)
    if _spec and _spec.loader:  # pragma: no branch
        _legacy: ModuleType = module_from_spec(_spec)
        _spec.loader.exec_module(_legacy)  # type: ignore[arg-type]
        legacy_public = [n for n in dir(_legacy) if not n.startswith("_")]
        globals().update({n: getattr(_legacy, n) for n in legacy_public})
        __all__.extend(legacy_public)

from .settings import settings  # re-export user settings
from . import providers as _providers

AppConfig = _providers.AppConfig
resolve_environment = _providers.resolve_environment
get_provider = _providers.get_provider
bootstrap_defaults = _providers.bootstrap_defaults
is_dev_stage = _providers.is_dev_stage

__all__.extend([
    "settings",
    "AppConfig",
    "resolve_environment",
    "get_provider",
    "bootstrap_defaults",
    "is_dev_stage",
])

# Keep settings submodule available via `from config.settings import settings`.
# No explicit import here to avoid import-time side effects; normal submodule
# import resolution will find `config/settings.py` when referenced.
