"""Layered risk-free rate retrieval.

Order of precedence (daily cache):
1. FRED API (DGS3MO) if FRED_API_KEY present.
2. Environment variable RISK_FREE_ANNUAL (decimal, e.g. 0.04).
3. Fallback 0.0.

Result cached per UTC date in data/risk_free.json to avoid repeated network calls.
"""
from __future__ import annotations

from pathlib import Path
from datetime import datetime, UTC
import json
import os
import requests

from app_settings import settings

_CACHE_FILE = Path(settings.paths.data_dir) / "risk_free.json"
_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)


def _env_rate() -> float:
    val = os.getenv("RISK_FREE_ANNUAL")
    if not val:
        return 0.0
    try:
        return float(val)
    except ValueError:
        return 0.0


def get_risk_free_rate() -> float:
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    if _CACHE_FILE.exists():
        try:
            data = json.loads(_CACHE_FILE.read_text())
            if data.get("date") == today:
                return float(data.get("rate", 0.0))
        except Exception:
            pass

    fred_key = os.getenv("FRED_API_KEY")
    rate: float | None = None
    if fred_key:
        try:
            url = (
                "https://api.stlouisfed.org/fred/series/observations?series_id=DGS3MO&api_key="
                f"{fred_key}&file_type=json&sort_order=desc&limit=1"
            )
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            obs = r.json().get("observations", [])
            if obs:
                raw_val = obs[0].get("value")
                if raw_val not in (None, ".", ""):
                    rate = float(raw_val) / 100.0
        except Exception:
            rate = None
    if rate is None:
        rate = _env_rate()
    try:
        _CACHE_FILE.write_text(json.dumps({"date": today, "rate": rate}, indent=2))
    except Exception:
        pass
    return float(rate)
