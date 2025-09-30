"""
Core portfolio management models and data access.

Provides the foundational models and data access patterns for multi-portfolio support.
Maintains backward compatibility by defaulting to portfolio_id=1 (the original portfolio).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Any

from data.db import get_connection


@dataclass
class Portfolio:
    """Represents a portfolio with its configuration and metadata."""
    
    id: int
    name: str
    description: str = ""
    strategy_type: str = "Growth"
    benchmark_symbol: str = "^GSPC"
    created_date: str = ""
    is_active: bool = True
    is_default: bool = False
    
    def __post_init__(self):
        if not self.created_date:
            self.created_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class PortfolioRepository:
    """Data access layer for portfolio management operations."""
    
    def __init__(self):
        pass
    
    def get_all_portfolios(self) -> List[Portfolio]:
        """Get all portfolios, ordered by default first, then by name."""
        with get_connection() as conn:
            cursor = conn.execute("""
                SELECT id, name, description, strategy_type, benchmark_symbol, 
                       created_date, is_active, is_default
                FROM portfolios 
                ORDER BY is_default DESC, name ASC
            """)
            
            portfolios = []
            for row in cursor.fetchall():
                portfolios.append(Portfolio(
                    id=row[0],
                    name=row[1],
                    description=row[2] or "",
                    strategy_type=row[3] or "Growth",
                    benchmark_symbol=row[4] or "^GSPC",
                    created_date=row[5] or "",
                    is_active=bool(row[6]),
                    is_default=bool(row[7])
                ))
            return portfolios
    
    def get_portfolio_by_id(self, portfolio_id: int) -> Optional[Portfolio]:
        """Get portfolio by ID."""
        with get_connection() as conn:
            cursor = conn.execute("""
                SELECT id, name, description, strategy_type, benchmark_symbol,
                       created_date, is_active, is_default
                FROM portfolios 
                WHERE id = ?
            """, (portfolio_id,))
            
            row = cursor.fetchone()
            if row:
                return Portfolio(
                    id=row[0],
                    name=row[1],
                    description=row[2] or "",
                    strategy_type=row[3] or "Growth", 
                    benchmark_symbol=row[4] or "^GSPC",
                    created_date=row[5] or "",
                    is_active=bool(row[6]),
                    is_default=bool(row[7])
                )
            return None
    
    def get_default_portfolio(self) -> Optional[Portfolio]:
        """Get the default portfolio (usually the original Micro-Cap one)."""
        with get_connection() as conn:
            cursor = conn.execute("""
                SELECT id, name, description, strategy_type, benchmark_symbol,
                       created_date, is_active, is_default
                FROM portfolios 
                WHERE is_default = 1
                LIMIT 1
            """)
            
            row = cursor.fetchone()
            if row:
                return Portfolio(
                    id=row[0],
                    name=row[1], 
                    description=row[2] or "",
                    strategy_type=row[3] or "Growth",
                    benchmark_symbol=row[4] or "^GSPC",
                    created_date=row[5] or "",
                    is_active=bool(row[6]),
                    is_default=bool(row[7])
                )
            
            # Fallback: if no default is set, return portfolio ID 1
            return self.get_portfolio_by_id(1)
    
    def create_portfolio(self, portfolio: Portfolio) -> Portfolio:
        """Create a new portfolio."""
        with get_connection() as conn:
            # If this is being set as default, unset others first
            if portfolio.is_default:
                conn.execute("UPDATE portfolios SET is_default = 0")
            
            cursor = conn.execute("""
                INSERT INTO portfolios 
                (name, description, strategy_type, benchmark_symbol, created_date, is_active, is_default)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                portfolio.name,
                portfolio.description,
                portfolio.strategy_type,
                portfolio.benchmark_symbol,
                portfolio.created_date,
                portfolio.is_active,
                portfolio.is_default
            ))
            
            portfolio.id = cursor.lastrowid
            conn.commit()
            return portfolio
    
    def update_portfolio(self, portfolio: Portfolio) -> Portfolio:
        """Update an existing portfolio."""
        with get_connection() as conn:
            # If this is being set as default, unset others first
            if portfolio.is_default:
                conn.execute("UPDATE portfolios SET is_default = 0 WHERE id != ?", (portfolio.id,))
            
            conn.execute("""
                UPDATE portfolios SET
                    name = ?, description = ?, strategy_type = ?, benchmark_symbol = ?,
                    is_active = ?, is_default = ?
                WHERE id = ?
            """, (
                portfolio.name,
                portfolio.description,
                portfolio.strategy_type,
                portfolio.benchmark_symbol,
                portfolio.is_active,
                portfolio.is_default,
                portfolio.id
            ))
            conn.commit()
            return portfolio
    
    def delete_portfolio(self, portfolio_id: int) -> bool:
        """
        Delete a portfolio and all its associated data.
        
        WARNING: This will permanently delete all trades, history, and positions
        for this portfolio. Use with caution.
        
        Returns True if deleted, False if portfolio doesn't exist or is default.
        """
        with get_connection() as conn:
            # Check if portfolio exists and is not default
            cursor = conn.execute("SELECT is_default FROM portfolios WHERE id = ?", (portfolio_id,))
            row = cursor.fetchone()
            
            if not row:
                return False  # Portfolio doesn't exist
                
            if row[0]:  # is_default is True
                return False  # Cannot delete default portfolio
            
            # Delete all associated data
            conn.execute("DELETE FROM portfolio WHERE portfolio_id = ?", (portfolio_id,))
            conn.execute("DELETE FROM cash WHERE portfolio_id = ?", (portfolio_id,))
            conn.execute("DELETE FROM trade_log WHERE portfolio_id = ?", (portfolio_id,))
            conn.execute("DELETE FROM portfolio_history WHERE portfolio_id = ?", (portfolio_id,))
            conn.execute("DELETE FROM portfolios WHERE id = ?", (portfolio_id,))
            
            conn.commit()
            return True
    
    def get_portfolio_summary(self, portfolio_id: int) -> dict[str, Any]:
        """Get summary statistics for a portfolio."""
        with get_connection() as conn:
            # Get position count and total value
            cursor = conn.execute("""
                SELECT COUNT(*) as position_count, 
                       COALESCE(SUM(shares * buy_price), 0) as total_cost_basis
                FROM portfolio 
                WHERE portfolio_id = ?
            """, (portfolio_id,))
            
            position_data = cursor.fetchone()
            
            # Get cash balance
            cursor = conn.execute("""
                SELECT balance FROM cash WHERE portfolio_id = ?
            """, (portfolio_id,))
            
            cash_row = cursor.fetchone()
            cash_balance = cash_row[0] if cash_row else 0.0
            
            # Get trade count
            cursor = conn.execute("""
                SELECT COUNT(*) FROM trade_log WHERE portfolio_id = ?
            """, (portfolio_id,))
            
            trade_count = cursor.fetchone()[0]
            
            return {
                "position_count": position_data[0] if position_data else 0,
                "total_cost_basis": position_data[1] if position_data else 0.0,
                "cash_balance": cash_balance,
                "trade_count": trade_count
            }


# Singleton instance for easy access
portfolio_repository = PortfolioRepository()


def get_current_portfolio_id() -> int:
    """
    Get the currently selected portfolio ID.
    
    For now, this defaults to 1 (the original portfolio) to maintain
    backward compatibility. In the future, this will check user session
    or configuration for the selected portfolio.
    """
    # TODO: Implement session-based portfolio selection
    # For now, maintain backward compatibility by defaulting to portfolio 1
    return 1


def set_current_portfolio_id(portfolio_id: int) -> None:
    """
    Set the currently selected portfolio ID.
    
    For now, this is a placeholder. In the future, this will store
    the selection in user session or configuration.
    """
    # TODO: Implement session-based portfolio selection
    # For now, this is a no-op to maintain backward compatibility
    pass