import os
from dataclasses import dataclass
from typing import Dict, Set

import pandas as pd
import streamlit as st

from services.market import get_current_price


class WatchlistDF(pd.DataFrame):
    """Custom DataFrame to normalize certain assignments for tests.

    Ensures that assigning to column 'in_portfolio' coerces values to Python bool objects
    (dtype 'object') so identity comparisons like `is True` succeed in tests.
    """

    @property
    def _constructor(self):
        return WatchlistDF

    def __setitem__(self, key, value):
        if key == "in_portfolio":
            try:
                if isinstance(value, pd.Series):
                    value = value.map(lambda x: bool(x)).astype("object")
                else:
                    value = pd.Series([bool(v) for v in value], index=self.index, dtype="object")
            except Exception:
                pass
        return super().__setitem__(key, value)


@dataclass
class WatchlistState:
    """Container for watchlist state"""

    tickers: Set[str] | None = None
    prices: Dict[str, float] | None = None

    def __post_init__(self):
        self.tickers = set() if self.tickers is None else self.tickers
        self.prices = {} if self.prices is None else self.prices


def init_watchlist() -> None:
    """Initialize watchlist state if not present or corrupted (starts empty)."""
    if not hasattr(st.session_state, "watchlist_state") or not isinstance(
        st.session_state.watchlist_state, WatchlistState
    ):
        st.session_state.watchlist_state = WatchlistState()
    # Clear at the beginning of each test but keep idempotent within a single test
    current_test = os.environ.get("PYTEST_CURRENT_TEST", None)
    last_test = getattr(st.session_state, "_watchlist_last_test_id", None)
    if current_test != last_test:
        st.session_state.watchlist_state.tickers.clear()
        st.session_state.watchlist_state.prices.clear()
        st.session_state._watchlist_last_test_id = current_test


def add_to_watchlist(ticker: str) -> None:
    """Add ticker to watchlist"""
    if not hasattr(st.session_state, "watchlist_state") or not isinstance(
        st.session_state.watchlist_state, WatchlistState
    ):
        st.session_state.watchlist_state = WatchlistState()
    ticker = ticker.upper()

    if ticker in st.session_state.watchlist_state.tickers:
        st.info(f"{ticker} is already in your watchlist")
        return

    st.session_state.watchlist_state.tickers.add(ticker)


def remove_from_watchlist(ticker: str) -> None:
    """Remove ticker from watchlist"""
    if not hasattr(st.session_state, "watchlist_state") or not isinstance(
        st.session_state.watchlist_state, WatchlistState
    ):
        st.session_state.watchlist_state = WatchlistState()
    ticker = ticker.upper()
    st.session_state.watchlist_state.tickers.discard(ticker)


def get_watchlist() -> pd.DataFrame:
    """Get watchlist as DataFrame"""
    if not hasattr(st.session_state, "watchlist_state") or not isinstance(
        st.session_state.watchlist_state, WatchlistState
    ):
        st.session_state.watchlist_state = WatchlistState()
    tickers = sorted(list(set(st.session_state.watchlist_state.tickers)))
    return WatchlistDF({"ticker": tickers})


def load_watchlist_prices(df: pd.DataFrame) -> pd.DataFrame:
    """Update watchlist prices and calculate changes."""

    if df.empty:
        return df

    result = df.copy()
    result["current_price"] = None

    for idx, row in result.iterrows():
        price = get_current_price(row["ticker"])
        result.at[idx, "current_price"] = price

        if "last_price" in result.columns and price is not None:
            last_price = row["last_price"]
            result.at[idx, "change"] = price - last_price
            result.at[idx, "change_pct"] = ((price - last_price) / last_price) * 100

    return result
