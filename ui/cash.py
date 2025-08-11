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
            st.number_input("Amount", key="ac_amount", min_value=0.0, step=100.0)
            submitted = st.form_submit_button("Add", type="primary")
            if submitted:
                st.session_state.cash += st.session_state.ac_amount
                st.session_state.show_cash_form = False
                save_portfolio_snapshot(st.session_state.portfolio, st.session_state.cash)
