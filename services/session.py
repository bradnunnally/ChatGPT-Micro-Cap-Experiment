import streamlit as st

from app_settings import settings
from data.portfolio import load_portfolio  # type: ignore
from data.watchlist import load_watchlist  # type: ignore
from services.core.sqlite_repository import SqlitePortfolioRepository


def init_session_state() -> None:
    """Initialise default values in ``st.session_state`` on first run."""

    for key, default in {
        "b_ticker": "",
        "b_shares": 1.0,
        "b_price": 1.0,
        "b_stop_pct": 0.0,
        "s_ticker": "",
        "s_shares": 1.0,
        "s_price": 1.0,
        "ac_amount": 0.0,
        "lookup_symbol": "",
        "watchlist_feedback": None,
        "watchlist": [],
        "watchlist_prices": {},
        "show_cash_form": False,
        "daily_summary": "",
        "show_info": True,
    }.items():
        st.session_state.setdefault(key, default)

    # Load portfolio and cash from database on startup with portfolio context
    if "portfolio" not in st.session_state or "cash" not in st.session_state:
        from services.portfolio_service import ensure_portfolio_context_in_queries
        
        # Ensure we have a current portfolio context
        current_portfolio_id = ensure_portfolio_context_in_queries()
        
        # Load portfolio using the current context
        portfolio_df, cash_amount, needs_cash = load_portfolio()
        
        # If we have valid data, use it; otherwise mark as needing initialization
        if not portfolio_df.empty or cash_amount > 0:
            st.session_state.portfolio = portfolio_df
            st.session_state.cash = cash_amount
            st.session_state.needs_cash = False  # We have data, no need to initialize
        else:
            # No data found - this should trigger the initialization flow
            st.session_state.portfolio = portfolio_df  # Empty dataframe
            st.session_state.cash = cash_amount if cash_amount is not None else 0.0
            st.session_state.needs_cash = needs_cash

    # Initialize a repository instance for persistence if not present
    if "repo" not in st.session_state:
        st.session_state.repo = SqlitePortfolioRepository()

    if not st.session_state.watchlist and settings.paths.watchlist_file.exists():
        st.session_state.watchlist = load_watchlist()
