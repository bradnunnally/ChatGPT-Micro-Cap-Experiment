"""Streamlit app for local portfolio tracking and AI‑assisted trading."""

from pathlib import Path
import os

import streamlit as st

from components.nav import navbar
from dotenv import dotenv_values
from infra.logging import get_correlation_id, set_correlation_id
from ui.dashboard import render_dashboard

# Manual .env ingestion (avoids find_dotenv() stack inspection issues under Streamlit reload)
try:  # pragma: no cover
    vals = dotenv_values(".env")
    for k, v in vals.items():
        if k not in os.environ and v is not None:
            os.environ[k] = v
except Exception:
    pass

st.set_page_config(
    page_title="AI Assisted Trading",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Ensure a stable correlation ID per session for traceable logs
if "correlation_id" not in st.session_state:
    # get_correlation_id() will generate a new one lazily
    st.session_state["correlation_id"] = get_correlation_id()
else:
    set_correlation_id(str(st.session_state["correlation_id"]))

# Simple CSS for basic button improvements
st.markdown(
    """
<style>
/* Basic button styling improvements */
.stButton > button {
    border-radius: 6px;
    font-weight: 500;
    transition: all 0.2s ease;
}

/* Use data attributes for more reliable targeting */
button[data-testid="baseButton-primary"] {
    background-color: #2196f3;
    border: 1px solid #2196f3;
    color: white;
}

button[data-testid="baseButton-primary"]:hover {
    background-color: #1976d2;
    border: 1px solid #1976d2;
    transform: translateY(-1px);
}

button[data-testid="baseButton-secondary"] {
    background-color: #ffebee;
    border: 1px solid #e57373;
    color: #c62828;
}

button[data-testid="baseButton-secondary"]:hover {
    background-color: #ffcdd2;
    border: 1px solid #e53935;
    transform: translateY(-1px);
}
</style>
""",
    unsafe_allow_html=True,
)

navbar(Path(__file__).name)

st.header("Portfolio Dashboard")


def main() -> None:
    """Application entry point."""

    render_dashboard()


if __name__ == "__main__":
    main()
