"""UI components for manual pricing management."""

import streamlit as st
from services.manual_pricing import manual_pricing_service
import os

LEGACY_PROVIDER_FLAG_ENV = {"0", "", None}

def _using_micro_provider() -> bool:
    """Determine if micro provider mode is active (Finnhub or Synthetic)."""
    flag = os.getenv("ENABLE_MICRO_PROVIDERS") or os.getenv("APP_USE_FINNHUB")
    return (flag or "").lower() in {"1", "true", "yes", "on"}


def show_manual_pricing_section():
    """Display manual pricing management section."""
    
    with st.expander("Manual Price Overrides", expanded=False):
        st.caption("Set manual prices when market data APIs are unavailable")
        
        try:
            # Current manual prices
            manual_prices = manual_pricing_service.get_all_prices()
        except Exception as e:
            st.error(f"Error loading manual prices: {e}")
            # Initialize the session state manually as a fallback
            if "manual_prices" not in st.session_state:
                st.session_state["manual_prices"] = {}
            manual_prices = {}
        
        if manual_prices:
            st.subheader("Current Manual Prices")
            col1, col2, col3 = st.columns([2, 2, 1])
            
            with col1:
                st.text("Ticker")
            with col2:
                st.text("Price")
            with col3:
                st.text("Action")
            
            for ticker, price in manual_prices.items():
                col1, col2, col3 = st.columns([2, 2, 1])
                with col1:
                    st.text(ticker)
                with col2:
                    st.text(f"${price:.2f}")
                with col3:
                    if st.button("Remove", key=f"remove_{ticker}"):
                        manual_pricing_service.remove_price(ticker)
                        st.rerun()
            
            if st.button("Clear All Manual Prices", type="secondary"):
                manual_pricing_service.clear_all()
                st.success("All manual prices cleared")
                st.rerun()
        
        # Add new manual price
        st.subheader("Add Manual Price")
        
        with st.form("manual_price_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            
            with col1:
                ticker_input = st.text_input(
                    "Ticker Symbol",
                    placeholder="e.g., AAPL",
                    key="manual_ticker"
                ).strip().upper()
            
            with col2:
                price_input = st.number_input(
                    "Current Price ($)",
                    min_value=0.01,
                    value=1.00,
                    step=0.01,
                    format="%.2f",
                    key="manual_price"
                )
            
            submitted = st.form_submit_button("Set Manual Price", type="primary")
            
            if submitted:
                if not ticker_input:
                    st.error("Please enter a ticker symbol")
                elif price_input <= 0:
                    st.error("Price must be positive")
                else:
                    try:
                        manual_pricing_service.set_price(ticker_input, price_input)
                        st.success(f"Manual price set for {ticker_input}: ${price_input:.2f}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error setting manual price: {e}")


def show_api_status_warning():
    """Show warning when API is having issues for legacy provider only."""
    if _using_micro_provider():
    # Placeholder: could show micro provider health indicators here
        return
    st.warning(
        "⚠️ **Market Data API Issues Detected**\n\n"
        "Yahoo Finance API may be rate limited. Current prices may lag. You can:\n"
        "- Use manual price overrides below for accurate portfolio values\n"
        "- Continue trading (buy/sell still works without live prices)\n"
        "- Wait for API to recover (prices will auto-update)"
    )
