"""Navigation bar component used across pages."""

import base64
import os
import threading
import time
from pathlib import Path

import streamlit as st

from services.session import init_session_state


def _render_portfolio_selector() -> None:
    """Render the portfolio selection dropdown."""
    try:
        from services.portfolio_service import portfolio_service
        
        # Get available portfolios
        portfolios = portfolio_service.get_all_active_portfolios()
        if len(portfolios) <= 1:
            # Only show selector if there are multiple portfolios
            return
        
        # Create options for selectbox
        options = [(p.name, p.id) for p in portfolios]
        portfolio_names = [name for name, _ in options]
        portfolio_ids = [pid for _, pid in options]
        
        # Get current selection
        current_portfolio = portfolio_service.get_current_portfolio()
        current_index = 0
        if current_portfolio:
            try:
                current_index = portfolio_ids.index(current_portfolio.id)
            except ValueError:
                current_index = 0
        
        # Render selectbox
        selected_name = st.selectbox(
            "Portfolio",
            options=portfolio_names,
            index=current_index,
            key="portfolio_selector",
            help="Select active portfolio"
        )
        
        # Handle selection change
        if selected_name:
            selected_id = portfolio_ids[portfolio_names.index(selected_name)]
            if current_portfolio is None or selected_id != current_portfolio.id:
                portfolio_service.set_current_portfolio(selected_id)
                st.rerun()  # Refresh to update data
                
    except Exception as e:
        # Fail gracefully - portfolio selection is optional
        st.caption("Portfolio selection unavailable")


def _shutdown_server() -> None:
    """Initiate a graceful app shutdown after notifying the user."""

    message = "Shutting down app…"
    # toast available on newer Streamlit versions
    if hasattr(st, "toast"):
        st.toast(message, icon="👋")
    else:  # pragma: no cover - legacy fallback
        st.warning(message)

    def _kill():
        time.sleep(0.6)
        os._exit(0)

    threading.Thread(target=_kill, daemon=True).start()


def navbar(active_page: str) -> None:
    """Render the application title and horizontal navigation bar.

    Parameters
    ----------
    active_page:
        Name of the current file (e.g. ``Path(__file__).name``).
    """

    init_session_state()

    st.markdown(
        """
        <style>

            /* Hide sidebar and hamburger */
            section[data-testid="stSidebar"] { display: none !important; }
            div[data-testid="stSidebarNav"] { display: none !important; }
            button[aria-label="Main menu"] { display: none !important; }

            .nav-container {
                display: flex;
                gap: 2rem;
                padding-bottom: 0.25rem;
            }
            .nav-link {
                text-decoration: none;
                color: inherit;
                border-bottom: 3px solid transparent;
                padding-bottom: 0.25rem;
            }
            .nav-link:hover {
                border-bottom: 3px solid #999999;
            }
            .nav-link.active {
                font-weight: bold;
                border-bottom: 3px solid red;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

    header_cols = st.columns([4, 2, 1])
    with header_cols[0]:
        st.title("AI Assisted Trading")
    with header_cols[1]:
        # Portfolio selector
        _render_portfolio_selector()
    with header_cols[2]:
        quit_key = f"quit_app_{Path(active_page).stem}" if active_page else "quit_app"
        if st.button("Quit App", key=quit_key, type="secondary"):
            _shutdown_server()

    nav = st.container()
    with nav:
        csv_link = ""
        if not st.session_state.portfolio.empty:
            csv = st.session_state.portfolio.to_csv(index=False).encode("utf-8")
            b64 = base64.b64encode(csv).decode()
            csv_link = f"<a class='nav-link' href='data:text/csv;base64,{b64}' download='portfolio_snapshot.csv'>Download Portfolio</a>"
        else:
            csv_link = "<span class='nav-link'>Download Portfolio</span>"

        st.markdown(
            f"""
            <div class="nav-container">
                <a class="nav-link {'active' if active_page == Path('app.py').name else ''}" href="/" target="_self">Dashboard</a>
                <a class="nav-link {'active' if active_page == Path('pages/performance_page.py').name else ''}" href="/performance_page" target="_self">Performance</a>
                <a class="nav-link {'active' if active_page == Path('pages/user_guide_page.py').name else ''}" href="/user_guide_page" target="_self">User Guide</a>
                <a class="nav-link {'active' if active_page == Path('pages/watchlist.py').name else ''}" href="/watchlist" target="_self">Watchlist</a>
                {csv_link}
            </div>
            <hr />
            """,
            unsafe_allow_html=True,
        )
