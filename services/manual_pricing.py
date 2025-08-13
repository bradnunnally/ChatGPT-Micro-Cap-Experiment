"""Manual pricing service for when market data APIs are unavailable."""

import logging
from typing import Dict, Optional
import streamlit as st

logger = logging.getLogger(__name__)


class ManualPricingService:
    """Service to manage manual price overrides when market APIs fail."""
    
    def __init__(self):
        self._session_key = "manual_prices"
        self._ensure_initialized()
    
    def _ensure_initialized(self):
        """Ensure the session state key is initialized."""
        if self._session_key not in st.session_state:
            st.session_state[self._session_key] = {}
    
    def set_price(self, ticker: str, price: float) -> None:
        """Set a manual price override for a ticker."""
        self._ensure_initialized()
        ticker = ticker.upper().strip()
        if price <= 0:
            raise ValueError("Price must be positive")
        
        st.session_state[self._session_key][ticker] = float(price)
        logger.info(f"Manual price set for {ticker}: ${price:.2f}")
    
    def get_price(self, ticker: str) -> Optional[float]:
        """Get manual price override for a ticker."""
        self._ensure_initialized()
        ticker = ticker.upper().strip()
        return st.session_state[self._session_key].get(ticker)
    
    def remove_price(self, ticker: str) -> None:
        """Remove manual price override for a ticker."""
        self._ensure_initialized()
        ticker = ticker.upper().strip()
        if ticker in st.session_state[self._session_key]:
            del st.session_state[self._session_key][ticker]
            logger.info(f"Manual price removed for {ticker}")
    
    def get_all_prices(self) -> Dict[str, float]:
        """Get all manual price overrides."""
        self._ensure_initialized()
        return dict(st.session_state[self._session_key])
    
    def clear_all(self) -> None:
        """Clear all manual price overrides."""
        self._ensure_initialized()
        st.session_state[self._session_key] = {}
        logger.info("All manual prices cleared")
    
    def has_price(self, ticker: str) -> bool:
        """Check if a manual price exists for a ticker."""
        self._ensure_initialized()
        ticker = ticker.upper().strip()
        return ticker in st.session_state[self._session_key]


# Global instance with proper initialization
manual_pricing_service = ManualPricingService()


def get_manual_price(ticker: str) -> Optional[float]:
    """Get manual price override for a ticker."""
    return manual_pricing_service.get_price(ticker)


def set_manual_price(ticker: str, price: float) -> None:
    """Set manual price override for a ticker."""
    manual_pricing_service.set_price(ticker, price)
