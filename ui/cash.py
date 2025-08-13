import streamlit as st

from data.portfolio import save_portfolio_snapshot


def show_cash_section() -> None:
    """Display cash balance and provide a toggleable form to add funds."""
    cash_value = "${:,.2f}".format(float(st.session_state.cash))

    st.subheader("Cash Balance")
    st.metric(
        label="Available Cash",
        value=cash_value,
    )

    # Move form toggle to session state initialization
    if "show_cash_form" not in st.session_state:
        st.session_state.show_cash_form = False

    if st.button("Add Cash", key="toggle_cash", type="primary"):
        st.session_state.show_cash_form = not st.session_state.show_cash_form

    if st.session_state.show_cash_form:
        with st.form("add_cash_form"):
            amount_to_add = st.number_input("Amount", min_value=0.0, step=100.0, value=100.0)
            submitted = st.form_submit_button("Add", type="primary")
            if submitted:
                if amount_to_add > 0:
                    st.session_state.cash += amount_to_add
                    save_portfolio_snapshot(st.session_state.portfolio, st.session_state.cash)
                    st.success(f"Successfully added ${amount_to_add:,.2f} to cash balance!")
                    st.session_state.show_cash_form = False
                    st.rerun()
                else:
                    st.error("Please enter an amount greater than 0")
