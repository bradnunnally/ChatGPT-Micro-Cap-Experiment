"""
Data Migration Page
Main page for portfolio import/export functionality.
"""

import streamlit as st
from ui.data_migration import render_data_migration_page


def main():
    """Main function for the data migration page."""
    
    st.set_page_config(
        page_title="Portfolio Data Migration",
        page_icon="📁",
        layout="wide"
    )
    
    render_data_migration_page()


if __name__ == "__main__":
    main()