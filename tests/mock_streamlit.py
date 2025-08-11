import pandas as pd
import contextlib
from unittest.mock import patch
from dataclasses import dataclass, field
from typing import Set, Dict


@dataclass
class WatchlistState:
    """Container for watchlist state"""

    tickers: Set[str] = field(default_factory=set)
    prices: Dict[str, float] = field(default_factory=dict)


@contextlib.contextmanager
def mock_streamlit_context():
    """Context manager to properly mock Streamlit runtime"""
    with patch("streamlit.runtime.scriptrunner.script_run_context.get_script_run_ctx"):
        with patch("streamlit.runtime.state.session_state_proxy._get_session_state"):
            yield


# Keep minimal StreamlitMock for legacy tests that still need it
class StreamlitMock:
    def __init__(self):
        self.session_state = type(
            "SessionState", (), {"watchlist_state": WatchlistState(), "cash": 10000.0}
        )()
        self.calls = []

    def info(self, text):
        self.calls.append(("info", text))

    def assert_called(self, method_name):
        return any(call[0] == method_name for call in self.calls)
