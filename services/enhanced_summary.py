"""
Enhanced Daily Summary Service with Portfolio-Specific Instructions
Provides ChatGPT-tailored summaries based on portfolio strategy and context.
"""

from dataclasses import dataclass
from typing import Dict, Any, List
from datetime import datetime


@dataclass
class PortfolioInstructions:
    """Portfolio-specific instructions and context for ChatGPT summaries."""
    
    strategy_description: str
    risk_tolerance: str
    focus_areas: List[str]
    benchmark_context: str
    decision_guidance: str
    volatility_target: str
    key_metrics: List[str]


class EnhancedSummaryService:
    """Service for generating enhanced daily summaries with portfolio-specific instructions."""
    
    def __init__(self):
        self.strategy_instructions = {
            "Micro-Cap Growth": PortfolioInstructions(
                strategy_description="Aggressive micro-cap growth focused on companies < $300M market cap",
                risk_tolerance="High (target volatility 25-35%)",
                focus_areas=[
                    "Small companies with disruptive potential",
                    "Higher volatility tolerance (25-35% expected)",
                    "Growth over dividends",
                    "Quick position sizing adjustments based on momentum"
                ],
                benchmark_context="Russell 2000 (^RUT) vs S&P 500 (^GSPC)",
                decision_guidance="Focus on rapid growth potential and market disruption opportunities. Be prepared for high volatility and quick position adjustments.",
                volatility_target="25-35%",
                key_metrics=["Revenue Growth", "Market Cap", "Volatility", "Beta"]
            ),
            "Small-Cap Value": PortfolioInstructions(
                strategy_description="Value-oriented investing in undervalued small-cap companies < $2B market cap",
                risk_tolerance="Moderate-High (target volatility 20-28%)", 
                focus_areas=[
                    "Undervalued companies with strong fundamentals",
                    "P/E ratios below sector averages",
                    "Strong balance sheets and cash flow",
                    "Contrarian investment opportunities"
                ],
                benchmark_context="Russell 2000 Value (^RUJ) vs S&P 500 (^GSPC)",
                decision_guidance="Look for undervalued opportunities with strong fundamentals. Focus on companies trading below intrinsic value with solid financials.",
                volatility_target="20-28%",
                key_metrics=["P/E Ratio", "P/B Ratio", "Debt-to-Equity", "Free Cash Flow"]
            ),
            "Growth": PortfolioInstructions(
                strategy_description="Growth-focused investing in companies with above-average growth potential",
                risk_tolerance="Moderate-High (target volatility 18-25%)",
                focus_areas=[
                    "Revenue and earnings growth acceleration",
                    "Market leadership and competitive advantages",
                    "Innovation and market expansion",
                    "Long-term growth sustainability"
                ],
                benchmark_context="S&P 500 Growth (^SP500GR) vs S&P 500 (^GSPC)",
                decision_guidance="Prioritize companies with sustainable competitive advantages and strong growth trajectories. Focus on long-term value creation.",
                volatility_target="18-25%",
                key_metrics=["Revenue Growth", "EPS Growth", "ROE", "Market Share"]
            ),
            "Value": PortfolioInstructions(
                strategy_description="Value investing in undervalued companies with strong fundamentals",
                risk_tolerance="Moderate (target volatility 15-22%)",
                focus_areas=[
                    "Undervalued stocks with strong fundamentals",
                    "Dividend-paying companies",
                    "Companies trading below book value",
                    "Defensive characteristics during market downturns"
                ],
                benchmark_context="S&P 500 Value (^SP500VL) vs S&P 500 (^GSPC)",
                decision_guidance="Focus on undervalued opportunities with strong dividend yields and defensive characteristics. Look for margin of safety in purchases.",
                volatility_target="15-22%",
                key_metrics=["P/E Ratio", "Dividend Yield", "P/B Ratio", "ROE"]
            ),
            "Income": PortfolioInstructions(
                strategy_description="Income-focused investing in dividend-paying stocks and income-generating assets",
                risk_tolerance="Low-Moderate (target volatility 12-18%)",
                focus_areas=[
                    "High dividend yields and consistent payouts",
                    "Dividend growth sustainability",
                    "Stable cash flows and earnings",
                    "Capital preservation with income generation"
                ],
                benchmark_context="Dividend Aristocrats vs S&P 500 (^GSPC)",
                decision_guidance="Prioritize consistent dividend income and capital preservation. Focus on companies with long dividend payment histories.",
                volatility_target="12-18%",
                key_metrics=["Dividend Yield", "Dividend Growth", "Payout Ratio", "Cash Flow"]
            ),
            "Balanced": PortfolioInstructions(
                strategy_description="Balanced approach combining growth and value strategies",
                risk_tolerance="Moderate (target volatility 15-20%)",
                focus_areas=[
                    "Diversified mix of growth and value stocks",
                    "Risk-adjusted returns optimization",
                    "Sector and style diversification",
                    "Moderate risk with steady growth"
                ],
                benchmark_context="S&P 500 (^GSPC) with sector diversification",
                decision_guidance="Maintain balanced exposure across growth and value. Focus on risk-adjusted returns and portfolio diversification.",
                volatility_target="15-20%",
                key_metrics=["Sharpe Ratio", "Beta", "Sector Allocation", "Risk-Adjusted Returns"]
            )
        }
    
    def generate_enhanced_summary_header(self, portfolio_info: Dict[str, Any], date_str: str) -> List[str]:
        """Generate enhanced summary header with portfolio-specific instructions."""
        
        lines = []
        portfolio_name = portfolio_info.get("name", "Unknown Portfolio")
        strategy_type = portfolio_info.get("strategy_type", "Balanced")
        benchmark_symbol = portfolio_info.get("benchmark_symbol", "^GSPC")
        
        # Get strategy instructions
        instructions = self.strategy_instructions.get(strategy_type, self.strategy_instructions["Balanced"])
        
        # Header section
        lines.append("=" * 64)
        lines.append(f"Daily Results — {portfolio_name} — {date_str}")
        lines.append("=" * 64)
        lines.append("")
        
        # Portfolio strategy context
        lines.append(f"Portfolio Strategy: {instructions.strategy_description}")
        lines.append(f"Benchmark: {instructions.benchmark_context}")
        lines.append(f"Risk Tolerance: {instructions.risk_tolerance}")
        lines.append("")
        
        # ChatGPT Instructions section
        lines.append("[ Your Instructions ]")
        lines.append(f"This is your {strategy_type.upper()} portfolio. Your strategy emphasizes:")
        
        for focus_area in instructions.focus_areas:
            lines.append(f"- {focus_area}")
        
        lines.append("")
        lines.append(f"Decision Guidance: {instructions.decision_guidance}")
        lines.append("")
        lines.append(f"Key Metrics to Monitor: {', '.join(instructions.key_metrics)}")
        lines.append("")
        
        return lines
    
    def generate_enhanced_summary_footer(self, portfolio_info: Dict[str, Any], analytics_data: Dict[str, Any] = None) -> List[str]:
        """Generate enhanced summary footer with portfolio-specific context."""
        
        lines = []
        strategy_type = portfolio_info.get("strategy_type", "Balanced")
        instructions = self.strategy_instructions.get(strategy_type, self.strategy_instructions["Balanced"])
        
        lines.append("[ Strategy Reminders ]")
        lines.append(f"• Target Volatility: {instructions.volatility_target}")
        lines.append(f"• Risk Tolerance: {instructions.risk_tolerance}")
        lines.append(f"• Primary Focus: {instructions.strategy_description}")
        
        if analytics_data:
            current_volatility = analytics_data.get("volatility", "N/A")
            sharpe_ratio = analytics_data.get("sharpe_ratio", "N/A")
            max_drawdown = analytics_data.get("max_drawdown", "N/A")
            
            lines.append("")
            lines.append("[ Current Performance vs Strategy ]")
            lines.append(f"• Current Volatility: {current_volatility}% (Target: {instructions.volatility_target})")
            lines.append(f"• Sharpe Ratio: {sharpe_ratio}")
            lines.append(f"• Max Drawdown: {max_drawdown}%")
        
        lines.append("")
        lines.append("=" * 64)
        
        return lines
    
    def enhance_existing_summary(self, original_summary: str, portfolio_info: Dict[str, Any], analytics_data: Dict[str, Any] = None) -> str:
        """Enhance an existing summary with portfolio-specific instructions."""
        
        date_str = datetime.now().strftime("%Y-%m-%d")
        
        # Generate enhanced header
        header_lines = self.generate_enhanced_summary_header(portfolio_info, date_str)
        
        # Generate enhanced footer
        footer_lines = self.generate_enhanced_summary_footer(portfolio_info, analytics_data)
        
        # Combine all sections
        enhanced_summary = "\n".join(header_lines) + "\n" + original_summary + "\n" + "\n".join(footer_lines)
        
        return enhanced_summary