from decimal import Decimal, InvalidOperation

import streamlit as st

from config import COL_PRICE, COL_SHARES, COL_TICKER
from services.core.validation import (
    validate_price as _validate_price,
)
from services.core.validation import (
    validate_shares as _validate_shares,
)
from services.core.validation import (
    validate_ticker as _validate_ticker,
)
from services.exceptions.validation import ValidationError as _ValidationError
from services.market import fetch_price
from services.trading import manual_buy, manual_sell

# Note: Core services are imported where used to reduce import-time side effects.


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


def _render_feedback() -> None:
    """Render and clear a feedback message stored in session state.

    Expects st.session_state.feedback to be a tuple (level, message), where level is
    either "success" or "error". Once rendered, the message is removed to avoid
    duplicate display on subsequent reruns.
    """
    fb = st.session_state.pop("feedback", None)
    if not fb:
        return
    level, msg = fb
    if level == "success":
        st.success(msg, icon="✅")
    else:
        st.error(msg, icon="⚠️")


def show_buy_form(ticker_default: str = "") -> None:
    """Render and process the buy form inside an expander.

    Parameters
    ----------
    ticker_default: str, optional
        When provided, pre-populates the ticker input with this value.
    """

    def submit_buy() -> None:
        """Validate inputs with centralized validators, then execute buy."""
        try:
            ticker = str(st.session_state.b_ticker).strip().upper()
            shares = int(st.session_state.b_shares)
            price_float = float(st.session_state.b_price)
            # Convert via string to avoid binary float artifacts
            price_dec = Decimal(str(price_float))

            _validate_ticker(ticker)
            _validate_shares(shares)
            _validate_price(price_dec)

            stop_loss = 0.0
            if price_float > 0 and st.session_state.b_stop_pct > 0:
                stop_loss = price_float * (1 - st.session_state.b_stop_pct / 100)
                # Validate stop only if set
                _validate_price(Decimal(str(stop_loss)))

            ok, msg, port, cash = manual_buy(
                ticker,
                shares,
                price_float,
                stop_loss,
                st.session_state.portfolio,
                st.session_state.cash,
                repo=st.session_state.get("repo"),
            )
            if ok:
                st.session_state.portfolio = port
                st.session_state.cash = cash
                st.session_state.feedback = ("success", msg)
                st.session_state.pop("b_ticker", None)
                st.session_state.pop("b_shares", None)
                st.session_state.pop("b_price", None)
                st.session_state.pop("b_stop_pct", None)
                st.session_state.buy_form_open = False
            else:
                st.session_state.feedback = ("error", msg)
        except (ValueError, InvalidOperation, _ValidationError) as e:
            # Surface validation/parsing errors inline
            st.session_state.feedback = ("error", str(e))

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
                calc_stop = st.session_state.b_price * (1 - st.session_state.b_stop_pct / 100)
                st.caption(f"Stop loss price: ${calc_stop:.2f}")

            col1, col2 = st.columns(2)
            with col1:
                submitted = st.form_submit_button(
                    "Submit Buy", on_click=submit_buy, use_container_width=True, type="primary"
                )
            with col2:
                if st.form_submit_button("Cancel", use_container_width=True, type="secondary"):
                    st.session_state.buy_form_open = False
                    st.rerun()

            if submitted:
                st.session_state.buy_form_open = False
    # Render any pending feedback message after the form region
    _render_feedback()


def show_sell_form() -> None:
    """Render and process the sell form inside an expander."""

    def submit_sell() -> None:
        """Validate inputs with centralized validators, then execute sell."""
        try:
            selected_ticker = st.session_state.get("s_ticker_selected", None)
            if not selected_ticker or selected_ticker == "Select a Ticker":
                st.session_state.feedback = ("error", "Please select a ticker to sell.")
                return

            ticker = str(selected_ticker).strip().upper()
            shares = int(st.session_state.s_shares)
            price_float = float(st.session_state.s_price)
            price_dec = Decimal(str(price_float))

            _validate_ticker(ticker)
            _validate_shares(shares)
            _validate_price(price_dec)

            ok, msg, port, cash = manual_sell(
                ticker,
                shares,
                price_float,
                st.session_state.portfolio,
                st.session_state.cash,
                repo=st.session_state.get("repo"),
            )
            if ok:
                st.session_state.portfolio = port
                st.session_state.cash = cash
                st.session_state.feedback = ("success", msg)
                st.session_state.pop("s_ticker_selected", None)
                st.session_state.pop("s_ticker_select", None)
                st.session_state.pop("s_shares", None)
                st.session_state.pop("s_price", None)
                st.session_state.sell_form_open = False
            else:
                st.session_state.feedback = ("error", msg)
        except (ValueError, InvalidOperation, _ValidationError) as e:
            st.session_state.feedback = ("error", str(e))

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
            key="s_ticker_select",
        )

        # Only proceed if a real ticker is selected
        if selected == "Select a Ticker":
            st.warning("Please choose a ticker from your portfolio before selling.")
            if st.button("Close", key="close_sell_form2", type="secondary"):
                st.session_state.sell_form_open = False
                st.rerun()
            return

        matching = st.session_state.portfolio[st.session_state.portfolio[COL_TICKER] == selected]

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
                    "Submit Sell", on_click=submit_sell, use_container_width=True, type="primary"
                )
            with col2:
                if st.form_submit_button("Cancel", use_container_width=True, type="secondary"):
                    st.session_state.sell_form_open = False
                    st.rerun()

            if submitted:
                st.session_state.sell_form_open = False
    # Render any pending feedback message after the form region
    _render_feedback()
