import math
import time
from json import JSONDecodeError
import pandas as pd
import yfinance as yf
import streamlit as st
from functools import lru_cache
from typing import Optional, Any
try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
except Exception:  # pragma: no cover - optional resiliency
    requests = None
    HTTPAdapter = None
    Retry = None

from services.logging import log_error


@lru_cache(maxsize=1)
def _get_requests_session() -> Optional[Any]:
    """Create a requests.Session with retries and a friendly User-Agent.

    Returns None if requests/urllib3 isn't available.
    """
    if requests is None or HTTPAdapter is None or Retry is None:
        return None
    session = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=0.3,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "POST"),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 yfinance/0.2",
            "Accept": "*/*",
        }
    )
    return session


def _chart_url(ticker: str, range_: str = "5d", interval: str = "1d") -> str:
    return (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        f"?range={range_}&interval={interval}"
    )


def _fetch_chart_json(ticker: str, range_: str = "5d", interval: str = "1d") -> dict | None:
    url = _chart_url(ticker, range_, interval)
    sess = _get_requests_session()
    # First try via session if available
    if sess is not None:
        try:
            resp = sess.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return data if isinstance(data, dict) else None
        except Exception:
            pass
    # Fallback: direct requests.get with simple headers
    if requests is not None:
        try:
            resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return data if isinstance(data, dict) else None
        except Exception:
            pass
    return None


@st.cache_data(ttl=300)
def fetch_price(ticker: str) -> float | None:
    """Return the latest tradable price for ``ticker`` (live or last close)."""
    try:
        price = get_last_price(ticker)
        return float(price) if price is not None else None
    except Exception as e:  # pragma: no cover - network errors
        log_error(f"Failed to fetch price for {ticker}: {e}")
        return None


@st.cache_data(ttl=300)
def fetch_prices(tickers: list[str]) -> pd.DataFrame:
    """Return a 1-row DataFrame with Close prices for each ticker.

    Uses per-ticker robust fetching to avoid batch download failures.
    Data format: columns ['Close'][ticker] via MultiIndex for consistency with yfinance.
    """
    if not tickers:
        return pd.DataFrame()

    close_map: dict[str, float] = {}
    for t in tickers:
        try:
            price = get_last_price(t)
            if price is not None:
                close_map[t] = float(price)
        except Exception as e:
            log_error(f"Failed to fetch price for {t}: {e}")

    if not close_map:
        return pd.DataFrame()

    # Build a 1-row DataFrame compatible with previous code paths
    data = {("Close", k): [v] for k, v in close_map.items()}
    df = pd.DataFrame(data)
    df.columns = pd.MultiIndex.from_tuples(df.columns)
    return df


def get_day_high_low(ticker: str) -> tuple[float, float]:
    """Return today's high and low price for ``ticker``.

    Robust to transient yfinance/Yahoo issues by retrying and validating data.
    """

    def _download_history(symbol: str) -> pd.DataFrame | None:
        last_err: Exception | None = None
        # Retry a few times with short backoff
        for delay in (0.0, 0.25, 0.5, 1.0):
            if delay:
                time.sleep(delay)
            try:
                # Use Ticker().history which can be more reliable than download()
                sess = _get_requests_session()
                t = yf.Ticker(symbol, session=sess) if sess is not None else yf.Ticker(symbol)
                hist = t.history(
                    period="1d",
                    interval="1d",
                    actions=False,
                    auto_adjust=False,
                    prepost=True,
                )
                if isinstance(hist, pd.DataFrame) and not hist.empty:
                    return hist
            except (JSONDecodeError, ValueError) as e:
                last_err = e
                continue
            except Exception as e:  # pragma: no cover - network errors
                last_err = e
                continue
        if last_err:
            log_error(f"History fetch failed for {symbol}: {last_err}")
        return None

    # First try Yahoo chart API directly (works in this environment)
    chart = _fetch_chart_json(ticker, range_="5d", interval="1d")
    if chart and isinstance(chart.get("chart", {}), dict):
        try:
            result = chart["chart"]["result"][0]
            q = result["indicators"]["quote"][0]
            highs = q.get("high") or []
            lows = q.get("low") or []
            if highs and lows and highs[-1] is not None and lows[-1] is not None:
                h = float(highs[-1])
                l = float(lows[-1])
                if math.isfinite(h) and math.isfinite(l):
                    return h, l
        except Exception:
            pass

    # Fallback to yfinance history with retries
    data = _download_history(ticker)
    if data is None or data.empty:
        raise ValueError("No market data available.")
    high = data.get("High")
    low = data.get("Low")
    if high is None or low is None:
        raise ValueError("No market data available.")
    h = float(high.iloc[-1])
    l = float(low.iloc[-1])
    if not (math.isfinite(h) and math.isfinite(l)):
        raise ValueError("No market data available.")
    return h, l


def get_current_price(ticker: str) -> float:
    """Get current price for a ticker."""
    try:
        # Use explicit auto_adjust parameter
        sess = _get_requests_session()
        if sess is not None:
            # Prefer Ticker().history for consistency
            t = yf.Ticker(ticker, session=sess)
            data = t.history(period="1d", interval="1d", actions=False, auto_adjust=True, prepost=True)
        else:
            data = yf.download(
                ticker, 
                period="1d", 
                progress=False,
                auto_adjust=True
            )
        if data.empty:
            return None

        # Use recommended iloc syntax
        close_price = data["Close"].iloc[0]
        return float(close_price)

    except Exception as e:
        log_error(f"Error getting price for {ticker}: {e}")
        return None


def get_last_price(ticker: str) -> float | None:
    """Return the most recent close price for ticker, or None if unavailable.

    Tries fast_info.last_price first, then falls back to 5-day history close.
    """
    # Try direct chart API first
    chart = _fetch_chart_json(ticker, range_="5d", interval="1d")
    if chart and isinstance(chart.get("chart", {}), dict):
        try:
            result = chart["chart"]["result"][0]
            q = result["indicators"]["quote"][0]
            closes = q.get("close") or []
            if closes and closes[-1] is not None:
                val = float(closes[-1])
                if math.isfinite(val) and val > 0:
                    return val
        except Exception:
            pass

    # Fast path via yfinance fast_info
    try:
        sess = _get_requests_session()
        t = yf.Ticker(ticker, session=sess) if sess is not None else yf.Ticker(ticker)
        fi = t.fast_info
        last = getattr(fi, "last_price", None)
        if last is not None and math.isfinite(float(last)):
            return float(last)
    except Exception:
        pass

    # Fallback to recent history close
    try:
        sess = _get_requests_session()
        t = yf.Ticker(ticker, session=sess) if sess is not None else yf.Ticker(ticker)
        hist = t.history(
            period="5d", interval="1d", actions=False, auto_adjust=False, prepost=True
        )
        if isinstance(hist, pd.DataFrame) and not hist.empty:
            close = hist.get("Close")
            if close is not None:
                val = close.iloc[-1]
                if val is not None and math.isfinite(float(val)):
                    return float(val)
    except Exception:
        return None
    return None
