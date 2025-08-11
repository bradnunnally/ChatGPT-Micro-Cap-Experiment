import streamlit as st
import pandas as pd

from config import COL_TICKER, COL_SHARES, COL_PRICE
from services.market import fetch_price
from services.trading import manual_buy, manual_sell
from services.core.trading_service import TradingService
from services.core.validation_service import ValidationService


def validate_buy_form(data: dict) -> bool:
    """Validate buy form data."""
    try:
        # Check required fields
        if not data.get("ticker"):
            st.error("Ticker symbol is required")
            return False

        shares = float(data.get("shares", 0))
        price = float(data.get("price", 0))
        
        if shares <= 0:
            st.error("Number of shares must be positive")
            return False
            
        if price <= 0:
            st.error("Price must be positive")
            return False

        total_cost = shares * price
        if total_cost > st.session_state.cash:
            st.error("Insufficient funds for purchase")
            return False

        return True

    except (ValueError, TypeError):
        st.error("Invalid number format")
        return False


def validate_sell_form(data: dict) -> bool:
    """
    Validate sell form data.
    Returns True if valid, False otherwise.
    """
    if not data.get("ticker"):
        st.error("Ticker symbol is required")
        return False

    try:
        shares = float(data.get("shares", 0))
        price = float(data.get("price", 0))

        if shares <= 0:
            st.error("Number of shares must be positive")
            return False

        if price <= 0:
            st.error("Price must be positive")
            return False

        # Check if we have enough shares
        portfolio = st.session_state.portfolio
        matching = portfolio[portfolio["Ticker"] == data["ticker"]]
        if matching.empty or matching.iloc[0]["Shares"] < shares:
            st.error("Insufficient shares for this sale")
            return False

        return True

    except ValueError:
        st.error("Invalid number format")
        return False


def show_buy_form(ticker_default: str = "") -> None:
    """Render and process the buy form inside an expander.

    Parameters
    ----------
    ticker_default: str, optional
        When provided, pre-populates the ticker input with this value.
    """

    def submit_buy() -> None:
        if st.session_state.b_shares <= 0 or st.session_state.b_price <= 0:
            st.session_state.feedback = (
                "error",
                "Shares and price must be positive.",
            )
            return
        ok, msg, port, cash = manual_buy(
            st.session_state.b_ticker,
            st.session_state.b_shares,
            st.session_state.b_price,
            st.session_state.b_price * (1 - st.session_state.b_stop_pct / 100)
            if st.session_state.b_price > 0 and st.session_state.b_stop_pct > 0
            else 0.0,
            st.session_state.portfolio,
            st.session_state.cash,
        )
        if ok:
            st.session_state.portfolio = port
            st.session_state.cash = cash
            st.session_state.feedback = ("success", msg)
            st.session_state.pop("b_ticker", None)
            st.session_state.pop("b_shares", None)
            st.session_state.pop("b_price", None)
            st.session_state.pop("b_stop_pct", None)
            # Close the buy form after successful submission
            st.session_state.buy_form_open = False
            # Immediately refresh to show updated portfolio
            st.rerun()
        else:
            st.session_state.feedback = ("error", msg)

    # Initialize buy form state in session state
    if "buy_form_open" not in st.session_state:
        st.session_state.buy_form_open = False
    
    # Create a button to toggle the buy form
    if st.button("📈 Log a Buy", use_container_width=True, type="primary"):
        st.session_state.buy_form_open = not st.session_state.buy_form_open
    
    # Show the buy form if it's open
    if st.session_state.buy_form_open:
        st.markdown("### Buy Stock")
        
        with st.form("buy_form", clear_on_submit=True):
            st.text_input(
                "Ticker",
                key="b_ticker",
                placeholder="e.g. AAPL",
                value=ticker_default,
            )
            st.number_input(
                "Shares",
                min_value=1,
                value=1,
                step=1,
                key="b_shares",
            )
            st.number_input(
                "Price",
                min_value=0.0,
                value=0.0,
                step=0.01,
                format="%.2f",
                key="b_price",
            )
            st.number_input(
                "Stop-loss %",
                min_value=0.0,
                value=0.0,
                max_value=100.0,
                step=0.1,
                format="%.1f",
                key="b_stop_pct",
            )
            if st.session_state.b_price > 0 and st.session_state.b_stop_pct > 0:
                calc_stop = st.session_state.b_price * (
                    1 - st.session_state.b_stop_pct / 100
                )
                st.caption(f"Stop loss price: ${calc_stop:.2f}")
            
            col1, col2 = st.columns(2)
            with col1:
                submitted = st.form_submit_button(
                    "Submit Buy", 
                    on_click=submit_buy,
                    use_container_width=True,
                    type="primary"
                )
            with col2:
                if st.form_submit_button(
                    "Cancel",
                    use_container_width=True,
                    type="secondary"
                ):
                    st.session_state.buy_form_open = False
                    st.rerun()
            
            if submitted:
                st.session_state.buy_form_open = False


