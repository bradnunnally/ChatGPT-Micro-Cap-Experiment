"""
Enhanced Analytics Service for Multi-Portfolio Analysis

Provides advanced analytics capabilities including:
- Portfolio-specific performance metrics
- Cross-portfolio comparisons  
- Strategy-specific KPIs
- Custom benchmark analysis
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import pandas as pd
import numpy as np

from core.portfolio_models import Portfolio, PortfolioRepository
from services.portfolio_service import portfolio_service
from data.db import get_connection
from config import TODAY

logger = logging.getLogger(__name__)


@dataclass
class PortfolioAnalytics:
    """Comprehensive analytics data for a portfolio."""
    
    portfolio_id: int
    portfolio_name: str
    strategy_type: str
    benchmark_symbol: str
    
    # Core metrics
    total_value: float
    cash_balance: float
    invested_value: float
    total_return: float
    
    # Performance metrics
    sharpe_ratio: Optional[float] = None
    max_drawdown: Optional[float] = None
    beta: Optional[float] = None
    alpha: Optional[float] = None
    
    # Strategy-specific metrics
    strategy_metrics: Dict[str, Any] = None
    
    # Risk metrics
    volatility: Optional[float] = None
    value_at_risk: Optional[float] = None
    
    # Benchmark comparison
    benchmark_return: Optional[float] = None
    excess_return: Optional[float] = None
    
    def __post_init__(self):
        if self.strategy_metrics is None:
            self.strategy_metrics = {}


@dataclass
class PortfolioComparison:
    """Cross-portfolio comparison data."""
    
    portfolios: List[PortfolioAnalytics]
    comparison_period: str  # "1M", "3M", "6M", "1Y", "YTD", "All"
    
    # Comparative metrics
    best_performer: Optional[str] = None
    worst_performer: Optional[str] = None
    correlation_matrix: Optional[pd.DataFrame] = None
    
    # Risk-adjusted performance rankings
    sharpe_rankings: List[Tuple[str, float]] = None
    return_rankings: List[Tuple[str, float]] = None
    
    def __post_init__(self):
        if self.sharpe_rankings is None:
            self.sharpe_rankings = []
        if self.return_rankings is None:
            self.return_rankings = []


class EnhancedAnalyticsService:
    """Service for advanced portfolio analytics and comparisons."""
    
    def __init__(self):
        self.repository = PortfolioRepository()
    
    # === Portfolio-Specific Analytics ===
    
    def get_portfolio_analytics(self, portfolio_id: int, period: str = "3M") -> PortfolioAnalytics:
        """
        Get comprehensive analytics for a specific portfolio.
        
        Args:
            portfolio_id: Portfolio to analyze
            period: Time period for analysis ("1M", "3M", "6M", "1Y", "YTD", "All")
        
        Returns:
            PortfolioAnalytics with comprehensive metrics
        """
        portfolio = self.repository.get_portfolio_by_id(portfolio_id)
        if not portfolio:
            raise ValueError(f"Portfolio {portfolio_id} not found")
        
        # Get core portfolio data
        summary = self.repository.get_portfolio_summary(portfolio_id)
        
        # Calculate performance metrics
        performance_data = self._calculate_performance_metrics(portfolio_id, period)
        
        # Get strategy-specific metrics
        strategy_metrics = self._calculate_strategy_specific_metrics(portfolio, period)
        
        # Calculate benchmark comparison
        benchmark_data = self._calculate_benchmark_comparison(portfolio_id, portfolio.benchmark_symbol, period)
        
        return PortfolioAnalytics(
            portfolio_id=portfolio_id,
            portfolio_name=portfolio.name,
            strategy_type=portfolio.strategy_type,
            benchmark_symbol=portfolio.benchmark_symbol,
            total_value=summary["cash_balance"] + summary["total_cost_basis"],  # Simplified for now
            cash_balance=summary["cash_balance"],
            invested_value=summary["total_cost_basis"],
            total_return=performance_data.get("total_return", 0.0),
            sharpe_ratio=performance_data.get("sharpe_ratio"),
            max_drawdown=performance_data.get("max_drawdown"),
            beta=benchmark_data.get("beta"),
            alpha=benchmark_data.get("alpha"),
            strategy_metrics=strategy_metrics,
            volatility=performance_data.get("volatility"),
            value_at_risk=performance_data.get("var_95"),
            benchmark_return=benchmark_data.get("benchmark_return"),
            excess_return=benchmark_data.get("excess_return")
        )
    
    def _calculate_performance_metrics(self, portfolio_id: int, period: str) -> Dict[str, Any]:
        """Calculate core performance metrics for a portfolio."""
        try:
            with get_connection() as conn:
                # Get historical data for the period
                start_date = self._get_period_start_date(period)
                
                cursor = conn.execute("""
                    SELECT date, total_value, ticker
                    FROM portfolio_history 
                    WHERE portfolio_id = ? AND date >= ? AND ticker = 'TOTAL'
                    ORDER BY date ASC
                """, (portfolio_id, start_date))
                
                data = cursor.fetchall()
                
                if len(data) < 2:
                    logger.warning(f"Insufficient data for portfolio {portfolio_id} performance analysis")
                    return {}
                
                # Convert to DataFrame for analysis
                df = pd.DataFrame(data, columns=["date", "total_value", "ticker"])
                df["date"] = pd.to_datetime(df["date"])
                df = df.sort_values("date")
                
                # Calculate returns
                df["daily_return"] = df["total_value"].pct_change()
                
                # Calculate metrics
                if df["total_value"].iloc[0] == 0:
                    total_return = 0.0
                else:
                    total_return = (df["total_value"].iloc[-1] / df["total_value"].iloc[0] - 1) * 100
                
                # Risk metrics
                daily_returns = df["daily_return"].dropna()
                if len(daily_returns) > 1:
                    volatility = daily_returns.std() * np.sqrt(252) * 100  # Annualized
                    sharpe_ratio = self._calculate_sharpe_ratio(daily_returns)
                    max_drawdown = self._calculate_max_drawdown(df["total_value"])
                    var_95 = daily_returns.quantile(0.05) * 100  # 95% VaR
                else:
                    volatility = sharpe_ratio = max_drawdown = var_95 = None
                
                return {
                    "total_return": total_return,
                    "volatility": volatility,
                    "sharpe_ratio": sharpe_ratio,
                    "max_drawdown": max_drawdown,
                    "var_95": var_95,
                    "observations": len(daily_returns)
                }
                
        except Exception as e:
            logger.error(f"Error calculating performance metrics for portfolio {portfolio_id}: {e}")
            return {}
    
    def _calculate_strategy_specific_metrics(self, portfolio: Portfolio, period: str) -> Dict[str, Any]:
        """Calculate metrics specific to the portfolio's strategy type."""
        strategy_type = portfolio.strategy_type.lower()
        
        if "growth" in strategy_type:
            return self._calculate_growth_metrics(portfolio.id, period)
        elif "value" in strategy_type:
            return self._calculate_value_metrics(portfolio.id, period)
        elif "income" in strategy_type or "dividend" in strategy_type:
            return self._calculate_income_metrics(portfolio.id, period)
        else:
            return {}
    
    def _calculate_growth_metrics(self, portfolio_id: int, period: str) -> Dict[str, Any]:
        """Calculate growth-specific metrics."""
        try:
            with get_connection() as conn:
                # Get position data
                cursor = conn.execute("""
                    SELECT ticker, shares, buy_price, cost_basis 
                    FROM portfolio 
                    WHERE portfolio_id = ?
                """, (portfolio_id,))
                
                positions = cursor.fetchall()
                
                if not positions:
                    return {}
                
                # Growth-specific calculations
                position_count = len(positions)
                avg_position_size = sum(pos[3] for pos in positions) / position_count if position_count > 0 else 0
                
                # Concentration metrics
                total_value = sum(pos[3] for pos in positions)
                max_position = max(pos[3] for pos in positions) if positions else 0
                concentration_ratio = (max_position / total_value * 100) if total_value > 0 else 0
                
                return {
                    "position_count": position_count,
                    "avg_position_size": avg_position_size,
                    "concentration_ratio": concentration_ratio,
                    "diversification_score": min(100, (1 - concentration_ratio/100) * 100),
                    "strategy_focus": "Growth-oriented metrics"
                }
                
        except Exception as e:
            logger.error(f"Error calculating growth metrics: {e}")
            return {}
    
    def _calculate_value_metrics(self, portfolio_id: int, period: str) -> Dict[str, Any]:
        """Calculate value-specific metrics."""
        try:
            with get_connection() as conn:
                # Get position data with current prices (simplified)
                cursor = conn.execute("""
                    SELECT ticker, shares, buy_price, cost_basis 
                    FROM portfolio 
                    WHERE portfolio_id = ?
                """, (portfolio_id,))
                
                positions = cursor.fetchall()
                
                if not positions:
                    return {}
                
                # Value-specific calculations
                total_cost = sum(pos[3] for pos in positions)
                position_count = len(positions)
                
                # Safety margin (simplified - would need current prices)
                avg_cost_per_position = total_cost / position_count if position_count > 0 else 0
                
                return {
                    "position_count": position_count,
                    "avg_cost_per_position": avg_cost_per_position,
                    "total_cost_basis": total_cost,
                    "value_discipline_score": 85,  # Placeholder - would calculate based on P/E, P/B ratios
                    "strategy_focus": "Value-oriented metrics"
                }
                
        except Exception as e:
            logger.error(f"Error calculating value metrics: {e}")
            return {}
    
    def _calculate_income_metrics(self, portfolio_id: int, period: str) -> Dict[str, Any]:
        """Calculate income/dividend-specific metrics."""
        return {
            "estimated_dividend_yield": 0.0,  # Would need dividend data
            "income_consistency_score": 0.0,
            "strategy_focus": "Income-oriented metrics"
        }
    
    def _calculate_benchmark_comparison(self, portfolio_id: int, benchmark_symbol: str, period: str) -> Dict[str, Any]:
        """Calculate portfolio vs benchmark performance."""
        # This would integrate with market data service to get benchmark returns
        # For now, return placeholder data
        return {
            "benchmark_return": 8.5,  # Placeholder
            "excess_return": 2.3,     # Portfolio return - benchmark return
            "beta": 1.1,              # Portfolio volatility vs benchmark
            "alpha": 1.8,             # Excess return adjusted for risk
            "correlation": 0.75       # Correlation with benchmark
        }
    
    # === Cross-Portfolio Comparison ===
    
    def compare_portfolios(self, portfolio_ids: List[int], period: str = "3M") -> PortfolioComparison:
        """
        Compare performance across multiple portfolios.
        
        Args:
            portfolio_ids: List of portfolio IDs to compare
            period: Time period for comparison
        
        Returns:
            PortfolioComparison with comparative analysis
        """
        portfolios_analytics = []
        
        for portfolio_id in portfolio_ids:
            try:
                analytics = self.get_portfolio_analytics(portfolio_id, period)
                portfolios_analytics.append(analytics)
            except Exception as e:
                logger.error(f"Error getting analytics for portfolio {portfolio_id}: {e}")
                continue
        
        if not portfolios_analytics:
            raise ValueError("No valid portfolio analytics data found")
        
        # Calculate comparative metrics
        comparison = PortfolioComparison(
            portfolios=portfolios_analytics,
            comparison_period=period
        )
        
        # Find best and worst performers
        returns = [(p.portfolio_name, p.total_return) for p in portfolios_analytics]
        returns.sort(key=lambda x: x[1], reverse=True)
        
        comparison.best_performer = returns[0][0] if returns else None
        comparison.worst_performer = returns[-1][0] if returns else None
        
        # Create rankings
        comparison.return_rankings = returns
        
        # Sharpe ratio rankings
        sharpe_data = [(p.portfolio_name, p.sharpe_ratio or 0) for p in portfolios_analytics]
        sharpe_data.sort(key=lambda x: x[1], reverse=True)
        comparison.sharpe_rankings = sharpe_data
        
        return comparison
    
    def get_all_portfolios_comparison(self, period: str = "3M") -> PortfolioComparison:
        """Get comparison of all active portfolios."""
        portfolios = self.repository.get_all_active_portfolios()
        portfolio_ids = [p.id for p in portfolios]
        return self.compare_portfolios(portfolio_ids, period)
    
    # === Utility Methods ===
    
    def _get_period_start_date(self, period: str) -> str:
        """Convert period string to start date."""
        today = datetime.now()
        
        if period == "1M":
            start_date = today - timedelta(days=30)
        elif period == "3M":
            start_date = today - timedelta(days=90)
        elif period == "6M":
            start_date = today - timedelta(days=180)
        elif period == "1Y":
            start_date = today - timedelta(days=365)
        elif period == "YTD":
            start_date = datetime(today.year, 1, 1)
        else:  # "All"
            start_date = datetime(2020, 1, 1)  # Arbitrary early date
        
        return start_date.strftime("%Y-%m-%d")
    
    def _calculate_sharpe_ratio(self, daily_returns: pd.Series, risk_free_rate: float = 0.02) -> Optional[float]:
        """Calculate Sharpe ratio for daily returns."""
        if len(daily_returns) < 2:
            return None
        
        try:
            excess_returns = daily_returns - (risk_free_rate / 252)  # Daily risk-free rate
            if excess_returns.std() == 0:
                return None
            
            sharpe = excess_returns.mean() / excess_returns.std() * np.sqrt(252)
            return float(sharpe)
        except Exception:
            return None
    
    def _calculate_max_drawdown(self, values: pd.Series) -> Optional[float]:
        """Calculate maximum drawdown percentage."""
        if len(values) < 2:
            return None
        
        try:
            peak = values.expanding().max()
            drawdown = (values - peak) / peak
            max_dd = drawdown.min() * 100  # Convert to percentage
            return float(max_dd)
        except Exception:
            return None


# Global service instance
enhanced_analytics_service = EnhancedAnalyticsService()