"""User guide page for the application."""

from pathlib import Path
import os

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


def _trigger_rerun() -> None:
    if hasattr(st, "rerun"):
        st.rerun()
    else:  # pragma: no cover - legacy Streamlit fallback
        st.experimental_rerun()


def _resolve_env_path() -> Path:
    """Return the environment file path used for storing secrets."""

    app_base = os.environ.get("APP_BASE_DIR")
    if app_base:
        base_path = Path(app_base).expanduser()
        env_path = base_path / ".env"
        base_path.mkdir(parents=True, exist_ok=True)
        return env_path

    project_root = Path(__file__).resolve().parents[1]
    return project_root / ".env"


def _read_finnhub_api_key(env_path: Path) -> str:
    if not env_path.exists():
        return ""
    try:
        for line in env_path.read_text().splitlines():
            if line.startswith("FINNHUB_API_KEY="):
                return line.split("=", 1)[1].strip()
    except Exception:  # pragma: no cover - defensive
        pass
    return ""


def _write_finnhub_api_key(env_path: Path, api_key: str) -> None:
    env_path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    if env_path.exists():
        try:
            lines = env_path.read_text().splitlines()
        except Exception:  # pragma: no cover - defensive
            lines = []

    updated = False
    for idx, line in enumerate(lines):
        if line.startswith("FINNHUB_API_KEY="):
            lines[idx] = f"FINNHUB_API_KEY={api_key}"
            updated = True
            break

    if not updated:
        lines.append(f"FINNHUB_API_KEY={api_key}")

    env_path.write_text("\n".join(lines) + "\n")
    os.environ["FINNHUB_API_KEY"] = api_key


def _render_api_key_manager() -> None:
    env_path = _resolve_env_path()
    current_key = _read_finnhub_api_key(env_path)
    key_set = bool(current_key)

    state_flag = "editing_finnhub_api_key"
    if state_flag not in st.session_state:
        st.session_state[state_flag] = not key_set

    editing = st.session_state[state_flag]

    with st.expander("Finnhub API Key", expanded=editing):
        st.caption(f"Stored in `{env_path}`")

        if editing:
            with st.form("finnhub_api_form", clear_on_submit=False):
                api_input = st.text_input(
                    "Enter Finnhub API Key",
                    value="",
                    key="finnhub_api_input",
                    type="password",
                    help="Your key is stored locally in the .env file and used for live data.",
                )
                submitted = st.form_submit_button(
                    "Save API Key",
                    type="primary",
                )
                if submitted:
                    api_clean = (api_input or "").strip()
                    if not api_clean:
                        st.error("Please enter a valid Finnhub API key.")
                    else:
                        try:
                            _write_finnhub_api_key(env_path, api_clean)
                        except Exception as exc:  # pragma: no cover - filesystem errors
                            st.error(f"Failed to save API key: {exc}")
                        else:
                            st.success("Finnhub API key saved.")
                            st.session_state.pop("finnhub_api_input", None)
                            st.session_state[state_flag] = False
                            _trigger_rerun()
        else:
            masked = "●" * max(len(current_key) - 4, 0) + current_key[-4:]
            st.success(f"Finnhub API key configured ({masked}).")
            if st.button("Replace API Key", type="secondary", key="replace_api_key"):
                st.session_state[state_flag] = True
                _trigger_rerun()


_render_api_key_manager()

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
            from core.constants import ALL_MAIN_TABLES
            for table in ALL_MAIN_TABLES:
                try:
                    cur.execute(f"DELETE FROM {table}")
                except Exception as e:  # pragma: no cover
                    st.warning(f"Failed clearing {table}: {e}")
            conn.commit()
            conn.close()
            st.success("Database reset complete. Reload the app or navigate to Dashboard.")
        except Exception as e:  # pragma: no cover
            st.error(f"Reset failed: {e}")
