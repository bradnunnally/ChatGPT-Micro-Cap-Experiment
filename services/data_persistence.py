"""Database persistence service for portfolio operations.

This module provides centralized database operations for portfolio snapshots,
separating persistence logic from business logic.
"""

import logging
from typing import List, Tuple
import pandas as pd

from data.db import get_connection, init_db
from config import TODAY

logger = logging.getLogger(__name__)


class PortfolioPersistenceService:
    """Service for persisting portfolio data to the database."""
    
    def save_portfolio_snapshot(self, portfolio_df: pd.DataFrame, snapshot_df: pd.DataFrame, cash: float) -> None:
        """Save complete portfolio snapshot to database.
        
        Args:
            portfolio_df: Current portfolio positions
            snapshot_df: Computed snapshot with all calculated fields
            cash: Current cash balance
        """
        logger.debug(f"Saving portfolio snapshot with {len(portfolio_df)} positions and ${cash:.2f} cash")
        
        init_db()
        with get_connection() as conn:
            # Save all components in a transaction-like manner
            self._save_current_positions(conn, portfolio_df)
            self._save_cash_balance(conn, cash)
            self._save_daily_history(conn, snapshot_df)
            
        logger.info("Portfolio snapshot saved successfully")
    
    def _save_current_positions(self, conn, portfolio_df: pd.DataFrame) -> None:
        """Save current portfolio positions to the portfolio table.
        
        Args:
            conn: Database connection
            portfolio_df: DataFrame with current positions
        """
        # Get current portfolio ID from session context
        from services.portfolio_service import ensure_portfolio_context_in_queries
        current_portfolio_id = ensure_portfolio_context_in_queries()
        
        # Clear existing positions for current portfolio only
        conn.execute("DELETE FROM portfolio WHERE portfolio_id = ?", (current_portfolio_id,))
        
        if portfolio_df.empty:
            logger.debug("No positions to save")
            return
            
        # Prepare data for insertion
        core_columns = ["ticker", "shares", "stop_loss", "buy_price", "cost_basis"]
        available_columns = [col for col in core_columns if col in portfolio_df.columns]
        
        if not available_columns:
            logger.warning("No valid columns found in portfolio DataFrame")
            return
            
        # Convert DataFrame to insertion format
        insert_sql = "INSERT INTO portfolio (ticker, shares, stop_loss, buy_price, cost_basis, portfolio_id) VALUES (?, ?, ?, ?, ?, ?)"
        
        rows = self._prepare_portfolio_rows(portfolio_df, core_columns, current_portfolio_id)
        
        # Execute batch insert
        for row in rows:
            conn.execute(insert_sql, row)
            
        logger.debug(f"Saved {len(rows)} portfolio positions")
    
    def _prepare_portfolio_rows(self, portfolio_df: pd.DataFrame, core_columns: List[str], portfolio_id: int) -> List[Tuple]:
        """Prepare portfolio data for database insertion.
        
        Args:
            portfolio_df: Portfolio DataFrame
            core_columns: Required column names
            portfolio_id: ID of the portfolio to save to
            
        Returns:
            List of tuples ready for database insertion
        """
        try:
            return (
                portfolio_df.reindex(columns=core_columns)
                .fillna(0)
                .apply(
                    lambda r: (
                        r["ticker"],
                        float(r["shares"]),
                        float(r["stop_loss"]),
                        float(r["buy_price"]),
                        float(r["cost_basis"]),
                        portfolio_id,
                    ),
                    axis=1,
                )
                .tolist()
            )
        except Exception as e:
            logger.error(f"Error preparing portfolio rows: {e}")
            return []
    
    def _save_cash_balance(self, conn, cash: float) -> None:
        """Save cash balance to the cash table.
        
        Args:
            conn: Database connection
            cash: Cash balance
        """
        # Get current portfolio ID from session context
        from services.portfolio_service import ensure_portfolio_context_in_queries
        current_portfolio_id = ensure_portfolio_context_in_queries()
        
        conn.execute("INSERT OR REPLACE INTO cash (portfolio_id, balance) VALUES (?, ?)", (current_portfolio_id, float(cash)))
        logger.debug(f"Saved cash balance: ${cash:.2f} for portfolio {current_portfolio_id}")
    
    def _save_daily_history(self, conn, snapshot_df: pd.DataFrame) -> None:
        """Save daily portfolio history snapshot.
        
        Args:
            conn: Database connection
            snapshot_df: Computed snapshot DataFrame
        """
        # Clear existing data for today
        conn.execute("DELETE FROM portfolio_history WHERE date = ?", (TODAY,))
        
        try:
            # Try pandas to_sql first (works in normal operation)
            snapshot_df.to_sql("portfolio_history", conn, if_exists="append", index=False)
            logger.debug(f"Saved {len(snapshot_df)} history rows using pandas to_sql")
            
        except Exception as e:
            logger.warning(f"pandas to_sql failed, using manual insertion: {e}")
            self._manual_history_insert(conn, snapshot_df)
    
    def _manual_history_insert(self, conn, snapshot_df: pd.DataFrame) -> None:
        """Manually insert history data (fallback for mocked connections).
        
        Args:
            conn: Database connection
            snapshot_df: Snapshot DataFrame
        """
        insert_sql = (
            "INSERT INTO portfolio_history "
            "(date, ticker, shares, cost_basis, stop_loss, current_price, total_value, pnl, action, cash_balance, total_equity) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )
        
        rows_inserted = 0
        for _, row in snapshot_df.iterrows():
            try:
                conn.execute(
                    insert_sql,
                    (
                        row["date"],
                        row["ticker"],
                        float(row["shares"]) if row["shares"] != "" else 0.0,
                        float(row["cost_basis"]) if row["cost_basis"] != "" else 0.0,
                        float(row["stop_loss"]) if row["stop_loss"] != "" else 0.0,
                        float(row["current_price"]) if row["current_price"] != "" else 0.0,
                        float(row["total_value"]) if row["total_value"] != "" else 0.0,
                        float(row["pnl"]) if row["pnl"] != "" else 0.0,
                        row["action"],
                        float(row["cash_balance"]) if row["cash_balance"] != "" else 0.0,
                        float(row["total_equity"]) if row["total_equity"] != "" else 0.0,
                    ),
                )
                rows_inserted += 1
            except Exception as e:
                logger.error(f"Error inserting history row: {e}")
                
        logger.debug(f"Manually inserted {rows_inserted} history rows")


class DataTransformationService:
    """Service for transforming data between different formats."""
    
    @staticmethod
    def prepare_snapshot_input(portfolio_df: pd.DataFrame) -> pd.DataFrame:
        """Transform portfolio DataFrame to format expected by compute_snapshot.
        
        Args:
            portfolio_df: Raw portfolio DataFrame
            
        Returns:
            DataFrame with standardized column names
        """
        from config import COL_TICKER, COL_SHARES, COL_STOP, COL_PRICE, COL_COST
        
        return portfolio_df.rename(
            columns={
                COL_TICKER: "ticker",
                COL_SHARES: "shares",
                COL_STOP: "stop_loss",
                COL_PRICE: "buy_price",
                COL_COST: "cost_basis",
            }
        )
    
    @staticmethod
    def prepare_snapshot_output(snapshot_df: pd.DataFrame) -> pd.DataFrame:
        """Transform compute_snapshot output to standardized format.
        
        Args:
            snapshot_df: Raw snapshot from compute_snapshot
            
        Returns:
            DataFrame with lowercase column names for database/UI compatibility
        """
        return snapshot_df.rename(
            columns={
                "Date": "date",
                "Ticker": "ticker",
                "Shares": "shares",
                "Cost Basis": "cost_basis",
                "Stop Loss": "stop_loss",
                "Current Price": "current_price",
                "Total Value": "total_value",
                "PnL": "pnl",
                "Action": "action",
                "Price Source": "price_source",
                "Cash Balance": "cash_balance",
                "Total Equity": "total_equity",
            }
        )
    
    @staticmethod
    def prepare_database_subset(snapshot_df: pd.DataFrame) -> pd.DataFrame:
        """Extract columns needed for database storage.
        
        Args:
            snapshot_df: Complete snapshot DataFrame
            
        Returns:
            DataFrame with only database-required columns
        """
        db_columns = [
            "date",
            "ticker", 
            "shares",
            "cost_basis",
            "stop_loss",
            "current_price",
            "total_value",
            "pnl",
            "action",
            "cash_balance",
            "total_equity",
        ]
        
        return snapshot_df[db_columns]


# Global service instances
_persistence_service = PortfolioPersistenceService()
_transformation_service = DataTransformationService()


def save_portfolio_data(portfolio_df: pd.DataFrame, snapshot_df: pd.DataFrame, cash: float) -> None:
    """Convenience function to save portfolio data using global service.
    
    Args:
        portfolio_df: Current portfolio positions
        snapshot_df: Computed snapshot
        cash: Cash balance
    """
    _persistence_service.save_portfolio_snapshot(portfolio_df, snapshot_df, cash)


def transform_for_snapshot_input(portfolio_df: pd.DataFrame) -> pd.DataFrame:
    """Convenience function for input transformation."""
    return _transformation_service.prepare_snapshot_input(portfolio_df)


def transform_snapshot_output(snapshot_df: pd.DataFrame) -> pd.DataFrame:
    """Convenience function for output transformation.""" 
    return _transformation_service.prepare_snapshot_output(snapshot_df)