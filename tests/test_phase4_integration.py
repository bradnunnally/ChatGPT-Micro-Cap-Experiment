"""
Integration Tests for Phase 4 Polish Features
Tests end-to-end functionality of enhanced summaries and data migration.
"""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch

from services.enhanced_summary import EnhancedSummaryService
from services.data_migration import DataMigrationService
from services.portfolio_service import PortfolioService
from core.portfolio_models import Portfolio


class TestPhase4Integration:
    """Integration tests for Phase 4 features."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.enhanced_summary_service = EnhancedSummaryService()
        
        # Create temporary database for migration service
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.temp_db.close()
        self.migration_service = DataMigrationService(db_path=self.temp_db.name)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        Path(self.temp_db.name).unlink(missing_ok=True)
    
    def test_enhanced_summary_with_all_strategy_types(self):
        """Test enhanced summary generation for all supported strategy types."""
        strategy_types = [
            "Micro-Cap Growth", "Small-Cap Value", "Growth", 
            "Value", "Income", "Balanced"
        ]
        
        for strategy_type in strategy_types:
            portfolio_info = {
                "id": 1,
                "name": f"Test {strategy_type} Portfolio",
                "strategy_type": strategy_type,
                "benchmark_symbol": "^GSPC"
            }
            
            # Test header generation
            header_lines = self.enhanced_summary_service.generate_enhanced_summary_header(
                portfolio_info, "2025-09-30"
            )
            
            assert len(header_lines) > 10
            assert any(f"Test {strategy_type} Portfolio" in line for line in header_lines)
            assert any("[ Your Instructions ]" in line for line in header_lines)
            
            # Test footer generation
            footer_lines = self.enhanced_summary_service.generate_enhanced_summary_footer(
                portfolio_info
            )
            
            assert len(footer_lines) > 5
            assert any("[ Strategy Reminders ]" in line for line in footer_lines)
    
    def test_end_to_end_portfolio_export_import(self):
        """Test complete export-import workflow."""
        # Mock portfolio service for export
        test_portfolio = Portfolio(
            id=1,
            name="Integration Test Portfolio",
            description="Test portfolio for integration testing",
            strategy_type="Growth",
            benchmark_symbol="^GSPC",
            created_date="2025-09-30"
        )
        
        mock_portfolio_service = Mock()
        mock_portfolio_service.get_portfolio.return_value = test_portfolio
        self.migration_service.portfolio_service = mock_portfolio_service
        
        # Setup database with test data
        self._setup_integration_test_database()
        
        # Export portfolio
        export_data = self.migration_service.export_portfolio(1, include_history=True)
        
        # Verify export data
        assert export_data.portfolio["name"] == "Integration Test Portfolio"
        assert export_data.portfolio["strategy_type"] == "Growth"
        assert len(export_data.holdings) > 0
        assert len(export_data.snapshots) > 0
        
        # Test enhanced summary with exported portfolio
        enhanced_summary = self.enhanced_summary_service.enhance_existing_summary(
            "Original summary content",
            export_data.portfolio
        )
        
        assert "Integration Test Portfolio" in enhanced_summary
        assert "GROWTH portfolio" in enhanced_summary
        assert "[ Your Instructions ]" in enhanced_summary
        assert "Original summary content" in enhanced_summary
    
    def test_export_import_with_enhanced_summary(self):
        """Test that imported portfolios work with enhanced summaries."""
        # Create export data with different strategy types
        export_data = {
            "portfolio": {
                "name": "Micro-Cap Growth Test",
                "description": "Test micro-cap portfolio",
                "strategy_type": "Micro-Cap Growth",
                "benchmark_symbol": "^RUT",
                "created_date": "2025-09-30",
                "is_active": True,
                "is_default": False
            },
            "holdings": [
                {
                    "ticker": "SMALL",
                    "shares": 1000,
                    "cost_per_share": 5.0,
                    "purchase_date": "2025-09-15"
                }
            ],
            "snapshots": [],
            "export_metadata": {
                "export_date": "2025-09-30T12:00:00",
                "portfolio_name": "Micro-Cap Growth Test",
                "include_history": False
            }
        }
        
        # Test enhanced summary with this portfolio
        enhanced_summary = self.enhanced_summary_service.enhance_existing_summary(
            "Test portfolio summary",
            export_data["portfolio"]
        )
        
        # Verify micro-cap specific content
        assert "Micro-Cap Growth Test" in enhanced_summary
        assert "companies < $300M market cap" in enhanced_summary
        assert "Russell 2000" in enhanced_summary
        assert "25-35%" in enhanced_summary
        assert "disruptive potential" in enhanced_summary
    
    def test_data_migration_preserves_strategy_context(self):
        """Test that data migration preserves strategy-specific context."""
        strategies_to_test = [
            ("Small-Cap Value", "undervalued", "P/E ratios"),
            ("Income", "dividend", "income generation"),
            ("Balanced", "diversified", "risk-adjusted")
        ]
        
        for strategy_type, keyword1, keyword2 in strategies_to_test:
            portfolio_data = {
                "name": f"Test {strategy_type}",
                "strategy_type": strategy_type,
                "benchmark_symbol": "^GSPC"
            }
            
            # Generate enhanced summary
            enhanced_summary = self.enhanced_summary_service.enhance_existing_summary(
                "Base summary content",
                portfolio_data
            )
            
            # Verify strategy-specific keywords are present
            assert keyword1.lower() in enhanced_summary.lower()
            assert keyword2.lower() in enhanced_summary.lower()
            assert f"{strategy_type.upper()} portfolio" in enhanced_summary
    
    def test_export_file_format_compatibility(self):
        """Test that exported files are compatible with import functionality."""
        # Mock portfolio for export
        test_portfolio = Portfolio(
            id=1,
            name="Compatibility Test",
            strategy_type="Value"
        )
        
        mock_portfolio_service = Mock()
        mock_portfolio_service.get_portfolio.return_value = test_portfolio
        self.migration_service.portfolio_service = mock_portfolio_service
        
        # Setup minimal database
        self._setup_integration_test_database()
        
        # Export to file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            success = self.migration_service.export_portfolio_to_file(1, temp_path)
            assert success is True
            
            # Verify file can be read and has correct structure
            with open(temp_path, 'r') as f:
                imported_data = json.load(f)
            
            required_keys = ["portfolio", "holdings", "snapshots", "export_metadata"]
            for key in required_keys:
                assert key in imported_data
            
            # Test import summary functionality
            summary = self.migration_service.get_import_summary(temp_path)
            assert summary is not None
            assert summary["portfolio_name"] == "Compatibility Test"
            assert summary["strategy_type"] == "Value"
        
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    def test_enhanced_summary_analytics_integration(self):
        """Test enhanced summary integration with analytics data."""
        portfolio_info = {
            "id": 1,
            "name": "Analytics Integration Test",
            "strategy_type": "Growth",
            "benchmark_symbol": "^GSPC"
        }
        
        analytics_data = {
            "volatility": "18.5",
            "sharpe_ratio": "1.42",
            "max_drawdown": "12.3"
        }
        
        enhanced_summary = self.enhanced_summary_service.enhance_existing_summary(
            "Base summary with analytics",
            portfolio_info,
            analytics_data
        )
        
        # Verify analytics data is included
        assert "Current Volatility: 18.5%" in enhanced_summary
        assert "Sharpe Ratio: 1.42" in enhanced_summary
        assert "Max Drawdown: 12.3%" in enhanced_summary
        assert "Target: 18-25%" in enhanced_summary  # Growth strategy target
    
    def _setup_integration_test_database(self):
        """Set up database with test data for integration tests."""
        import sqlite3
        
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
                    stop_type TEXT
                )
            """)
            
            conn.execute("""
                CREATE TABLE portfolio_snapshots (
                    id INTEGER PRIMARY KEY,
                    portfolio_id INTEGER,
                    date TEXT,
                    total_value REAL,
                    cash_balance REAL,
                    total_positions_value REAL
                )
            """)
            
            conn.execute("""
                CREATE TABLE cash_balances (
                    id INTEGER PRIMARY KEY,
                    portfolio_id INTEGER,
                    balance REAL,
                    last_updated TEXT
                )
            """)
            
            # Insert test data
            conn.execute("""
                INSERT INTO portfolios 
                (id, name, description, strategy_type, benchmark_symbol, created_date, is_active, is_default)
                VALUES (1, 'Integration Test Portfolio', 'Test Description', 'Growth', '^GSPC', '2025-09-30', 1, 0)
            """)
            
            conn.execute("""
                INSERT INTO positions 
                (portfolio_id, ticker, shares, cost_per_share, purchase_date)
                VALUES (1, 'TEST', 100, 50.0, '2025-09-01')
            """)
            
            conn.execute("""
                INSERT INTO portfolio_snapshots 
                (portfolio_id, date, total_value, cash_balance, total_positions_value)
                VALUES (1, '2025-09-30', 10000.0, 5000.0, 5000.0)
            """)
            
            conn.commit()