def show_sell_form() -> None:
    """Render and process the sell form inside an expander."""

    def submit_sell() -> None:
        if st.session_state.s_shares <= 0 or st.session_state.s_price <= 0:
            st.session_state.feedback = (
                "error",
                "Shares and price must be positive.",
            )
            return
        
        # Get the selected ticker from session state
        selected_ticker = st.session_state.get("s_ticker_selected", None)
        
        if not selected_ticker or selected_ticker == "Select a Ticker":
            st.session_state.feedback = (
                "error",
                "Please select a ticker to sell.",
            )
            return
            
        ok, msg, port, cash = manual_sell(
            selected_ticker,
            st.session_state.s_shares,
            st.session_state.s_price,
            st.session_state.portfolio,
            st.session_state.cash,
        )
        if ok:
            st.session_state.portfolio = port
            st.session_state.cash = cash
            st.session_state.feedback = ("success", msg)
            # Clear form values and close the form
            st.session_state.pop("s_ticker_selected", None)
            st.session_state.pop("s_ticker_select", None)
            st.session_state.pop("s_shares", None)
            st.session_state.pop("s_price", None)
            # Close the sell form after successful submission
            st.session_state.sell_form_open = False
        else:
            st.session_state.feedback = ("error", msg)

    # Initialize sell form state in session state
    if "sell_form_open" not in st.session_state:
        st.session_state.sell_form_open = False
    
    # Create a button to toggle the sell form
    if st.button("📉 Log a Sale", use_container_width=True, type="primary"):
        st.session_state.sell_form_open = not st.session_state.sell_form_open
    
    # Show the sell form if it's open
    if st.session_state.sell_form_open:
        st.markdown("### Sell Stock")
        
        holdings = st.session_state.portfolio
        if holdings.empty:
            st.info("You have no holdings to sell.")
            if st.button("Close", key="close_sell_form", type="secondary"):
                st.session_state.sell_form_open = False
                st.rerun()
            return

        # Build options with a placeholder
        tickers = ["Select a Ticker"] + sorted(
            st.session_state.portfolio[COL_TICKER].unique().tolist()
        )

        # Keep the selectbox to allow dynamic updates
        selected = st.selectbox(
            "Ticker",
            options=tickers,
            index=0,  # Force default selection to "Select a Ticker"
            key="s_ticker_select"
        )

        # Only proceed if a real ticker is selected
        if selected == "Select a Ticker":
            st.warning("Please choose a ticker from your portfolio before selling.")
            if st.button("Close", key="close_sell_form2", type="secondary"):
                st.session_state.sell_form_open = False
                st.rerun()
            return

        matching = st.session_state.portfolio[
            st.session_state.portfolio[COL_TICKER] == selected
        ]

        # Check if matching shares exist before proceeding
        if matching.empty:
            st.error(f"No shares found for {selected}")
            if st.button("Close", key="close_sell_form3", type="secondary"):
                st.session_state.sell_form_open = False
                st.rerun()
            return

        max_shares = int(matching.iloc[0][COL_SHARES])
        latest_price = float(matching.iloc[0][COL_PRICE])
        fetched_price = fetch_price(selected)
        price_default = fetched_price if fetched_price is not None else latest_price

        # Determine min/default values
        share_min = 1 if max_shares > 0 else 0
        share_default = 1 if max_shares > 0 else 0

        if max_shares == 0:
            st.info("You have no shares to sell for this ticker.")
            if st.button("Close", key="close_sell_form4", type="secondary"):
                st.session_state.sell_form_open = False
                st.rerun()
            return

        # Store the selected ticker in session state for the submit function
        st.session_state.s_ticker_selected = selected

        # Now render the form with the dynamic fields
        with st.form("sell_form", clear_on_submit=True):
            st.write(f"**Selling {selected}** (You own {max_shares} shares)")
            
            st.number_input(
                "Shares to sell",
                min_value=share_min,
                value=share_default,
                max_value=max_shares,
                step=1,
                key="s_shares",
            )
            st.number_input(
                "Price",
                min_value=0.0,
                value=price_default,
                step=0.01,
                format="%.2f",
                key="s_price",
            )
            
            col1, col2 = st.columns(2)
            with col1:
                submitted = st.form_submit_button(
                    "Submit Sell", 
                    on_click=submit_sell,
                    use_container_width=True,
                    type="primary"
                )
            with col2:
                if st.form_submit_button(
                    "Cancel",
                    use_container_width=True,
                    type="secondary"
                ):
                    st.session_state.sell_form_open = False
                    st.rerun()
            
            if submitted:
                st.session_state.sell_form_open = False


