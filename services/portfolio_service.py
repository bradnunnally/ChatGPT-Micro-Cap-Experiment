"""
Portfolio management service for multi-portfolio operations.

This service provides high-level operations for managing multiple portfolios
while maintaining backward compatibility with existing single-portfolio code.
"""

from __future__ import annotations

import streamlit as st
from typing import List, Optional, Any
import pandas as pd

from core.portfolio_models import Portfolio, PortfolioRepository, get_current_portfolio_id
from infra.logging import get_logger

logger = get_logger(__name__)


class PortfolioService:
    """High-level service for portfolio management operations."""
    
    def __init__(self):
        self.repository = PortfolioRepository()
    
    def get_all_active_portfolios(self) -> List[Portfolio]:
        """Get all active portfolios for selection."""
        portfolios = self.repository.get_all_portfolios()
        return [p for p in portfolios if p.is_active]
    
    def get_current_portfolio(self) -> Optional[Portfolio]:
        """Get the currently selected portfolio."""
        # For backward compatibility, check session state first, then default
        current_id = self._get_session_portfolio_id()
        return self.repository.get_portfolio_by_id(current_id)
    
    def set_current_portfolio(self, portfolio_id: int) -> bool:
        """Set the currently selected portfolio."""
        portfolio = self.repository.get_portfolio_by_id(portfolio_id)
        if portfolio and portfolio.is_active:
            self._set_session_portfolio_id(portfolio_id)
            logger.info(f"Switched to portfolio: {portfolio.name}", extra={
                "portfolio_id": portfolio_id,
                "portfolio_name": portfolio.name
            })
            return True
        return False
    
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
    
    This maintains backward compatibility by defaulting to portfolio ID 1
    while enabling multi-portfolio support when ready.
    """
    context = get_current_portfolio_context()
    return context["portfolio_id"]