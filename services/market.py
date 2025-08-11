import math
import time
from json import JSONDecodeError
import pandas as pd
import yfinance as yf
import streamlit as st

from services.logging import log_error


@st.cache_data(ttl=300)
def fetch_price(ticker: str) -> float | None:
    """Return the latest close price for ``ticker`` or ``None`` on failure."""

    try:  # pragma: no cover - network errors
        data = yf.download(ticker, period="1d", progress=False)
        return float(data["Close"].iloc[-1]) if not data.empty else None
    except Exception:
        log_error(f"Failed to fetch price for {ticker}")
        return None


@st.cache_data(ttl=300)
def fetch_prices(tickers: list[str]) -> pd.DataFrame:
    """Return daily data for ``tickers`` in a single request."""

    if not tickers:
        return pd.DataFrame()

    try:  # pragma: no cover - network errors
        return yf.download(tickers, period="1d", progress=False)
    except Exception:
        log_error(f"Failed to fetch prices for {', '.join(tickers)}")
        return pd.DataFrame()


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
                hist = yf.Ticker(symbol).history(
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
    # Fast path via fast_info
    try:
        fi = yf.Ticker(ticker).fast_info
        last = getattr(fi, "last_price", None)
        if last is not None and math.isfinite(float(last)):
            return float(last)
    except Exception:
        # Fall through to history
        pass

    # Fallback to recent history close
    try:
        hist = yf.Ticker(ticker).history(
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
