"""
Tests for Enhanced Summary Service
Tests portfolio-specific summary generation with ChatGPT instructions.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from services.enhanced_summary import EnhancedSummaryService, PortfolioInstructions


class TestEnhancedSummaryService:
    """Test cases for enhanced summary service."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.service = EnhancedSummaryService()
        self.sample_portfolio_info = {
            "id": 1,
            "name": "Test Growth Portfolio",
            "strategy_type": "Growth",
            "benchmark_symbol": "^GSPC",
            "description": "Test portfolio for growth strategy"
        }
    
    def test_init_creates_strategy_instructions(self):
        """Test that service initializes with strategy instructions."""
        assert len(self.service.strategy_instructions) >= 6
        assert "Growth" in self.service.strategy_instructions
        assert "Value" in self.service.strategy_instructions
        assert "Micro-Cap Growth" in self.service.strategy_instructions
    
    def test_strategy_instructions_structure(self):
        """Test that strategy instructions have proper structure."""
        growth_instructions = self.service.strategy_instructions["Growth"]
        
        assert isinstance(growth_instructions, PortfolioInstructions)
        assert growth_instructions.strategy_description
        assert growth_instructions.risk_tolerance
        assert isinstance(growth_instructions.focus_areas, list)
        assert len(growth_instructions.focus_areas) > 0
        assert growth_instructions.benchmark_context
        assert growth_instructions.decision_guidance
        assert growth_instructions.volatility_target
        assert isinstance(growth_instructions.key_metrics, list)
    
    def test_generate_enhanced_summary_header(self):
        """Test enhanced summary header generation."""
        date_str = "2025-09-30"
        
        header_lines = self.service.generate_enhanced_summary_header(
            self.sample_portfolio_info, date_str
        )
        
        assert len(header_lines) > 10
        assert any("Daily Results — Test Growth Portfolio — 2025-09-30" in line for line in header_lines)
        assert any("Portfolio Strategy:" in line for line in header_lines)
        assert any("[ Your Instructions ]" in line for line in header_lines)
        assert any("GROWTH portfolio" in line for line in header_lines)
    
    def test_generate_enhanced_summary_footer(self):
        """Test enhanced summary footer generation."""
        analytics_data = {
            "volatility": "22.5",
            "sharpe_ratio": "1.25",
            "max_drawdown": "8.3"
        }
        
        footer_lines = self.service.generate_enhanced_summary_footer(
            self.sample_portfolio_info, analytics_data
        )
        
        assert len(footer_lines) > 5
        assert any("[ Strategy Reminders ]" in line for line in footer_lines)
        assert any("Target Volatility:" in line for line in footer_lines)
        assert any("[ Current Performance vs Strategy ]" in line for line in footer_lines)
        assert any("Current Volatility: 22.5%" in line for line in footer_lines)
    
    def test_enhance_existing_summary(self):
        """Test enhancement of existing summary."""
        original_summary = """
[ Holdings ]
AAPL: 100 shares at $150.00
MSFT: 50 shares at $300.00

[ Total Value ]
Portfolio Value: $30,000
        """
        
        enhanced = self.service.enhance_existing_summary(
            original_summary, self.sample_portfolio_info
        )
        
        assert "Daily Results — Test Growth Portfolio" in enhanced
        assert "[ Your Instructions ]" in enhanced
        assert "GROWTH portfolio" in enhanced
        assert "[ Holdings ]" in enhanced  # Original content preserved
        assert "[ Strategy Reminders ]" in enhanced
    
    def test_micro_cap_growth_strategy_specifics(self):
        """Test Micro-Cap Growth strategy specific instructions."""
        micro_cap_portfolio = {
            "id": 2,
            "name": "Micro-Cap Growth",
            "strategy_type": "Micro-Cap Growth",
            "benchmark_symbol": "^RUT"
        }
        
        header_lines = self.service.generate_enhanced_summary_header(
            micro_cap_portfolio, "2025-09-30"
        )
        
        header_text = "\n".join(header_lines)
        assert "companies < $300M market cap" in header_text
        assert "Russell 2000" in header_text
        assert "25-35%" in header_text
        assert "disruptive potential" in header_text
    
    def test_small_cap_value_strategy_specifics(self):
        """Test Small-Cap Value strategy specific instructions."""
        value_portfolio = {
            "id": 3,
            "name": "Small-Cap Value",
            "strategy_type": "Small-Cap Value",
            "benchmark_symbol": "^RUJ"
        }
        
        header_lines = self.service.generate_enhanced_summary_header(
            value_portfolio, "2025-09-30"
        )
        
        header_text = "\n".join(header_lines)
        assert "undervalued" in header_text.lower()
        assert "P/E ratios" in header_text
        assert "Russell 2000 Value" in header_text
        assert "fundamentals" in header_text.lower()
    
    def test_balanced_strategy_fallback(self):
        """Test fallback to Balanced strategy for unknown strategies."""
        unknown_portfolio = {
            "id": 4,
            "name": "Unknown Strategy",
            "strategy_type": "Unknown Strategy",
            "benchmark_symbol": "^GSPC"
        }
        
        header_lines = self.service.generate_enhanced_summary_header(
            unknown_portfolio, "2025-09-30"
        )
        
        header_text = "\n".join(header_lines)
        assert "Balanced approach" in header_text
        assert "diversified mix" in header_text.lower()
    
    def test_footer_without_analytics_data(self):
        """Test footer generation without analytics data."""
        footer_lines = self.service.generate_enhanced_summary_footer(
            self.sample_portfolio_info
        )
        
        footer_text = "\n".join(footer_lines)
        assert "[ Strategy Reminders ]" in footer_text
        assert "[ Current Performance vs Strategy ]" not in footer_text
    
    def test_all_strategy_types_have_instructions(self):
        """Test that all supported strategy types have complete instructions."""
        strategy_types = [
            "Micro-Cap Growth", "Small-Cap Value", "Growth", 
            "Value", "Income", "Balanced"
        ]
        
        for strategy_type in strategy_types:
            assert strategy_type in self.service.strategy_instructions
            
            instructions = self.service.strategy_instructions[strategy_type]
            assert instructions.strategy_description
            assert instructions.risk_tolerance
            assert len(instructions.focus_areas) > 0
            assert instructions.benchmark_context
            assert instructions.decision_guidance
            assert instructions.volatility_target
            assert len(instructions.key_metrics) > 0