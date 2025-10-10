"""
Portfolio management service - simplified for single portfolio.

This service provides portfolio operations for a single default portfolio.
Maintains backward compatibility while removing multi-portfolio complexity.
"""

from __future__ import annotations

import streamlit as st
from typing import List, Optional, Any
import pandas as pd

from core.portfolio_models import Portfolio, PortfolioRepository, get_current_portfolio_id
from infra.logging import get_logger

logger = get_logger(__name__)

# Default portfolio ID for single portfolio mode
DEFAULT_PORTFOLIO_ID = 1


class PortfolioService:
    """High-level service for portfolio management operations."""
    
    def __init__(self):
        self.repository = PortfolioRepository()
        self._ensure_default_portfolio_exists()
    
    def _ensure_default_portfolio_exists(self):
        """Ensure the default portfolio exists."""
        portfolio = self.repository.get_portfolio_by_id(DEFAULT_PORTFOLIO_ID)
        if not portfolio:
            # Create default portfolio
            default_portfolio = Portfolio(
                id=DEFAULT_PORTFOLIO_ID,
                name="My Portfolio",
                description="Primary investment portfolio",
                strategy_type="Micro-Cap Growth",
                benchmark_symbol="^RUT",
                is_active=True,
                is_default=True
            )
            self.repository.create_portfolio(default_portfolio)
            logger.info("Created default portfolio")
    
    def get_all_active_portfolios(self) -> List[Portfolio]:
        """Get all active portfolios - returns single default portfolio."""
        portfolio = self.get_current_portfolio()
        return [portfolio] if portfolio else []
    
    def get_current_portfolio(self) -> Optional[Portfolio]:
        """Get the current (default) portfolio."""
        return self.repository.get_portfolio_by_id(DEFAULT_PORTFOLIO_ID)
    
    def set_current_portfolio(self, portfolio_id: int) -> bool:
        """Set current portfolio - simplified to always use default."""
        # For backward compatibility, just return True
        return True
    
    def _reload_portfolio_session_data(self, portfolio_id: int) -> None:
        """Reload session state portfolio data for the specified portfolio."""
        try:
            import streamlit as st
            from data.portfolio import load_portfolio_for_id
            
            # Load portfolio-specific data
            portfolio_df, cash_balance = load_portfolio_for_id(portfolio_id)
            
            # Update session state
            st.session_state.portfolio = portfolio_df
            st.session_state.cash = cash_balance
            
        except Exception as e:
            logger.warning(f"Failed to reload portfolio data: {e}")
            # Fall back to clearing session state to force reload
            if hasattr(st, 'session_state'):
                for key in ['portfolio', 'cash']:
                    st.session_state.pop(key, None)
    
    def create_new_portfolio(
        self, 
        name: str, 
        description: str = "", 
        strategy_type: str = "Growth",
        benchmark_symbol: str = "^GSPC"
    ) -> Portfolio:
        """Create a new portfolio with the given parameters."""
        portfolio = Portfolio(
            id=0,  # Will be set by database
            name=name,
            description=description,
            strategy_type=strategy_type,
            benchmark_symbol=benchmark_symbol,
            is_active=True,
            is_default=False
        )
        
        created = self.repository.create_portfolio(portfolio)
        logger.info(f"Created new portfolio: {created.name}", extra={
            "portfolio_id": created.id,
            "strategy_type": strategy_type
        })
        return created
    
    def get_portfolio_options_for_ui(self) -> List[tuple[str, int]]:
        """Get portfolio options formatted for UI dropdowns."""
        portfolios = self.get_all_active_portfolios()
        return [(f"{p.name} ({p.strategy_type})", p.id) for p in portfolios]
    
    def get_portfolio_summary_for_ui(self, portfolio_id: int) -> dict[str, Any]:
        """Get portfolio summary formatted for UI display."""
        portfolio = self.repository.get_portfolio_by_id(portfolio_id)
        if not portfolio:
            return {}
        
        summary = self.repository.get_portfolio_summary(portfolio_id)
        
        return {
            "name": portfolio.name,
            "description": portfolio.description,
            "strategy_type": portfolio.strategy_type,
            "benchmark_symbol": portfolio.benchmark_symbol,
            "position_count": summary["position_count"],
            "cash_balance": summary["cash_balance"],
            "total_cost_basis": summary["total_cost_basis"],
            "trade_count": summary["trade_count"]
        }
    
    def _get_session_portfolio_id(self) -> int:
        """Get portfolio ID from session state, with fallback to default."""
        if hasattr(st, 'session_state') and hasattr(st.session_state, 'current_portfolio_id'):
            return st.session_state.current_portfolio_id
        
        # Fallback to default portfolio
        default = self.repository.get_default_portfolio()
        return default.id if default else 1
    
    def _set_session_portfolio_id(self, portfolio_id: int) -> None:
        """Set portfolio ID in session state."""
        if hasattr(st, 'session_state'):
            st.session_state.current_portfolio_id = portfolio_id


# Global service instance
portfolio_service = PortfolioService()


def get_current_portfolio_context() -> dict[str, Any]:
    """
    Get current portfolio context for use throughout the application.
    
    This provides a consistent way to get portfolio information that can be
    used in data queries, UI display, and logging.
    """
    current_portfolio = portfolio_service.get_current_portfolio()
    
    if not current_portfolio:
        # Fallback to default portfolio for safety
        default = portfolio_service.repository.get_default_portfolio()
        current_portfolio = default
    
    return {
        "portfolio_id": current_portfolio.id if current_portfolio else 1,
        "portfolio_name": current_portfolio.name if current_portfolio else "Default",
        "strategy_type": current_portfolio.strategy_type if current_portfolio else "Growth",
        "benchmark_symbol": current_portfolio.benchmark_symbol if current_portfolio else "^GSPC"
    }


def ensure_portfolio_context_in_queries() -> int:
    """
    Helper function to get the current portfolio ID for database queries.
    
    Simplified to always return DEFAULT_PORTFOLIO_ID for single portfolio mode.
    """
    return DEFAULT_PORTFOLIO_ID