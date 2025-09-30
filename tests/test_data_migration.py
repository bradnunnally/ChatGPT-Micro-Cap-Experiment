"""
Tests for Data Migration Service
Tests portfolio import/export functionality.
"""

import pytest
import json
import tempfile
import sqlite3
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from services.data_migration import DataMigrationService, PortfolioExportData
from core.portfolio_models import Portfolio


class TestDataMigrationService:
    """Test cases for data migration service."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Create temporary database
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.temp_db.close()
        
        self.service = DataMigrationService(db_path=self.temp_db.name)
        self._setup_test_database()
        
        # Mock portfolio service
        self.mock_portfolio_service = Mock()
        self.service.portfolio_service = self.mock_portfolio_service
    
    def teardown_method(self):
        """Clean up test fixtures."""
        Path(self.temp_db.name).unlink(missing_ok=True)
    
    def _setup_test_database(self):
        """Set up test database with schema and sample data."""
        with sqlite3.connect(self.temp_db.name) as conn:
            # Create tables
            conn.execute("""
                CREATE TABLE portfolios (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    strategy_type TEXT,
                    benchmark_symbol TEXT,
                    created_date TEXT,
                    is_active BOOLEAN,
                    is_default BOOLEAN
                )
            """)
            
            conn.execute("""
                CREATE TABLE positions (
                    id INTEGER PRIMARY KEY,
                    portfolio_id INTEGER,
                    ticker TEXT,
                    shares REAL,
                    cost_per_share REAL,
                    purchase_date TEXT,
                    stop_loss_price REAL,
                    stop_type TEXT,
                    FOREIGN KEY (portfolio_id) REFERENCES portfolios (id)
                )
            """)
            
            conn.execute("""
                CREATE TABLE portfolio_snapshots (
                    id INTEGER PRIMARY KEY,
                    portfolio_id INTEGER,
                    date TEXT,
                    total_value REAL,
                    cash_balance REAL,
                    total_positions_value REAL,
                    FOREIGN KEY (portfolio_id) REFERENCES portfolios (id)
                )
            """)
            
            conn.execute("""
                CREATE TABLE cash_balances (
                    id INTEGER PRIMARY KEY,
                    portfolio_id INTEGER,
                    balance REAL,
                    last_updated TEXT,
                    FOREIGN KEY (portfolio_id) REFERENCES portfolios (id)
                )
            """)
            
            # Insert test data
            conn.execute("""
                INSERT INTO portfolios 
                (id, name, description, strategy_type, benchmark_symbol, created_date, is_active, is_default)
                VALUES (1, 'Test Portfolio', 'Test Description', 'Growth', '^GSPC', '2025-09-30', 1, 0)
            """)
            
            conn.execute("""
                INSERT INTO positions 
                (portfolio_id, ticker, shares, cost_per_share, purchase_date, stop_loss_price, stop_type)
                VALUES (1, 'AAPL', 100, 150.0, '2025-09-01', 140.0, 'fixed')
            """)
            
            conn.execute("""
                INSERT INTO positions 
                (portfolio_id, ticker, shares, cost_per_share, purchase_date, stop_loss_price, stop_type)
                VALUES (1, 'MSFT', 50, 300.0, '2025-09-02', 280.0, 'trailing')
            """)
            
            conn.execute("""
                INSERT INTO portfolio_snapshots 
                (portfolio_id, date, total_value, cash_balance, total_positions_value)
                VALUES (1, '2025-09-30', 30000.0, 5000.0, 25000.0)
            """)
            
            conn.commit()
    
    def test_export_portfolio_success(self):
        """Test successful portfolio export."""
        # Mock portfolio service
        test_portfolio = Portfolio(
            id=1, name="Test Portfolio", description="Test Description",
            strategy_type="Growth", benchmark_symbol="^GSPC",
            created_date="2025-09-30"
        )
        self.mock_portfolio_service.get_portfolio.return_value = test_portfolio
        
        # Export portfolio
        export_data = self.service.export_portfolio(1, include_history=True)
        
        assert isinstance(export_data, PortfolioExportData)
        assert export_data.portfolio["name"] == "Test Portfolio"
        assert len(export_data.holdings) == 2
        assert len(export_data.snapshots) == 1
        assert export_data.export_metadata["portfolio_id"] == 1
        assert export_data.export_metadata["include_history"] is True
    
    def test_export_portfolio_without_history(self):
        """Test portfolio export without historical data."""
        test_portfolio = Portfolio(
            id=1, name="Test Portfolio", strategy_type="Growth"
        )
        self.mock_portfolio_service.get_portfolio.return_value = test_portfolio
        
        export_data = self.service.export_portfolio(1, include_history=False)
        
        assert len(export_data.snapshots) == 0
        assert export_data.export_metadata["include_history"] is False
    
    def test_export_portfolio_not_found(self):
        """Test export of non-existent portfolio."""
        self.mock_portfolio_service.get_portfolio.return_value = None
        
        with pytest.raises(ValueError, match="Portfolio 999 not found"):
            self.service.export_portfolio(999)
    
    def test_export_portfolio_to_file(self):
        """Test exporting portfolio to JSON file."""
        test_portfolio = Portfolio(
            id=1, name="Test Portfolio", strategy_type="Growth"
        )
        self.mock_portfolio_service.get_portfolio.return_value = test_portfolio
        
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            success = self.service.export_portfolio_to_file(1, temp_path, include_history=True)
            
            assert success is True
            assert Path(temp_path).exists()
            
            # Verify file contents
            with open(temp_path, 'r') as f:
                data = json.load(f)
            
            assert "portfolio" in data
            assert "holdings" in data
            assert "snapshots" in data
            assert "export_metadata" in data
            assert data["portfolio"]["name"] == "Test Portfolio"
        
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    def test_import_portfolio_from_file(self):
        """Test importing portfolio from JSON file."""
        # Create test export data
        export_data = {
            "portfolio": {
                "name": "Imported Portfolio",
                "description": "Imported Description",
                "strategy_type": "Value",
                "benchmark_symbol": "^GSPC",
                "created_date": "2025-09-30",
                "is_active": True,
                "is_default": False
            },
            "holdings": [
                {
                    "ticker": "NVDA",
                    "shares": 25,
                    "cost_per_share": 400.0,
                    "purchase_date": "2025-09-15",
                    "stop_loss_price": 350.0,
                    "stop_type": "fixed"
                }
            ],
            "snapshots": [
                {
                    "date": "2025-09-30",
                    "total_value": 15000.0,
                    "cash_balance": 5000.0,
                    "total_positions_value": 10000.0
                }
            ],
            "export_metadata": {
                "export_date": "2025-09-30T12:00:00",
                "export_version": "1.0",
                "portfolio_id": 2,
                "portfolio_name": "Imported Portfolio",
                "include_history": True,
                "holdings_count": 1,
                "snapshots_count": 1
            }
        }
        
        # Mock portfolio service
        created_portfolio = Portfolio(
            id=2, name="Imported Portfolio", strategy_type="Value"
        )
        self.mock_portfolio_service.get_all_active_portfolios.return_value = []
        self.mock_portfolio_service.create_portfolio.return_value = created_portfolio
        
        # Write test data to file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            json.dump(export_data, temp_file)
            temp_path = temp_file.name
        
        try:
            # Import portfolio
            new_portfolio_id = self.service.import_portfolio_from_file(temp_path)
            
            assert new_portfolio_id == 2
            self.mock_portfolio_service.create_portfolio.assert_called_once()
        
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    def test_import_portfolio_name_conflict(self):
        """Test importing portfolio with existing name without overwrite."""
        export_data = {
            "portfolio": {"name": "Existing Portfolio"},
            "holdings": [],
            "export_metadata": {}
        }
        
        # Mock existing portfolio
        existing_portfolio = Portfolio(id=1, name="Existing Portfolio")
        self.mock_portfolio_service.get_all_active_portfolios.return_value = [existing_portfolio]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            json.dump(export_data, temp_file)
            temp_path = temp_file.name
        
        try:
            # Import should fail due to name conflict
            result = self.service.import_portfolio_from_file(temp_path, overwrite_existing=False)
            assert result is None
        
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    def test_get_portfolio_holdings(self):
        """Test getting portfolio holdings."""
        holdings = self.service._get_portfolio_holdings(1)
        
        assert len(holdings) == 2
        assert any(h["ticker"] == "AAPL" for h in holdings)
        assert any(h["ticker"] == "MSFT" for h in holdings)
    
    def test_get_portfolio_snapshots(self):
        """Test getting portfolio snapshots."""
        snapshots = self.service._get_portfolio_snapshots(1)
        
        assert len(snapshots) == 1
        assert snapshots[0]["total_value"] == 30000.0
    
    def test_get_import_summary(self):
        """Test getting import file summary."""
        export_data = {
            "portfolio": {
                "name": "Test Portfolio",
                "strategy_type": "Growth",
                "description": "Test Description"
            },
            "export_metadata": {
                "export_date": "2025-09-30T12:00:00",
                "holdings_count": 5,
                "snapshots_count": 10,
                "include_history": True
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            json.dump(export_data, temp_file)
            temp_path = temp_file.name
        
        try:
            summary = self.service.get_import_summary(temp_path)
            
            assert summary is not None
            assert summary["portfolio_name"] == "Test Portfolio"
            assert summary["strategy_type"] == "Growth"
            assert summary["holdings_count"] == 5
            assert summary["snapshots_count"] == 10
            assert summary["include_history"] is True
        
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    def test_export_all_portfolios(self):
        """Test exporting all portfolios."""
        portfolios = [
            Portfolio(id=1, name="Portfolio 1", strategy_type="Growth"),
            Portfolio(id=2, name="Portfolio 2", strategy_type="Value")
        ]
        self.mock_portfolio_service.get_all_active_portfolios.return_value = portfolios
        
        # Mock individual exports
        with patch.object(self.service, 'export_portfolio_to_file') as mock_export:
            mock_export.return_value = True
            
            with tempfile.TemporaryDirectory() as temp_dir:
                exported_files = self.service.export_all_portfolios(temp_dir)
                
                assert len(exported_files) == 2
                assert mock_export.call_count == 2