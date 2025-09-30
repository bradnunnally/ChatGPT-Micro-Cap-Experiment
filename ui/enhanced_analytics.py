"""
Enhanced Analytics UI Components

Provides advanced analytics visualizations including:
- Portfolio-specific performance dashboards
- Cross-portfolio comparisons
- Strategy-specific metrics displays
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from typing import List, Dict, Any, Optional

from services.enhanced_analytics import enhanced_analytics_service, PortfolioAnalytics, PortfolioComparison
from services.portfolio_service import portfolio_service


def render_enhanced_analytics_page():
    """Main enhanced analytics page."""
    st.header("📊 Enhanced Portfolio Analytics")
    
    # Portfolio selection
    portfolios = portfolio_service.get_all_active_portfolios()
    if not portfolios:
        st.error("No portfolios found. Please create portfolios first.")
        return
    
    # Sidebar controls
    st.sidebar.header("Analytics Controls")
    
    # Period selection
    period_options = ["1M", "3M", "6M", "1Y", "YTD", "All"]
    selected_period = st.sidebar.selectbox("Analysis Period", period_options, index=1)
    
    # Analytics mode selection
    analysis_mode = st.sidebar.radio(
        "Analysis Mode",
        ["Single Portfolio Deep Dive", "Multi-Portfolio Comparison", "Strategy Analysis"]
    )
    
    if analysis_mode == "Single Portfolio Deep Dive":
        render_single_portfolio_analytics(portfolios, selected_period)
    elif analysis_mode == "Multi-Portfolio Comparison":
        render_portfolio_comparison(portfolios, selected_period)
    else:
        render_strategy_analysis(portfolios, selected_period)


def render_single_portfolio_analytics(portfolios: List, selected_period: str):
    """Render detailed analytics for a single portfolio."""
    st.subheader("🎯 Single Portfolio Deep Dive")
    
    # Portfolio selection
    portfolio_options = [(f"{p.name} ({p.strategy_type})", p.id) for p in portfolios]
    selected_name, selected_id = st.selectbox(
        "Select Portfolio", 
        portfolio_options,
        format_func=lambda x: x[0]
    )
    
    try:
        # Get analytics data
        analytics = enhanced_analytics_service.get_portfolio_analytics(selected_id, selected_period)
        
        # Display portfolio header
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Portfolio", analytics.portfolio_name)
        with col2:
            st.metric("Strategy", analytics.strategy_type)
        with col3:
            st.metric("Benchmark", analytics.benchmark_symbol)
        
        # Key performance metrics
        st.write("### 📈 Performance Overview")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric(
                "Total Value", 
                f"${analytics.total_value:,.2f}",
                delta=f"{analytics.total_return:.2f}%" if analytics.total_return else None
            )
        with col2:
            st.metric("Cash Balance", f"${analytics.cash_balance:,.2f}")
        with col3:
            st.metric("Invested Value", f"${analytics.invested_value:,.2f}")
        with col4:
            st.metric(
                "Total Return", 
                f"{analytics.total_return:.2f}%" if analytics.total_return else "N/A"
            )
        
        # Risk metrics
        st.write("### ⚠️ Risk Analysis")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric(
                "Volatility", 
                f"{analytics.volatility:.2f}%" if analytics.volatility else "N/A"
            )
        with col2:
            st.metric(
                "Max Drawdown", 
                f"{analytics.max_drawdown:.2f}%" if analytics.max_drawdown else "N/A"
            )
        with col3:
            st.metric(
                "Sharpe Ratio", 
                f"{analytics.sharpe_ratio:.3f}" if analytics.sharpe_ratio else "N/A"
            )
        with col4:
            st.metric(
                "Value at Risk (95%)", 
                f"{analytics.value_at_risk:.2f}%" if analytics.value_at_risk else "N/A"
            )
        
        # Benchmark comparison
        if analytics.benchmark_return is not None:
            st.write("### 🎯 Benchmark Comparison")
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric(
                    "Benchmark Return", 
                    f"{analytics.benchmark_return:.2f}%"
                )
            with col2:
                st.metric(
                    "Excess Return", 
                    f"{analytics.excess_return:.2f}%" if analytics.excess_return else "N/A"
                )
            with col3:
                st.metric(
                    "Beta", 
                    f"{analytics.beta:.3f}" if analytics.beta else "N/A"
                )
            with col4:
                st.metric(
                    "Alpha", 
                    f"{analytics.alpha:.2f}%" if analytics.alpha else "N/A"
                )
        
        # Strategy-specific metrics
        if analytics.strategy_metrics:
            st.write("### 🎲 Strategy-Specific Metrics")
            
            strategy_cols = st.columns(len(analytics.strategy_metrics))
            for i, (key, value) in enumerate(analytics.strategy_metrics.items()):
                if i < len(strategy_cols):
                    with strategy_cols[i]:
                        if isinstance(value, (int, float)):
                            if "ratio" in key.lower() or "score" in key.lower():
                                st.metric(key.replace("_", " ").title(), f"{value:.1f}")
                            elif "count" in key.lower():
                                st.metric(key.replace("_", " ").title(), f"{value:,}")
                            else:
                                st.metric(key.replace("_", " ").title(), f"${value:,.2f}")
                        else:
                            st.write(f"**{key.replace('_', ' ').title()}:** {value}")
        
        # Performance visualization (placeholder)
        st.write("### 📊 Performance Visualization")
        create_performance_chart(analytics, selected_period)
        
    except Exception as e:
        st.error(f"Error loading analytics: {str(e)}")
        st.write("Please ensure the portfolio has sufficient historical data.")


def render_portfolio_comparison(portfolios: List, selected_period: str):
    """Render comparison between multiple portfolios."""
    st.subheader("⚖️ Multi-Portfolio Comparison")
    
    # Portfolio selection for comparison
    portfolio_options = {f"{p.name} ({p.strategy_type})": p.id for p in portfolios}
    
    selected_portfolios = st.multiselect(
        "Select Portfolios to Compare",
        list(portfolio_options.keys()),
        default=list(portfolio_options.keys())[:min(3, len(portfolio_options))]  # Default to first 3
    )
    
    if len(selected_portfolios) < 2:
        st.warning("Please select at least 2 portfolios for comparison.")
        return
    
    try:
        # Get comparison data
        portfolio_ids = [portfolio_options[name] for name in selected_portfolios]
        comparison = enhanced_analytics_service.compare_portfolios(portfolio_ids, selected_period)
        
        # Performance rankings
        st.write("### 🏆 Performance Rankings")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Total Return Rankings**")
            return_df = pd.DataFrame(comparison.return_rankings, columns=["Portfolio", "Return (%)"])
            return_df["Rank"] = range(1, len(return_df) + 1)
            return_df = return_df[["Rank", "Portfolio", "Return (%)"]]
            st.dataframe(return_df, hide_index=True)
        
        with col2:
            st.write("**Risk-Adjusted Return (Sharpe) Rankings**")
            sharpe_df = pd.DataFrame(comparison.sharpe_rankings, columns=["Portfolio", "Sharpe Ratio"])
            sharpe_df["Rank"] = range(1, len(sharpe_df) + 1)
            sharpe_df = sharpe_df[["Rank", "Portfolio", "Sharpe Ratio"]]
            st.dataframe(sharpe_df, hide_index=True)
        
        # Comparison metrics table
        st.write("### 📊 Detailed Comparison")
        create_comparison_table(comparison.portfolios)
        
        # Visualization
        st.write("### 📈 Comparative Performance")
        create_comparison_charts(comparison.portfolios, selected_period)
        
        # Best/Worst performers
        if comparison.best_performer and comparison.worst_performer:
            col1, col2 = st.columns(2)
            with col1:
                st.success(f"🏆 **Best Performer:** {comparison.best_performer}")
            with col2:
                st.error(f"📉 **Worst Performer:** {comparison.worst_performer}")
        
    except Exception as e:
        st.error(f"Error loading comparison data: {str(e)}")


def render_strategy_analysis(portfolios: List, selected_period: str):
    """Render analysis grouped by strategy type."""
    st.subheader("🎲 Strategy-Based Analysis")
    
    # Group portfolios by strategy
    strategy_groups = {}
    for portfolio in portfolios:
        strategy = portfolio.strategy_type
        if strategy not in strategy_groups:
            strategy_groups[strategy] = []
        strategy_groups[strategy].append(portfolio)
    
    # Display strategy analysis
    for strategy, strategy_portfolios in strategy_groups.items():
        st.write(f"### 📊 {strategy} Strategy Analysis")
        
        if len(strategy_portfolios) == 1:
            # Single portfolio in strategy
            portfolio = strategy_portfolios[0]
            try:
                analytics = enhanced_analytics_service.get_portfolio_analytics(portfolio.id, selected_period)
                display_strategy_summary(analytics)
            except Exception as e:
                st.error(f"Error loading data for {portfolio.name}: {str(e)}")
        else:
            # Multiple portfolios in strategy - show comparison
            try:
                portfolio_ids = [p.id for p in strategy_portfolios]
                comparison = enhanced_analytics_service.compare_portfolios(portfolio_ids, selected_period)
                display_strategy_comparison(strategy, comparison)
            except Exception as e:
                st.error(f"Error loading comparison for {strategy} strategy: {str(e)}")
        
        st.write("---")


def create_performance_chart(analytics: PortfolioAnalytics, period: str):
    """Create performance visualization chart."""
    # This is a placeholder - would integrate with actual historical data
    fig = go.Figure()
    
    # Placeholder data for demonstration
    dates = pd.date_range(end=pd.Timestamp.now(), periods=30, freq='D')
    portfolio_values = [analytics.total_value * (1 + i * 0.001) for i in range(len(dates))]
    
    fig.add_trace(go.Scatter(
        x=dates,
        y=portfolio_values,
        mode='lines',
        name=analytics.portfolio_name,
        line=dict(color='blue', width=2)
    ))
    
    fig.update_layout(
        title=f"{analytics.portfolio_name} Performance ({period})",
        xaxis_title="Date",
        yaxis_title="Portfolio Value ($)",
        showlegend=True,
        plot_bgcolor="rgba(0,0,0,0)",  # Transparent background
        paper_bgcolor="rgba(0,0,0,0)"
    )
    
    st.plotly_chart(fig, use_container_width=True)


def create_comparison_table(portfolios: List[PortfolioAnalytics]):
    """Create detailed comparison table."""
    comparison_data = []
    
    for portfolio in portfolios:
        comparison_data.append({
            "Portfolio": portfolio.portfolio_name,
            "Strategy": portfolio.strategy_type,
            "Total Value": f"${portfolio.total_value:,.2f}",
            "Return (%)": f"{portfolio.total_return:.2f}" if portfolio.total_return else "N/A",
            "Volatility (%)": f"{portfolio.volatility:.2f}" if portfolio.volatility else "N/A",
            "Sharpe Ratio": f"{portfolio.sharpe_ratio:.3f}" if portfolio.sharpe_ratio else "N/A",
            "Max Drawdown (%)": f"{portfolio.max_drawdown:.2f}" if portfolio.max_drawdown else "N/A",
            "Benchmark": portfolio.benchmark_symbol
        })
    
    df = pd.DataFrame(comparison_data)
    st.dataframe(df, hide_index=True)


def create_comparison_charts(portfolios: List[PortfolioAnalytics], period: str):
    """Create comparison visualization charts."""
    # Returns vs Risk scatter plot
    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=("Return vs Risk", "Performance Metrics"),
        specs=[[{"type": "scatter"}, {"type": "bar"}]]
    )
    
    # Scatter plot: Risk vs Return
    for portfolio in portfolios:
        if portfolio.total_return is not None and portfolio.volatility is not None:
            fig.add_trace(
                go.Scatter(
                    x=[portfolio.volatility],
                    y=[portfolio.total_return],
                    mode='markers+text',
                    name=portfolio.portfolio_name,
                    text=[portfolio.portfolio_name],
                    textposition="top center",
                    marker=dict(size=12)
                ),
                row=1, col=1
            )
    
    # Bar chart: Returns comparison
    portfolio_names = [p.portfolio_name for p in portfolios]
    returns = [p.total_return or 0 for p in portfolios]
    
    fig.add_trace(
        go.Bar(
            x=portfolio_names,
            y=returns,
            name="Returns",
            marker_color=['green' if r >= 0 else 'red' for r in returns]
        ),
        row=1, col=2
    )
    
    # Update layout
    fig.update_xaxes(title_text="Volatility (%)", row=1, col=1)
    fig.update_yaxes(title_text="Return (%)", row=1, col=1)
    fig.update_xaxes(title_text="Portfolio", row=1, col=2)
    fig.update_yaxes(title_text="Return (%)", row=1, col=2)
    
    fig.update_layout(
        height=500,
        showlegend=False,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)"
    )
    
    st.plotly_chart(fig, use_container_width=True)


def display_strategy_summary(analytics: PortfolioAnalytics):
    """Display summary for a single portfolio strategy."""
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Portfolio", analytics.portfolio_name)
        st.metric("Total Value", f"${analytics.total_value:,.2f}")
    
    with col2:
        st.metric("Return", f"{analytics.total_return:.2f}%" if analytics.total_return else "N/A")
        st.metric("Volatility", f"{analytics.volatility:.2f}%" if analytics.volatility else "N/A")
    
    with col3:
        st.metric("Sharpe Ratio", f"{analytics.sharpe_ratio:.3f}" if analytics.sharpe_ratio else "N/A")
        st.metric("Max Drawdown", f"{analytics.max_drawdown:.2f}%" if analytics.max_drawdown else "N/A")


def display_strategy_comparison(strategy: str, comparison: PortfolioComparison):
    """Display comparison for portfolios within the same strategy."""
    st.write(f"**{len(comparison.portfolios)} portfolios in {strategy} strategy**")
    
    # Quick stats
    col1, col2 = st.columns(2)
    
    with col1:
        if comparison.best_performer:
            st.success(f"Top Performer: {comparison.best_performer}")
    
    with col2:
        if comparison.worst_performer:
            st.error(f"Bottom Performer: {comparison.worst_performer}")
    
    # Mini comparison table
    strategy_data = []
    for portfolio in comparison.portfolios:
        strategy_data.append({
            "Portfolio": portfolio.portfolio_name,
            "Return (%)": f"{portfolio.total_return:.2f}" if portfolio.total_return else "N/A",
            "Sharpe": f"{portfolio.sharpe_ratio:.3f}" if portfolio.sharpe_ratio else "N/A"
        })
    
    df = pd.DataFrame(strategy_data)
    st.dataframe(df, hide_index=True)