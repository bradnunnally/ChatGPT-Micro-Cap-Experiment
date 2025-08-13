"""User guide page for the application."""

from pathlib import Path

import streamlit as st

from components.nav import navbar
from ui.user_guide import show_user_guide

st.set_page_config(
    page_title="User Guide",
    layout="wide",
    initial_sidebar_state="collapsed",
)

navbar(Path(__file__).name)

st.header("User Guide")

show_user_guide()

# --- Hidden maintenance section (collapsible) ----------------------------------
with st.expander("Admin / Maintenance (advanced)", expanded=False):
    st.markdown("**Reset Environment**: Clear all positions, history and cash for a pristine start. This action cannot be undone.")
    confirm = st.checkbox("I understand this will permanently delete current portfolio data.")
    if st.button("Reset to Empty Portfolio", disabled=not confirm, type="secondary"):
        import sqlite3, os
        from config.settings import settings
        from data.db import init_db
        os.environ["NO_DEV_SEED"] = "1"  # prevent automatic seeding after reset
        init_db()
        db_path = settings.paths.db_file
        try:
            conn = sqlite3.connect(str(db_path))
            cur = conn.cursor()
            for table in ("portfolio", "cash", "trade_log", "portfolio_history"):
                try:
                    cur.execute(f"DELETE FROM {table}")
                except Exception as e:  # pragma: no cover
                    st.warning(f"Failed clearing {table}: {e}")
            conn.commit()
            conn.close()
            st.success("Database reset complete. Reload the app or navigate to Dashboard.")
        except Exception as e:  # pragma: no cover
            st.error(f"Reset failed: {e}")
