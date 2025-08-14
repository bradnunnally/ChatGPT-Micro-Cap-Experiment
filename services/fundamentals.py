"""Fundamentals retrieval (cash/share, book value/share, dividend yield) with daily cache.

Data Sources (best-effort):
1. Finnhub basic financials (if FINNHUB_API_KEY present)
2. Placeholder None values when key absent or errors occur

Caching: per-ticker JSON in data/cache/fundamentals/<TICKER>.json refreshed at most once per day.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import os
from datetime import datetime, timezone
from typing import Any, Optional, Dict

from app_settings import settings
from services.logging import get_logger

logger = get_logger(__name__)

_FUND_DIR = Path(settings.paths.data_dir) / "cache" / "fundamentals"
_FUND_DIR.mkdir(parents=True, exist_ok=True)


@dataclass(slots=True)
class Fundamentals:
    ticker: str
    cash_per_share: Optional[float]
    book_value_per_share: Optional[float]
    dividend_yield_pct: Optional[float]
    updated: str

    def as_dict(self) -> dict[str, Any]:  # pragma: no cover - trivial
        return {
            "ticker": self.ticker,
            "cash_per_share": self.cash_per_share,
            "book_value_per_share": self.book_value_per_share,
            "dividend_yield_pct": self.dividend_yield_pct,
            "updated": self.updated,
        }


def _cache_path(ticker: str) -> Path:
    return _FUND_DIR / f"{ticker.upper()}.json"


def _load_cache(ticker: str) -> Optional[Fundamentals]:
    path = _cache_path(ticker)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        if data.get("updated") == datetime.now(timezone.utc).strftime("%Y-%m-%d"):
            return Fundamentals(**data)
    except Exception:  # pragma: no cover
        return None
    return None


def _save_cache(f: Fundamentals) -> None:  # pragma: no cover - simple IO
    try:
        _cache_path(f.ticker).write_text(json.dumps(f.as_dict(), separators=(",", ":")))
    except Exception:
        pass


def _fetch_finnhub(ticker: str) -> Dict[str, Optional[float]]:
    api_key = os.getenv("FINNHUB_API_KEY")
    if not api_key:  # no network dependency in tests
        return {"cash": None, "book": None, "div_yield": None}
    try:  # pragma: no cover - network path
        import finnhub  # type: ignore
        client = finnhub.Client(api_key=api_key)
        basic = client.company_basic_financials(ticker, "all") or {}
        metric = basic.get("metric", {})
        cash = metric.get("cashPerShareTTM") or metric.get("cashPerShareAnnual")
        book = metric.get("bookValuePerShareAnnual") or metric.get("bookValuePerShareTTM")
        profile = client.company_profile2(symbol=ticker) or {}
        div_yield = profile.get("dividendYield") or metric.get("dividendYieldIndicatedAnnual")
        if isinstance(div_yield, (int, float)) and div_yield > 5:
            pass
        return {
            "cash": float(cash) if isinstance(cash, (int, float)) else None,
            "book": float(book) if isinstance(book, (int, float)) else None,
            "div_yield": float(div_yield) if isinstance(div_yield, (int, float)) else None,
        }
    except Exception as e:  # pragma: no cover - defensive
        logger.warning("fundamentals_fetch_failed", extra={"ticker": ticker, "error": str(e)})
        return {"cash": None, "book": None, "div_yield": None}


def get_fundamentals(ticker: str, force_refresh: bool = False) -> Fundamentals:
    ticker = ticker.upper()
    if not force_refresh:
        cached = _load_cache(ticker)
        if cached:
            return cached
    data = _fetch_finnhub(ticker)
    f = Fundamentals(
        ticker=ticker,
        cash_per_share=data["cash"],
        book_value_per_share=data["book"],
        dividend_yield_pct=data["div_yield"],
        updated=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    )
    _save_cache(f)
    return f


def batch_get_fundamentals(tickers: list[str]) -> list[Fundamentals]:
    out: list[Fundamentals] = []
    seen = set()
    for t in tickers:
        t = t.upper()
        if t in seen or t == "TOTAL":
            continue
        seen.add(t)
        out.append(get_fundamentals(t))
    return out
