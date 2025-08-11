import streamlit as st

from config import COL_TICKER
from services.market import fetch_price
from services.watchlist_service import (
    add_to_watchlist,
    load_watchlist_prices,
    remove_from_watchlist,
)


def show_watchlist_sidebar() -> None:
    """Render ticker lookup and watchlist in the sidebar."""

    sidebar = st.sidebar
    sidebar.markdown("### Watchlist Tool")
    sidebar.caption("Track tickers to monitor their latest prices.")
    sidebar.divider()
    feedback_slot = sidebar.empty()

    def add_watchlist(sym: str, price: float, portfolio_tickers: set[str]) -> None:
        """Add ``sym`` to the watchlist."""

        if sym in st.session_state.watchlist:
            st.session_state.watchlist_feedback = ("info", f"{sym} already in watchlist.")
        elif sym in portfolio_tickers:
            st.session_state.watchlist_feedback = ("info", f"{sym} already in portfolio.")
        else:
            add_to_watchlist(sym)
            st.session_state.watchlist_prices[sym] = price
            st.session_state.watchlist_feedback = ("success", f"{sym} added to watchlist.")

    portfolio_tickers = (
        set(st.session_state.portfolio[COL_TICKER].values)
        if not st.session_state.portfolio.empty
        else set()
    )
    removed = [t for t in st.session_state.watchlist if t in portfolio_tickers]
    if removed:
        for t in removed:
            remove_from_watchlist(t)
            st.session_state.watchlist_prices.pop(t, None)
        st.session_state.watchlist_feedback = (
            "info",
            f"Removed {', '.join(removed)} from watchlist (now in portfolio).",
        )

    error_slot = sidebar.empty()
    with sidebar.form("lookup_form", clear_on_submit=True):
        symbol = st.text_input(
            "Stock Symbol",
            key="lookup_symbol",
            placeholder="(e.g., AAPL)",
            label_visibility="collapsed",
        )
        submitted = st.form_submit_button("Add to Watchlist")

    if submitted:
        if symbol:
            sym = symbol.upper()
            price = fetch_price(sym)
            if price is None:
                error_slot.error("Ticker not found.")
            else:
                add_watchlist(sym, price, portfolio_tickers)
        else:
            error_slot.error("Please enter a ticker symbol.")

    if st.session_state.watchlist:
        header = sidebar.container()
        hcol1, hcol2 = header.columns([4, 1])
        hcol1.subheader("Watchlist")
        if hcol2.button("🔄", key="refresh_watchlist", help="Refresh prices"):
            prices = load_watchlist_prices(st.session_state.watchlist)
            st.session_state.watchlist_prices.update(
                {t: prices.get(t) for t in st.session_state.watchlist}
            )

        for t in sorted(list(st.session_state.watchlist)):
            price = st.session_state.watchlist_prices.get(t)
            price_str = f"${price:.2f}" if price is not None else "N/A"
            row = sidebar.container()
            col1, col2 = row.columns([4, 1])
            col1.markdown(
                f"**{t}**<br><span style='color:gray;font-size:0.9em'>{price_str}</span>",
                unsafe_allow_html=True,
            )
            if col2.button("🗑️", key=f"rm_{t}", help=f"Remove {t}"):
                remove_from_watchlist(t)
                st.session_state.watchlist_prices.pop(t, None)
                st.session_state.watchlist_feedback = (
                    "info",
                    f"Removed {t} from watchlist.",
                )

    if st.session_state.watchlist_feedback:
        kind, text = st.session_state.watchlist_feedback
        getattr(feedback_slot, kind)(text)
        st.session_state.watchlist_feedback = None
    sidebar.divider()
