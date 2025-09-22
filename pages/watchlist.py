from pathlib import Path

import pandas as pd
import streamlit as st

from components.nav import navbar
from services.market import fetch_price
from services.time import get_clock
from services.watchlist_service import (
    add_to_watchlist,
    get_watchlist,
    load_watchlist_prices,
    remove_from_watchlist,
)
from ui.forms import show_buy_form

st.set_page_config(
    page_title="Watchlist",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Hide the default sidebar completely
st.markdown(
    """
    <style>
        section[data-testid="stSidebar"] { display: none; }
        button[aria-label="Main menu"] { display: none; }
    </style>
    """,
    unsafe_allow_html=True,
)


def watchlist_page():
    navbar(Path(__file__).name)
    st.title("Watchlist")

    # Track pending watchlist buy when modal API unavailable
    if "watchlist_buy_ticker" not in st.session_state:
        st.session_state["watchlist_buy_ticker"] = None
    def _trigger_rerun() -> None:
        if hasattr(st, "rerun"):
            st.rerun()
        else:  # pragma: no cover - legacy Streamlit versions
            st.experimental_rerun()

    def handle_watchlist_buy_success(symbol: str) -> None:
        try:
            remove_from_watchlist(symbol)
        finally:
            if "watchlist_buy_ticker" in st.session_state:
                st.session_state["watchlist_buy_ticker"] = None
            st.session_state.pop("buy_form_open", None)
            st.session_state.pop("s_owned_total", None)
            _trigger_rerun()

    # Add-ticker input with placeholder
    # wrap in a narrow column (30% width)
    input_col, _ = st.columns([3, 7])
    # persist across reruns using session state
    if "new_ticker" not in st.session_state:
        st.session_state["new_ticker"] = ""

    def add_ticker():
        symbol = st.session_state["new_ticker"].strip().upper()
        if symbol:
            try:
                fetch_price(symbol)
            except Exception as e:
                st.error(f"Could not add {symbol}: {e}")
            else:
                add_to_watchlist(symbol)
                st.session_state["new_ticker"] = ""

    input_col.text_input(
        "Add ticker to watchlist",
        placeholder="Enter ticker symbol. E.g. AAPL",
        key="new_ticker",
    )
    input_col.button("Add", on_click=add_ticker, type="primary")

    # Load current watchlist and prices
    watchlist = get_watchlist()
    prices_df = load_watchlist_prices(watchlist)
    last_update = get_clock().now().strftime("%B %d, %Y at %I:%M %p")
    st.caption(f"Last update: {last_update}")

    # Render table header
    st.markdown("## Current Watchlist")
    cols = st.columns([3, 2, 2, 1, 1])
    cols[0].markdown("**Ticker**")
    cols[1].markdown("**Price**")
    cols[2].markdown("**Change %**")
    cols[3].markdown("**Delete**")
    cols[4].markdown("**Buy**")

    # Loop through watchlist DataFrame
    if not prices_df.empty:
        for idx, row in prices_df.iterrows():
            ticker = row["ticker"]
            price = row.get("current_price")
            if price is None or pd.isna(price):
                continue

            change_pct = None
            row_cols = st.columns([3, 2, 2, 1, 1])
            row_cols[0].write(ticker)
            row_cols[1].write(f"${float(price):.2f}")
            if change_pct is None:
                row_cols[2].write("-")
            else:
                row_cols[2].write(f"{change_pct:.2f}%")
            if row_cols[3].button("❌", key=f"del_{ticker}"):
                remove_from_watchlist(ticker)
                st.rerun()
            if row_cols[4].button("Buy", key=f"buy_{ticker}"):
                if hasattr(st, "modal"):
                    with st.modal(f"Buy {ticker}"):
                        show_buy_form(ticker_default=ticker, on_success=handle_watchlist_buy_success)
                else:
                    st.session_state["watchlist_buy_ticker"] = ticker
                    st.session_state["buy_form_open"] = True
                    _trigger_rerun()
    else:
        st.write("Your watchlist is empty. Add some tickers above!")

    if not hasattr(st, "modal"):
        pending = st.session_state.get("watchlist_buy_ticker")
        if pending:
            st.divider()
            st.subheader(f"Buy {pending}")
            show_buy_form(ticker_default=pending, on_success=handle_watchlist_buy_success)
            if st.button("Close Buy Form", key="close_watchlist_buy"):
                st.session_state["watchlist_buy_ticker"] = None
                st.session_state.pop("buy_form_open", None)
                _trigger_rerun()


if __name__ == "__main__":
    watchlist_page()
