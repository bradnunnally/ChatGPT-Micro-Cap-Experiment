"""
Data Migration Tools for Portfolio Import/Export
Provides functionality to backup and restore portfolios with all associated data.
"""

import json
import sqlite3
import pandas as pd
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
import logging

from core.portfolio_models import Portfolio
from services.portfolio_service import PortfolioService


logger = logging.getLogger(__name__)


@dataclass
class PortfolioExportData:
    """Container for complete portfolio export data."""
    
    portfolio: Dict[str, Any]
    holdings: List[Dict[str, Any]]
    snapshots: List[Dict[str, Any]]
    export_metadata: Dict[str, Any]


class DataMigrationService:
    """Service for importing and exporting portfolio data."""
    
    def __init__(self, db_path: str = "data/trading.db"):
        self.db_path = db_path
        self.portfolio_service = PortfolioService()
    
    def export_portfolio(self, portfolio_id: int, include_history: bool = True) -> PortfolioExportData:
        """Export a complete portfolio with all associated data.
        
        Args:
            portfolio_id: ID of the portfolio to export
            include_history: Whether to include historical snapshots
            
        Returns:
            PortfolioExportData containing all portfolio information
        """
        
        logger.info(f"Starting export of portfolio {portfolio_id}")
        
        try:
            # Get portfolio information
            portfolio = self.portfolio_service.get_portfolio(portfolio_id)
            if not portfolio:
                raise ValueError(f"Portfolio {portfolio_id} not found")
            
            # Convert portfolio to dict
            portfolio_dict = asdict(portfolio)
            
            # Get current holdings
            holdings = self._get_portfolio_holdings(portfolio_id)
            
            # Get historical snapshots if requested
            snapshots = []
            if include_history:
                snapshots = self._get_portfolio_snapshots(portfolio_id)
            
            # Create export metadata
            export_metadata = {
                "export_date": datetime.now().isoformat(),
                "export_version": "1.0",
                "portfolio_id": portfolio_id,
                "portfolio_name": portfolio.name,
                "include_history": include_history,
                "holdings_count": len(holdings),
                "snapshots_count": len(snapshots)
            }
            
            export_data = PortfolioExportData(
                portfolio=portfolio_dict,
                holdings=holdings,
                snapshots=snapshots,
                export_metadata=export_metadata
            )
            
            logger.info(f"Successfully exported portfolio {portfolio_id} with {len(holdings)} holdings and {len(snapshots)} snapshots")
            return export_data
            
        except Exception as e:
            logger.error(f"Failed to export portfolio {portfolio_id}: {e}")
            raise
    
    def export_portfolio_to_file(self, portfolio_id: int, file_path: str, include_history: bool = True) -> bool:
        """Export portfolio to a JSON file.
        
        Args:
            portfolio_id: ID of the portfolio to export
            file_path: Path where to save the export file
            include_history: Whether to include historical snapshots
            
        Returns:
            True if export was successful, False otherwise
        """
        
        try:
            export_data = self.export_portfolio(portfolio_id, include_history)
            
            # Convert to JSON-serializable format
            export_dict = {
                "portfolio": export_data.portfolio,
                "holdings": export_data.holdings,
                "snapshots": export_data.snapshots,
                "export_metadata": export_data.export_metadata
            }
            
            # Ensure directory exists
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            
            # Write to file
            with open(file_path, 'w') as f:
                json.dump(export_dict, f, indent=2, default=str)
            
            logger.info(f"Portfolio {portfolio_id} exported to {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export portfolio {portfolio_id} to file {file_path}: {e}")
            return False
    
    def import_portfolio_from_file(self, file_path: str, overwrite_existing: bool = False) -> Optional[int]:
        """Import portfolio from a JSON file.
        
        Args:
            file_path: Path to the export file
            overwrite_existing: Whether to overwrite existing portfolio with same name
            
        Returns:
            ID of the imported portfolio, or None if import failed
        """
        
        try:
            # Read and validate file
            with open(file_path, 'r') as f:
                import_data = json.load(f)
            
            # Validate import data structure
            required_keys = ["portfolio", "holdings", "export_metadata"]
            for key in required_keys:
                if key not in import_data:
                    raise ValueError(f"Invalid import file: missing '{key}' section")
            
            portfolio_data = import_data["portfolio"]
            holdings_data = import_data["holdings"]
            snapshots_data = import_data.get("snapshots", [])
            metadata = import_data["export_metadata"]
            
            logger.info(f"Importing portfolio '{portfolio_data['name']}' with {len(holdings_data)} holdings")
            
            # Check for existing portfolio with same name
            existing_portfolios = self.portfolio_service.get_all_active_portfolios()
            existing_names = [p.name for p in existing_portfolios]
            
            if portfolio_data["name"] in existing_names and not overwrite_existing:
                raise ValueError(f"Portfolio '{portfolio_data['name']}' already exists. Use overwrite_existing=True to replace it.")
            
            # Remove or update conflicting portfolio
            if portfolio_data["name"] in existing_names and overwrite_existing:
                existing_portfolio = next(p for p in existing_portfolios if p.name == portfolio_data["name"])
                self._delete_portfolio_data(existing_portfolio.id)
                logger.info(f"Removed existing portfolio '{portfolio_data['name']}'")
            
            # Create portfolio in database (remove original ID to avoid conflicts)
            portfolio_data.pop("id", None)
            created_portfolio = self.portfolio_service.create_portfolio(
                name=portfolio_data.get("name"),
                description=portfolio_data.get("description", ""),
                strategy_type=portfolio_data.get("strategy_type", "Balanced"),
                benchmark_symbol=portfolio_data.get("benchmark_symbol", "^GSPC")
            )
            
            new_portfolio_id = created_portfolio.id
            
            # Import holdings
            if holdings_data:
                self._import_portfolio_holdings(new_portfolio_id, holdings_data)
            
            # Import historical snapshots
            if snapshots_data:
                self._import_portfolio_snapshots(new_portfolio_id, snapshots_data)
            
            logger.info(f"Successfully imported portfolio '{created_portfolio.name}' with ID {new_portfolio_id}")
            return new_portfolio_id
            
        except Exception as e:
            logger.error(f"Failed to import portfolio from {file_path}: {e}")
            return None
    
    def export_all_portfolios(self, export_dir: str, include_history: bool = True) -> List[str]:
        """Export all active portfolios to separate files.
        
        Args:
            export_dir: Directory where to save export files
            include_history: Whether to include historical snapshots
            
        Returns:
            List of exported file paths
        """
        
        exported_files = []
        
        try:
            portfolios = self.portfolio_service.get_all_active_portfolios()
            export_path = Path(export_dir)
            export_path.mkdir(parents=True, exist_ok=True)
            
            for portfolio in portfolios:
                # Create safe filename
                safe_name = "".join(c for c in portfolio.name if c.isalnum() or c in (' ', '-', '_')).rstrip()
                filename = f"{safe_name}_{portfolio.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                file_path = export_path / filename
                
                if self.export_portfolio_to_file(portfolio.id, str(file_path), include_history):
                    exported_files.append(str(file_path))
                    logger.info(f"Exported {portfolio.name} to {filename}")
                else:
                    logger.error(f"Failed to export portfolio {portfolio.name}")
            
            logger.info(f"Exported {len(exported_files)} portfolios to {export_dir}")
            return exported_files
            
        except Exception as e:
            logger.error(f"Failed to export all portfolios: {e}")
            return exported_files
    
    def _get_portfolio_holdings(self, portfolio_id: int) -> List[Dict[str, Any]]:
        """Get current holdings for a portfolio."""
        
        with sqlite3.connect(self.db_path) as conn:
            query = """
                SELECT ticker, shares, cost_per_share, purchase_date, stop_loss_price, stop_type
                FROM positions
                WHERE portfolio_id = ? AND shares > 0
            """
            
            cursor = conn.execute(query, (portfolio_id,))
            columns = [description[0] for description in cursor.description]
            
            holdings = []
            for row in cursor.fetchall():
                holding = dict(zip(columns, row))
                holdings.append(holding)
            
            return holdings
    
    def _get_portfolio_snapshots(self, portfolio_id: int) -> List[Dict[str, Any]]:
        """Get historical snapshots for a portfolio."""
        
        with sqlite3.connect(self.db_path) as conn:
            query = """
                SELECT date, total_value, cash_balance, total_positions_value
                FROM portfolio_snapshots
                WHERE portfolio_id = ?
                ORDER BY date
            """
            
            cursor = conn.execute(query, (portfolio_id,))
            columns = [description[0] for description in cursor.description]
            
            snapshots = []
            for row in cursor.fetchall():
                snapshot = dict(zip(columns, row))
                snapshots.append(snapshot)
            
            return snapshots
    
    def _import_portfolio_holdings(self, portfolio_id: int, holdings_data: List[Dict[str, Any]]) -> None:
        """Import holdings for a portfolio."""
        
        with sqlite3.connect(self.db_path) as conn:
            for holding in holdings_data:
                conn.execute("""
                    INSERT OR REPLACE INTO positions 
                    (portfolio_id, ticker, shares, cost_per_share, purchase_date, stop_loss_price, stop_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    portfolio_id,
                    holding.get("ticker"),
                    holding.get("shares"),
                    holding.get("cost_per_share"),
                    holding.get("purchase_date"),
                    holding.get("stop_loss_price"),
                    holding.get("stop_type")
                ))
            
            conn.commit()
    
    def _import_portfolio_snapshots(self, portfolio_id: int, snapshots_data: List[Dict[str, Any]]) -> None:
        """Import historical snapshots for a portfolio."""
        
        with sqlite3.connect(self.db_path) as conn:
            for snapshot in snapshots_data:
                conn.execute("""
                    INSERT OR REPLACE INTO portfolio_snapshots 
                    (portfolio_id, date, total_value, cash_balance, total_positions_value)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    portfolio_id,
                    snapshot.get("date"),
                    snapshot.get("total_value"),
                    snapshot.get("cash_balance"),
                    snapshot.get("total_positions_value")
                ))
            
            conn.commit()
    
    def _delete_portfolio_data(self, portfolio_id: int) -> None:
        """Delete all data for a portfolio."""
        
        with sqlite3.connect(self.db_path) as conn:
            # Delete in reverse dependency order
            conn.execute("DELETE FROM portfolio_snapshots WHERE portfolio_id = ?", (portfolio_id,))
            conn.execute("DELETE FROM positions WHERE portfolio_id = ?", (portfolio_id,))
            conn.execute("DELETE FROM cash_balances WHERE portfolio_id = ?", (portfolio_id,))
            conn.execute("DELETE FROM portfolios WHERE id = ?", (portfolio_id,))
            conn.commit()
    
    def get_import_summary(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Get summary information about an import file without importing.
        
        Args:
            file_path: Path to the export file
            
        Returns:
            Summary information about the import file
        """
        
        try:
            with open(file_path, 'r') as f:
                import_data = json.load(f)
            
            portfolio_data = import_data.get("portfolio", {})
            metadata = import_data.get("export_metadata", {})
            
            return {
                "portfolio_name": portfolio_data.get("name", "Unknown"),
                "strategy_type": portfolio_data.get("strategy_type", "Unknown"),
                "description": portfolio_data.get("description", ""),
                "export_date": metadata.get("export_date", "Unknown"),
                "holdings_count": metadata.get("holdings_count", 0),
                "snapshots_count": metadata.get("snapshots_count", 0),
                "include_history": metadata.get("include_history", False)
            }
            
        except Exception as e:
            logger.error(f"Failed to get import summary for {file_path}: {e}")
            return None