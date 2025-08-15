"""Factor & benchmark expansion utilities.

Phase 7 Task 1.3: Support ingestion of multiple factor / style ETF daily closes
leveraging existing Stooq fetch used for benchmark. Stores under data/benchmarks
for now (schema-compatible JSON list[{date, close}]). Provides return series helpers.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List
import json
import pandas as pd

from app_settings import settings
from services.benchmark import fetch_stooq_daily, save_series, load_series

# Default factor symbols (can extend)
DEFAULT_FACTORS = ["SPY", "IWM", "MTUM", "VLUE", "QUAL"]

_FACTORS_DIR = Path(settings.paths.data_dir) / "benchmarks"  # reuse same dir
_FACTORS_DIR.mkdir(parents=True, exist_ok=True)

def ensure_factor(symbol: str) -> list[dict]:
    """Ensure factor symbol daily series cached (refresh if stale)."""
    return load_series(symbol) or fetch_and_cache_factor(symbol)

def fetch_and_cache_factor(symbol: str) -> list[dict]:
    try:
        rows = fetch_stooq_daily(symbol)
    except Exception:
        return []
    if rows:
        save_series(symbol, rows)
    return rows

def get_factor_closes(symbols: List[str] | None = None) -> Dict[str, pd.Series]:
    symbols = symbols or DEFAULT_FACTORS
    out: Dict[str, pd.Series] = {}
    for sym in symbols:
        series = ensure_factor(sym)
        if not series:
            continue
        df = pd.DataFrame(series)
        s = pd.to_numeric(df["close"], errors="coerce")
        s.index = pd.to_datetime(df["date"])
        out[sym] = s.sort_index()
    return out

def get_factor_returns(symbols: List[str] | None = None) -> Dict[str, pd.Series]:
    closes = get_factor_closes(symbols)
    return {k: v.pct_change().dropna() for k, v in closes.items() if not v.empty}

def factors_summary(symbols: List[str] | None = None) -> dict:
    rets = get_factor_returns(symbols)
    out = {}
    for k, s in rets.items():
        if s.empty:
            continue
        out[k] = {
            "points": int(s.shape[0]),
            "start": s.index.min().strftime("%Y-%m-%d"),
            "end": s.index.max().strftime("%Y-%m-%d"),
            "mean_daily": float(s.mean()),
            "vol_daily": float(s.std()),
        }
    return out

__all__ = [
    "DEFAULT_FACTORS",
    "get_factor_closes",
    "get_factor_returns",
    "factors_summary",
    "fetch_and_cache_factor",
] 
