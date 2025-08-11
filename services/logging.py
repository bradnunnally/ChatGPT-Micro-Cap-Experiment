import logging
from datetime import datetime

import streamlit as st

# Create and configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Create console handler if not already exists
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def log_error(message: str) -> None:
    """Append a timestamped ``message`` to a session-scoped error log."""

    st.session_state.setdefault("error_log", []).append(
        f"{datetime.now():%H:%M:%S} - {message}"
    )
