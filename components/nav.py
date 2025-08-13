"""Navigation bar component used across pages."""

import base64
from pathlib import Path

import streamlit as st

from services.session import init_session_state


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

    st.title("AI Assisted Trading")

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
