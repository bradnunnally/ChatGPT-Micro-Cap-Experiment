"""
Portfolio Management Page

Provides a comprehensive interface for managing multiple portfolios:
- Create new portfolios with different strategies
- Edit existing portfolio configurations
- View portfolio summaries and performance
- Switch between portfolios
- Delete portfolios (with safety checks)
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from typing import Optional

from components.nav import navbar
from services.portfolio_service import portfolio_service
from core.portfolio_models import Portfolio
from infra.logging import get_logger

logger = get_logger(__name__)

# Portfolio strategy options
STRATEGY_OPTIONS = [
    "Micro-Cap Growth",
    "Small-Cap Value", 
    "Small-Cap Growth",
    "Mid-Cap Growth",
    "Dividend Income",
    "Technology Growth",
    "Healthcare/Biotech",
    "Clean Energy",
    "REITs",
    "Value Investing",
    "Momentum Trading",
    "Conservative Income",
    "Balanced Growth",
    "Aggressive Growth",
    "Custom Strategy"
]

# Benchmark options
BENCHMARK_OPTIONS = {
    "S&P 500": "^GSPC",
    "Russell 2000 (Small-Cap)": "^RUT", 
    "NASDAQ Composite": "^IXIC",
    "Dow Jones": "^DJI",
    "Russell 1000 (Large-Cap)": "^RUI",
    "Russell 3000": "^RUA",
    "FTSE REIT Index": "^RMZ",
    "Technology Sector": "XLK",
    "Healthcare Sector": "XLV",
    "Energy Sector": "XLE",
    "Custom Benchmark": "CUSTOM"
}


def _render_portfolio_overview():
    """Render overview of all portfolios."""
    st.write("### 📊 Portfolio Overview")
    
    portfolios = portfolio_service.get_all_active_portfolios()
    
    if not portfolios:
        st.warning("No portfolios found. Create your first portfolio below.")
        return
    
    # Create summary table
    summary_data = []
    for portfolio in portfolios:
        summary = portfolio_service.get_portfolio_summary_for_ui(portfolio.id)
        summary_data.append({
            "Portfolio": portfolio.name,
            "Strategy": portfolio.strategy_type,
            "Positions": summary["position_count"],
            "Cash": f"${summary['cash_balance']:,.2f}",
            "Cost Basis": f"${summary['total_cost_basis']:,.2f}",
            "Trades": summary["trade_count"],
            "Benchmark": portfolio.benchmark_symbol,
            "Default": "✅" if portfolio.is_default else "",
            "ID": portfolio.id
        })
    
    df = pd.DataFrame(summary_data)
    
    # Display as interactive table
    st.dataframe(
        df.drop("ID", axis=1),  # Hide ID column
        use_container_width=True,
        hide_index=True
    )
    
    # Portfolio selection
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        if st.button("🔄 Refresh Data", use_container_width=True):
            st.rerun()
    
    with col2:
        current_portfolio = portfolio_service.get_current_portfolio()
        if current_portfolio:
            st.success(f"Active: {current_portfolio.name}")
        else:
            st.error("No active portfolio")
    
    with col3:
        # Quick portfolio switch
        portfolio_names = [p.name for p in portfolios]
        if len(portfolio_names) > 1:
            selected = st.selectbox(
                "Switch To:",
                portfolio_names,
                key="quick_switch",
                label_visibility="collapsed"
            )
            if selected:
                selected_portfolio = next(p for p in portfolios if p.name == selected)
                if portfolio_service.set_current_portfolio(selected_portfolio.id):
                    st.success(f"Switched to {selected}")
                    st.rerun()


def _render_create_portfolio_form():
    """Render form to create a new portfolio."""
    st.write("### ➕ Create New Portfolio")
    
    with st.form("create_portfolio_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            name = st.text_input(
                "Portfolio Name *",
                placeholder="e.g., Tech Growth 2025",
                help="Unique name for your portfolio"
            )
            
            strategy = st.selectbox(
                "Investment Strategy *",
                STRATEGY_OPTIONS,
                help="Primary investment strategy for this portfolio"
            )
            
            benchmark_display = st.selectbox(
                "Benchmark Index *",
                list(BENCHMARK_OPTIONS.keys()),
                index=1,  # Default to Russell 2000
                help="Benchmark for performance comparison"
            )
        
        with col2:
            description = st.text_area(
                "Description",
                placeholder="Describe the focus and goals of this portfolio...",
                height=100,
                help="Optional description of portfolio strategy and goals"
            )
            
            if benchmark_display == "Custom Benchmark":
                custom_benchmark = st.text_input(
                    "Custom Benchmark Symbol",
                    placeholder="e.g., QQQ, SPY, ARKK",
                    help="Enter ticker symbol for custom benchmark"
                )
                benchmark_symbol = custom_benchmark.upper() if custom_benchmark else "^GSPC"
            else:
                benchmark_symbol = BENCHMARK_OPTIONS[benchmark_display]
                st.info(f"Benchmark Symbol: {benchmark_symbol}")
        
        # Form submission
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            submitted = st.form_submit_button(
                "🚀 Create Portfolio", 
                use_container_width=True,
                type="primary"
            )
        
        if submitted:
            if not name or not name.strip():
                st.error("Portfolio name is required")
            elif len(name.strip()) < 3:
                st.error("Portfolio name must be at least 3 characters")
            else:
                try:
                    # Check for duplicate names
                    existing_portfolios = portfolio_service.get_all_active_portfolios()
                    if any(p.name.lower() == name.strip().lower() for p in existing_portfolios):
                        st.error("A portfolio with this name already exists")
                    else:
                        # Create the portfolio
                        new_portfolio = portfolio_service.create_new_portfolio(
                            name=name.strip(),
                            description=description.strip() if description else "",
                            strategy_type=strategy,
                            benchmark_symbol=benchmark_symbol
                        )
                        
                        st.success(f"✅ Created portfolio: {new_portfolio.name}")
                        logger.info(f"User created new portfolio", extra={
                            "portfolio_name": new_portfolio.name,
                            "strategy_type": strategy,
                            "benchmark_symbol": benchmark_symbol
                        })
                        
                        # Auto-switch to new portfolio
                        portfolio_service.set_current_portfolio(new_portfolio.id)
                        st.info(f"Switched to new portfolio: {new_portfolio.name}")
                        
                        # Refresh the page
                        st.rerun()
                        
                except Exception as e:
                    st.error(f"Error creating portfolio: {str(e)}")
                    logger.error(f"Portfolio creation failed", extra={
                        "error": str(e),
                        "portfolio_name": name
                    })


def _render_edit_portfolio_section():
    """Render edit/delete portfolio interface."""
    st.write("### ✏️ Edit Portfolio")
    
    portfolios = portfolio_service.get_all_active_portfolios()
    
    if not portfolios:
        st.info("No portfolios available to edit.")
        return
    
    # Select portfolio to edit
    portfolio_options = [(p.name, p.id) for p in portfolios]
    portfolio_names = [name for name, _ in portfolio_options]
    
    selected_name = st.selectbox(
        "Select Portfolio to Edit:",
        portfolio_names,
        key="edit_portfolio_select"
    )
    
    if not selected_name:
        return
    
    # Get selected portfolio
    selected_portfolio = next(p for p in portfolios if p.name == selected_name)
    
    # Edit form
    with st.form("edit_portfolio_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            new_name = st.text_input(
                "Portfolio Name *",
                value=selected_portfolio.name,
                help="Unique name for your portfolio"
            )
            
            new_strategy = st.selectbox(
                "Investment Strategy *",
                STRATEGY_OPTIONS,
                index=STRATEGY_OPTIONS.index(selected_portfolio.strategy_type) 
                      if selected_portfolio.strategy_type in STRATEGY_OPTIONS else 0,
                help="Primary investment strategy for this portfolio"
            )
            
            # Find current benchmark in options
            current_benchmark_display = None
            for display, symbol in BENCHMARK_OPTIONS.items():
                if symbol == selected_portfolio.benchmark_symbol:
                    current_benchmark_display = display
                    break
            
            if not current_benchmark_display:
                current_benchmark_display = "Custom Benchmark"
            
            benchmark_display = st.selectbox(
                "Benchmark Index *",
                list(BENCHMARK_OPTIONS.keys()),
                index=list(BENCHMARK_OPTIONS.keys()).index(current_benchmark_display),
                help="Benchmark for performance comparison"
            )
        
        with col2:
            new_description = st.text_area(
                "Description",
                value=selected_portfolio.description,
                height=100,
                help="Optional description of portfolio strategy and goals"
            )
            
            if benchmark_display == "Custom Benchmark":
                custom_benchmark = st.text_input(
                    "Custom Benchmark Symbol",
                    value=selected_portfolio.benchmark_symbol if current_benchmark_display == "Custom Benchmark" else "",
                    placeholder="e.g., QQQ, SPY, ARKK",
                    help="Enter ticker symbol for custom benchmark"
                )
                new_benchmark_symbol = custom_benchmark.upper() if custom_benchmark else "^GSPC"
            else:
                new_benchmark_symbol = BENCHMARK_OPTIONS[benchmark_display]
                st.info(f"Benchmark Symbol: {new_benchmark_symbol}")
            
            # Default portfolio toggle (only if not already default)
            make_default = False
            if not selected_portfolio.is_default:
                make_default = st.checkbox(
                    "Make Default Portfolio",
                    help="Set as the default portfolio for new sessions"
                )
        
        # Form buttons
        col1, col2, col3 = st.columns([1, 1, 1])
        
        with col1:
            save_submitted = st.form_submit_button(
                "💾 Save Changes", 
                use_container_width=True,
                type="primary"
            )
        
        with col3:
            # Delete button (with confirmation)
            if not selected_portfolio.is_default:  # Can't delete default portfolio
                delete_submitted = st.form_submit_button(
                    "🗑️ Delete Portfolio",
                    use_container_width=True,
                    type="secondary"
                )
            else:
                st.info("Cannot delete default portfolio")
                delete_submitted = False
        
        # Handle form submissions
        if save_submitted:
            if not new_name or not new_name.strip():
                st.error("Portfolio name is required")
            elif len(new_name.strip()) < 3:
                st.error("Portfolio name must be at least 3 characters")
            else:
                try:
                    # Check for duplicate names (excluding current portfolio)
                    existing_portfolios = [p for p in portfolios if p.id != selected_portfolio.id]
                    if any(p.name.lower() == new_name.strip().lower() for p in existing_portfolios):
                        st.error("A portfolio with this name already exists")
                    else:
                        # Update the portfolio
                        updated_portfolio = Portfolio(
                            id=selected_portfolio.id,
                            name=new_name.strip(),
                            description=new_description.strip() if new_description else "",
                            strategy_type=new_strategy,
                            benchmark_symbol=new_benchmark_symbol,
                            created_date=selected_portfolio.created_date,
                            is_active=True,
                            is_default=make_default or selected_portfolio.is_default
                        )
                        
                        portfolio_service.repository.update_portfolio(updated_portfolio)
                        
                        st.success(f"✅ Updated portfolio: {updated_portfolio.name}")
                        logger.info(f"User updated portfolio", extra={
                            "portfolio_id": updated_portfolio.id,
                            "portfolio_name": updated_portfolio.name
                        })
                        
                        st.rerun()
                        
                except Exception as e:
                    st.error(f"Error updating portfolio: {str(e)}")
                    logger.error(f"Portfolio update failed", extra={
                        "error": str(e),
                        "portfolio_id": selected_portfolio.id
                    })
        
        elif delete_submitted:
            # Show confirmation dialog
            st.session_state.confirm_delete_portfolio_id = selected_portfolio.id
            st.rerun()


def _render_delete_confirmation():
    """Render delete confirmation dialog."""
    if not hasattr(st.session_state, 'confirm_delete_portfolio_id'):
        return
    
    portfolio_id = st.session_state.confirm_delete_portfolio_id
    portfolio = portfolio_service.repository.get_portfolio_by_id(portfolio_id)
    
    if not portfolio:
        del st.session_state.confirm_delete_portfolio_id
        return
    
    st.error(f"⚠️ Confirm Deletion of '{portfolio.name}'")
    st.warning("""
    **This action cannot be undone!**
    
    Deleting this portfolio will permanently remove:
    - All positions and holdings
    - All trade history
    - All performance data
    - Cash balance
    """)
    
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        if st.button("❌ Cancel", use_container_width=True):
            del st.session_state.confirm_delete_portfolio_id
            st.rerun()
    
    with col3:
        if st.button("🗑️ DELETE PERMANENTLY", use_container_width=True, type="secondary"):
            try:
                success = portfolio_service.repository.delete_portfolio(portfolio_id)
                if success:
                    st.success(f"✅ Deleted portfolio: {portfolio.name}")
                    logger.info(f"User deleted portfolio", extra={
                        "portfolio_id": portfolio_id,
                        "portfolio_name": portfolio.name
                    })
                    
                    # If this was the current portfolio, switch to default
                    current = portfolio_service.get_current_portfolio()
                    if current and current.id == portfolio_id:
                        default = portfolio_service.repository.get_default_portfolio()
                        if default:
                            portfolio_service.set_current_portfolio(default.id)
                    
                    del st.session_state.confirm_delete_portfolio_id
                    st.rerun()
                else:
                    st.error("Could not delete portfolio (may be default or not found)")
                    
            except Exception as e:
                st.error(f"Error deleting portfolio: {str(e)}")
                logger.error(f"Portfolio deletion failed", extra={
                    "error": str(e),
                    "portfolio_id": portfolio_id
                })


def main():
    """Main portfolio management page."""
    # Set page config to match other pages
    try:
        st.set_page_config(
            page_title="Portfolio Management", 
            layout="wide", 
            initial_sidebar_state="collapsed"
        )
    except Exception:
        # Ignore if already set
        pass
    
    navbar("portfolio_management.py")
    
    st.subheader("Portfolio Management")
    
    # Handle delete confirmation dialog
    _render_delete_confirmation()
    
    # Main content tabs
    tab1, tab2, tab3 = st.tabs(["📊 Overview", "➕ Create New", "✏️ Edit/Delete"])
    
    with tab1:
        _render_portfolio_overview()
    
    with tab2:
        _render_create_portfolio_form()
    
    with tab3:
        _render_edit_portfolio_section()
    
    # Footer with helpful information
    st.markdown("---")
    st.markdown("""
    ### 💡 Portfolio Strategy Guide
    
    - **Micro-Cap Growth**: Companies < $300M market cap with high growth potential
    - **Small-Cap Value**: Undervalued companies $300M - $2B with strong fundamentals  
    - **Dividend Income**: Stable companies with consistent dividend payments
    - **Technology Growth**: Tech companies with innovative products and growth potential
    - **REITs**: Real Estate Investment Trusts for income and diversification
    - **Conservative Income**: Low-risk investments focused on capital preservation
    """)


if __name__ == "__main__":
    main()