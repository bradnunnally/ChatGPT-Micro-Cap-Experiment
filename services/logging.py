from __future__ import annotations

import streamlit as st

# Re-export structured logging helpers
from infra.logging import (  # noqa: F401
    AuditLogger,
    audit as audit_logger,
    get_correlation_id,
    get_logger,
    new_correlation_id,
    set_correlation_id,
)

# Module-level logger for services
logger = get_logger(__name__)


def log_error(message: str) -> None:
    """Append a timestamped message to session-scoped log and emit JSON log."""
    # Keep existing behavior for UI tests that inspect session_state
    st.session_state.setdefault("error_log", []).append(message)
    # Emit structured error log with correlation id
    logger.error(message, extra={"event": "error", "ui_session": True})
