"""Navigation bar component used across pages."""

import base64
from pathlib import Path

import streamlit as st
from services.alerts import load_alert_state

from services.session import init_session_state
from services.market import get_metrics


def _alert_badge_html() -> str:
    try:
        state = load_alert_state()
        events = state.get("open_events") if isinstance(state, dict) else []
        if events:
            sev = 0
            for e in events:
                t = e.get("type")
                if t == "drawdown_threshold":
                    sev = max(sev, 2)
                elif t in {"var95", "concentration_top1"}:
                    sev = max(sev, 1)
            color = {2: "#d32f2f", 1: "#ef6c00"}.get(sev, "#616161")
            return f"<span style='background:{color};color:#fff;padding:2px 8px;border-radius:12px;font-size:0.65rem;margin-left:0.5rem;'>ALERTS {len(events)}</span>"
    except Exception:
        pass
    return ""


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

        alerts_badge = _alert_badge_html()
        st.markdown(
            f"""
            <div class="nav-container">
                <a class="nav-link {'active' if active_page == Path('app.py').name else ''}" href="/" target="_self">Dashboard</a>
                <a class="nav-link {'active' if active_page == Path('pages/performance_page.py').name else ''}" href="/performance_page" target="_self">Performance</a>
                <a class="nav-link {'active' if active_page == Path('pages/backtest_page.py').name else ''}" href="/backtest_page" target="_self">Backtests</a>
                <a class="nav-link {'active' if active_page == Path('pages/strategies_page.py').name else ''}" href="/strategies_page" target="_self">Strategies</a>
                <a class="nav-link {'active' if active_page == Path('pages/user_guide_page.py').name else ''}" href="/user_guide_page" target="_self">User Guide</a>
                <a class="nav-link {'active' if active_page == Path('pages/watchlist.py').name else ''}" href="/watchlist" target="_self">Watchlist</a>
                {csv_link}
                {alerts_badge}
            </div>
            <hr />
            """,
            unsafe_allow_html=True,
        )

    # Lightweight metrics status (top-right via empty container)
    metrics_container = st.empty()
    m = get_metrics()
    # Render a concise inline metrics summary
    summary = f"CB:{m.get('circuit_state')} F:{int(m.get('circuit_failures',0))} S:{int(m.get('price_fetch_bulk_success',0))} E:{int(m.get('price_fetch_bulk_failure',0))}"
    metrics_container.markdown(f"<div style='text-align:right;font-size:0.75rem;color:#666;'>[{summary}]</div>", unsafe_allow_html=True)
