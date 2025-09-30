"""
Enhanced Analytics Page

Advanced portfolio analytics with multi-portfolio comparisons,
strategy-specific metrics, and custom benchmark analysis.
"""

import streamlit as st
from pathlib import Path

from components.nav import navbar
from ui.enhanced_analytics import render_enhanced_analytics_page

st.set_page_config(
    page_title="Enhanced Analytics - Micro-Cap Experiment",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Navigation
navbar(Path(__file__).name)

# Main content
render_enhanced_analytics_page()