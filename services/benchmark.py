"""Benchmark data retrieval & caching (Stooq daily CSV).

Downloads daily benchmark closes from Stooq (no API key) and caches under data/benchmarks.
Auto-refreshes at most once per day when accessed. Network failures are swallowed and the
last cached data (if any) is returned.
"""
from __future__ import annotations

from pathlib import Path
from datetime import datetime, UTC
import json
from typing import List

import requests

from app_settings import settings

BENCHMARK_SYMBOL_DEFAULT = "SPY"

_CACHE_DIR = Path(settings.paths.data_dir) / "benchmarks"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _cache_file(symbol: str) -> Path:
    return _CACHE_DIR / f"{symbol.upper()}.json"


def load_series(symbol: str) -> list[dict]:
    f = _cache_file(symbol)
    if f.exists():
        try:
            return json.loads(f.read_text())
        except Exception:
            return []
    return []


def save_series(symbol: str, rows: list[dict]) -> None:
    try:
        _cache_file(symbol).write_text(json.dumps(rows, indent=2))
    except Exception:
        pass


def fetch_stooq_daily(symbol: str) -> list[dict]:
    """Fetch full daily history for symbol from Stooq.

    Stooq symbol pattern for US ETFs/equities: lowercase + .us (e.g. spy.us).
    Returns list[{date: YYYY-MM-DD, close: float}] sorted by date.
    """
    url_sym = f"{symbol.lower()}.us"
    url = f"https://stooq.com/q/d/l/?s={url_sym}&i=d"
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    lines = r.text.strip().splitlines()
    if len(lines) <= 1:
        return []
    out: list[dict] = []
    for line in lines[1:]:
        parts = line.split(",")
        if len(parts) < 6:
            continue
        date, _o, _h, _l, close, _vol = parts
        if close in ("", "0"):
            continue
        out.append({"date": date, "close": float(close)})
    return sorted(out, key=lambda x: x["date"])


def update_benchmark(symbol: str) -> list[dict]:
    existing = load_series(symbol)
    have = {r["date"] for r in existing}
    try:
        fresh = fetch_stooq_daily(symbol)
    except Exception:
        return existing
    new_rows = [r for r in fresh if r["date"] not in have]
    if not existing and fresh:
        save_series(symbol, fresh)
        return fresh
    if new_rows:
        merged = sorted(existing + new_rows, key=lambda x: x["date"])
        save_series(symbol, merged)
        return merged
    return existing


def get_benchmark_series(symbol: str = BENCHMARK_SYMBOL_DEFAULT) -> list[dict]:
    """Return (and lazily refresh) benchmark close series.

    Refresh logic: If cache empty or last date < today, attempt update.
    """
    series = load_series(symbol)
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    if (not series) or (series[-1]["date"] < today):
        series = update_benchmark(symbol)
    return series


def latest_close(symbol: str = BENCHMARK_SYMBOL_DEFAULT) -> float | None:
    s = get_benchmark_series(symbol)
    return s[-1]["close"] if s else None
