from __future__ import annotations

"""Extended data providers for a minimal CLI app.

This module is additive and does not modify existing providers. It includes:
- Protocol MarketDataProvider with richer methods used by the CLI app
- SyntheticDataProviderExt: deterministic offline data
- FinnhubDataProvider: real data with small on-disk cache and rate-limit handling

Network calls are contained only within FinnhubDataProvider.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol, Tuple, Optional, List, Dict, Any
import time
import json
import math
import random

import pandas as pd
import numpy as np
import logging

logger = logging.getLogger("micro.providers.finnhub")


class MarketDataProvider(Protocol):
    """Protocol for market data operations required by the CLI app."""

    def get_quote(self, ticker: str) -> dict: ...

    def get_daily_candles(self, ticker: str, start: date, end: date) -> pd.DataFrame: ...

    def get_company_profile(self, ticker: str) -> dict: ...

    def get_bid_ask(self, ticker: str) -> Tuple[Optional[float], Optional[float]]: ...

    def get_company_news(self, ticker: str, start: date, end: date) -> List[dict]: ...

    def get_earnings_calendar(self, ticker: str, start: date, end: date) -> List[dict]: ...


# ----------------------------- Synthetic Provider ---------------------------------------


@dataclass(slots=True)
class SyntheticDataProviderExt:
    """Deterministic synthetic provider for dev_stage.

    Generates plausible price paths and metadata with no network calls.
    """

    seed: int = 42
    calendar: str = "B"

    def _rng(self, ticker: str) -> np.random.Generator:
        derived = abs(hash((self.seed, ticker))) % (2**32 - 1)
        return np.random.default_rng(derived)

    def get_daily_candles(self, ticker: str, start: date, end: date) -> pd.DataFrame:
        dates = pd.bdate_range(start=start, end=end, freq=self.calendar)
        if len(dates) == 0:
            return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])  # pragma: no cover
        rng = self._rng(ticker)
        n = len(dates)
        drift = 0.0005
        vol = 0.02
        rets = rng.normal(drift, vol, size=n)
        start_price = rng.uniform(4, 30)
        close_prices = start_price * (1 + rets).cumprod()
        open_prices = np.empty_like(close_prices)
        open_prices[0] = close_prices[0] * (1 + rng.normal(0, 0.003))
        open_prices[1:] = close_prices[:-1] * (1 + rng.normal(0, 0.003, size=n - 1))
        spread = np.abs(rng.normal(0.01, 0.004, size=n))
        highs = np.maximum(open_prices, close_prices) * (1 + spread)
        lows = np.minimum(open_prices, close_prices) * (1 - spread)
        volumes = rng.integers(25_000, 500_000, size=n)
        df = pd.DataFrame(
            {
                "date": pd.to_datetime(dates, utc=True),
                "open": open_prices,
                "high": highs,
                "low": lows,
                "close": close_prices,
                "volume": volumes,
            }
        )
        return df

    def get_quote(self, ticker: str) -> dict:
        end = pd.Timestamp.utcnow().date()
        start = end - pd.Timedelta(days=5)
        df = self.get_daily_candles(ticker, start=start, end=end)
        if df.empty:
            return {"price": None, "change": None, "percent": None}
        last = float(df["close"].iloc[-1])
        prev = float(df["close"].iloc[-2]) if len(df) > 1 else last
        change = last - prev
        percent = (change / prev * 100.0) if prev else 0.0
        return {"price": round(last, 4), "change": round(change, 4), "percent": round(percent, 4)}

    def get_company_profile(self, ticker: str) -> dict:
        rng = self._rng(ticker)
        sectors = ["Technology", "Healthcare", "Financials", "Energy", "Consumer"]
        exchanges = ["NASDAQ", "NYSE", "AMEX"]
        market_cap = float(rng.uniform(10_000_000, 400_000_000))
        return {
            "ticker": ticker.upper(),
            "exchange": str(rng.choice(exchanges)),
            "sector": str(rng.choice(sectors)),
            "marketCap": round(market_cap, 2),
        }

    def get_bid_ask(self, ticker: str) -> Tuple[Optional[float], Optional[float]]:
        q = self.get_quote(ticker)
        price = q.get("price")
        if not price:
            return (None, None)
        rng = self._rng(ticker)
        spread_bps = abs(rng.normal(50, 20)) / 10_000  # 5-10 bps typical
        bid = float(price) * (1 - spread_bps / 2)
        ask = float(price) * (1 + spread_bps / 2)
        return (round(bid, 4), round(ask, 4))

    def get_company_news(self, ticker: str, start: date, end: date) -> List[dict]:
        # Provide 1-2 deterministic headlines
        rng = self._rng(ticker)
        count = int(rng.integers(1, 3))
        base_dt = datetime.combine(end, datetime.min.time(), tzinfo=timezone.utc)
        items = []
        for i in range(count):
            ts = base_dt - timedelta(days=i)
            items.append({
                "headline": f"{ticker.upper()} synthetic event #{i+1}",
                "datetime": int(ts.timestamp()),
                "source": "SYNTH",
                "url": "",
            })
        return items

    def get_earnings_calendar(self, ticker: str, start: date, end: date) -> List[dict]:
        # Next earnings about 30-90 days out from start
        rng = self._rng(ticker)
        next_days = int(rng.integers(30, 90))
        dt = datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc) + timedelta(days=next_days)
        return [{"symbol": ticker.upper(), "date": dt.date().isoformat()}]


# ----------------------------- Finnhub Provider -----------------------------------------


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _is_fresh(path: Path, ttl_s: int) -> bool:
    try:
        if not path.exists():
            return False
        age = time.time() - path.stat().st_mtime
        return age <= ttl_s
    except Exception:
        return False


def _read_json(path: Path) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _write_json(path: Path, data: Any) -> None:
    try:
        _ensure_dir(path.parent)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, separators=(",", ":"))
        tmp.replace(path)
    except Exception:
        pass


def _to_utc(ts: int | float | None) -> Optional[pd.Timestamp]:
    if ts is None:
        return None
    try:
        return pd.to_datetime(int(ts), unit="s", utc=True)
    except Exception:
        return None


@dataclass(slots=True)
class FinnhubDataProvider:
    """Finnhub-backed provider with small file cache and basic retry/backoff."""

    api_key: str
    cache_dir: str | Path = "data/cache"
    quote_ttl_s: int = 30
    candles_ttl_s: int = 3600
    profile_ttl_s: int = 86400
    misc_ttl_s: int = 86400  # news, earnings, bidask

    # Internal cached finnhub client (lazily created). Declared as field because of slots.
    _client: Any | None = field(init=False, default=None, repr=False)
    _capabilities: Dict[str, bool] | None = field(init=False, default=None, repr=False)

    def __post_init__(self) -> None:
        self.cache_dir = Path(self.cache_dir)
        _ensure_dir(self.cache_dir)
        # _client left as None for lazy creation

    # ------------------------ client and backoff helpers ----------------------
    def _client_get(self):
        if self._client is None:
            import finnhub  # type: ignore
            self._client = finnhub.Client(api_key=self.api_key)
        return self._client

    def _call(self, func, *args, attempts: int = 3, base_delay: float = 0.5, **kwargs):
        """Call finnhub SDK function with retry on HTTP 429 and transient errors."""
        last_err: Optional[Exception] = None
        for i in range(attempts):
            try:
                return func(*args, **kwargs)
            except Exception as e:  # Inspect for 429 if available
                msg = str(e)
                last_err = e
                # crude 429 detection across SDK/requests variations
                is_429 = "429" in msg or "Too Many Requests" in msg
                is_403 = "403" in msg or "access" in msg.lower()
                # Do not retry permission errors (403)
                if is_403:
                    break
                if not is_429 and i == attempts - 1:
                    break
                # backoff with jitter
                delay = base_delay * (2 ** i) * (1 + random.uniform(-0.2, 0.2))
                print(f"[finnhub] rate limited, retrying in {delay:.2f}s...")
                time.sleep(max(0.1, delay))
        if last_err:
            raise last_err
        raise RuntimeError("Finnhub call failed")

    # ------------------------------ cache keys --------------------------------
    def _quote_path(self, ticker: str) -> Path:
        return self.cache_dir / f"quote_{ticker.upper()}.json"

    def _candles_path(self, ticker: str, start: date, end: date) -> Path:
        return self.cache_dir / f"candles_{ticker.upper()}_{start.isoformat()}_{end.isoformat()}.json"

    def _profile_path(self, ticker: str) -> Path:
        return self.cache_dir / f"profile_{ticker.upper()}.json"

    def _bidask_path(self, ticker: str) -> Path:
        return self.cache_dir / f"bidask_{ticker.upper()}.json"

    def _news_path(self, ticker: str, start: date, end: date) -> Path:
        return self.cache_dir / f"news_{ticker.upper()}_{start.isoformat()}_{end.isoformat()}.json"

    def _earnings_path(self, ticker: str, start: date, end: date) -> Path:
        return self.cache_dir / f"earnings_{ticker.upper()}_{start.isoformat()}_{end.isoformat()}.json"

    # ------------------------------ API methods --------------------------------
    def get_quote(self, ticker: str) -> dict:
        path = self._quote_path(ticker)
        if _is_fresh(path, self.quote_ttl_s):
            data = _read_json(path) or {}
            logger.debug("cache_hit quote %s", ticker)
            return data
        logger.debug("cache_miss quote %s", ticker)
        client = self._client_get()
        data = self._call(client.quote, ticker)
        # Finnhub quote fields: c (current), pc (prev close)
        price = data.get("c")
        prev = data.get("pc") or 0
        change = (price - prev) if (price is not None and prev) else None
        percent = (change / prev * 100.0) if (change is not None and prev) else None
        mapped = {"price": price, "change": change, "percent": percent}
        _write_json(path, mapped)
        return mapped

    def get_daily_candles(self, ticker: str, start: date, end: date) -> pd.DataFrame:
        path = self._candles_path(ticker, start, end)
        if _is_fresh(path, self.candles_ttl_s):
            data = _read_json(path)
            if isinstance(data, dict) and data.get("t"):
                logger.debug("cache_hit candles %s %s %s", ticker, start, end)
                return self._candles_to_df(data)
        logger.debug("cache_miss candles %s %s %s", ticker, start, end)
        client = self._client_get()
        fr = int(datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc).timestamp())
        to = int(datetime.combine(end, datetime.min.time(), tzinfo=timezone.utc).timestamp()) + 24 * 3600
        res = self._call(client.stock_candles, ticker, "D", fr, to)
        if res and res.get("s") == "ok":
            _write_json(path, res)
            return self._candles_to_df(res)
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])  # pragma: no cover

    def _candles_to_df(self, res: dict) -> pd.DataFrame:
        ts = res.get("t") or []
        opens = res.get("o") or []
        highs = res.get("h") or []
        lows = res.get("l") or []
        closes = res.get("c") or []
        vols = res.get("v") or []
        if not ts:
            return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])  # pragma: no cover
        dt = pd.to_datetime(pd.Series(ts, dtype="int64"), unit="s", utc=True)
        df = pd.DataFrame(
            {
                "date": dt,
                "open": opens,
                "high": highs,
                "low": lows,
                "close": closes,
                "volume": vols,
            }
        )
        return df

    def get_company_profile(self, ticker: str) -> dict:
        path = self._profile_path(ticker)
        if _is_fresh(path, self.profile_ttl_s):
            data = _read_json(path)
            if isinstance(data, dict):
                logger.debug("cache_hit profile %s", ticker)
                return data
        logger.debug("cache_miss profile %s", ticker)
        client = self._client_get()
        profile = self._call(client.company_profile2, symbol=ticker) or {}
        basic = self._call(client.company_basic_financials, ticker, "all") or {}
        sector = profile.get("finnhubIndustry") or profile.get("sector")
        mc = None
        try:
            metrics = (basic or {}).get("metric") or {}
            mc = metrics.get("marketCapitalization") or metrics.get("marketCap")
        except Exception:
            pass
        mapped = {
            "ticker": ticker.upper(),
            "exchange": profile.get("exchange") or profile.get("mic") or profile.get("country"),
            "sector": sector,
            "marketCap": mc,
        }
        _write_json(path, mapped)
        return mapped

    def get_bid_ask(self, ticker: str) -> Tuple[Optional[float], Optional[float]]:
        path = self._bidask_path(ticker)
        if _is_fresh(path, self.misc_ttl_s):
            data = _read_json(path) or {}
            bid = data.get("bid")
            ask = data.get("ask")
            logger.debug("cache_hit bidask %s", ticker)
            return (bid, ask)
        logger.debug("cache_miss bidask %s", ticker)
        client = self._client_get()
        bid = ask = None
        # Finnhub SDK may not expose bid/ask everywhere; fallback to HTTP endpoint
        try:
            data = self._call(client.last_bid_ask, ticker)  # type: ignore[attr-defined]
            bid = data.get("bid")
            ask = data.get("ask")
        except Exception:
            # Fallback to REST
            import requests

            url = "https://finnhub.io/api/v1/stock/bidask"
            params = {"symbol": ticker, "token": self.api_key}
            try:
                r = requests.get(url, params=params, timeout=10)
                if r.status_code == 429:
                    raise RuntimeError("429 Too Many Requests")
                r.raise_for_status()
                j = r.json()
                bid = j.get("bid")
                ask = j.get("ask")
            except Exception as e:
                # Basic backoff on 429
                if "429" in str(e):
                    time.sleep(0.5)
                bid = ask = None
        _write_json(path, {"bid": bid, "ask": ask})
        return (bid, ask)

    def get_company_news(self, ticker: str, start: date, end: date) -> List[dict]:
        path = self._news_path(ticker, start, end)
        if _is_fresh(path, self.misc_ttl_s):
            data = _read_json(path)
            if isinstance(data, list):
                logger.debug("cache_hit news %s %s %s", ticker, start, end)
                return data
        logger.debug("cache_miss news %s %s %s", ticker, start, end)
        client = self._client_get()
        s = start.isoformat()
        e = end.isoformat()
        news = self._call(client.company_news, ticker, _from=s, to=e) or []
        _write_json(path, news)
        return news

    def get_earnings_calendar(self, ticker: str, start: date, end: date) -> List[dict]:
        path = self._earnings_path(ticker, start, end)
        if _is_fresh(path, self.misc_ttl_s):
            data = _read_json(path)
            if isinstance(data, list):
                logger.debug("cache_hit earnings %s %s %s", ticker, start, end)
                return data
        logger.debug("cache_miss earnings %s %s %s", ticker, start, end)
        client = self._client_get()
        cal = self._call(client.earnings_calendar, _from=start.isoformat(), to=end.isoformat(), symbol=ticker)
        items = (cal or {}).get("earningsCalendar") or []
        _write_json(path, items)
        return items

    # ------------------------------ capabilities --------------------------------
    def get_capabilities(self, probe_symbol: str = "AAPL") -> Dict[str, bool]:
        """Detect which endpoints appear accessible for this API key.

        Results are cached for the instance lifetime to avoid repeated calls.
        """
        if self._capabilities is not None:
            return self._capabilities
        caps = {k: False for k in ["quote", "profile", "candles", "bidask", "news", "earnings"]}
        try:
            q = self.get_quote(probe_symbol)
            caps["quote"] = bool(q and q.get("price") is not None)
        except Exception:
            pass
        try:
            p = self.get_company_profile(probe_symbol)
            caps["profile"] = bool(p and p.get("exchange"))
        except Exception:
            pass
        try:
            today = date.today()
            candles = self.get_daily_candles(probe_symbol, today - timedelta(days=5), today)
            caps["candles"] = not candles.empty
        except Exception:
            pass
        try:
            ba = self.get_bid_ask(probe_symbol)
            caps["bidask"] = any(ba)
        except Exception:
            pass
        try:
            today = date.today()
            news = self.get_company_news(probe_symbol, today - timedelta(days=3), today)
            caps["news"] = isinstance(news, list) and len(news) > 0
        except Exception:
            pass
        try:
            today = date.today()
            earn = self.get_earnings_calendar(probe_symbol, today - timedelta(days=30), today + timedelta(days=60))
            caps["earnings"] = isinstance(earn, list)
        except Exception:
            pass
        self._capabilities = caps
        return caps


__all__ = [
    "MarketDataProvider",
    "SyntheticDataProviderExt",
    "FinnhubDataProvider",
]
