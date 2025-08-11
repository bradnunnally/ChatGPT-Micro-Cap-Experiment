import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app_settings import settings
from components.nav import navbar

st.set_page_config(page_title="Performance", layout="wide", initial_sidebar_state="collapsed")

navbar(Path(__file__).name)

st.subheader("Performance Dashboard")

@st.cache_data
def load_portfolio_history(db_path: str) -> pd.DataFrame:
    """Load portfolio history from the database including individual tickers."""
    conn = sqlite3.connect(db_path)
    query = """
        SELECT date, ticker, total_equity, total_value 
        FROM portfolio_history 
        ORDER BY date;
    """
    df = pd.read_sql_query(query, conn, parse_dates=["date"])
    conn.close()
    
    # Replace empty strings and convert to float
    df["total_equity"] = pd.to_numeric(df["total_equity"].replace('', np.nan), errors='coerce')
    df["total_value"] = pd.to_numeric(df["total_value"].replace('', np.nan), errors='coerce')
    
    # Drop rows where both values are NaN
    df = df.dropna(subset=['total_equity', 'total_value'], how='all')
    
    return df

def create_performance_chart(hist_filtered: pd.DataFrame) -> go.Figure:
    """Create a performance chart with overall and individual ticker lines."""
    fig = go.Figure()
    
    # Add overall portfolio performance line
    portfolio_data = hist_filtered[hist_filtered['ticker'] == 'TOTAL']
    fig.add_trace(
        go.Scatter(
            x=portfolio_data['date'],
            y=portfolio_data['total_equity'],
            name='Overall Portfolio',
            line=dict(width=3, color='#1f77b4'),
        )
    )
    
    # Add individual ticker performance lines
    for ticker in hist_filtered['ticker'].unique():
        if ticker != 'TOTAL':
            ticker_data = hist_filtered[hist_filtered['ticker'] == ticker]
            fig.add_trace(
                go.Scatter(
                    x=ticker_data['date'],
                    y=ticker_data['total_value'],
                    name=ticker,
                    line=dict(width=1),
                    opacity=0.7,
                )
            )
    
    fig.update_layout(
        title='Portfolio Performance',
        xaxis_title='Date',
        yaxis_title='Value ($)',
        hovermode='x unified',
        showlegend=True,
        legend=dict(
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=0.01,
            bgcolor="rgba(255, 255, 255, 0.8)"
        )
    )
    return fig

def calculate_kpis(hist_filtered: pd.DataFrame) -> dict:
    """Calculate key performance indicators from filtered history data."""
    
    # Filter for only TOTAL rows for portfolio-level metrics
    portfolio_data = hist_filtered[hist_filtered['ticker'] == 'TOTAL'].copy()
    
    if portfolio_data.empty:
        return {
            'initial_equity': 0.0,
            'final_equity': 0.0,
            'net_profit': 0.0,
            'total_return': 0.0,
            'avg_daily_return': 0.0,
            'max_drawdown': 0.0,
            'num_days': 0
        }
    
    # Sort and forward-fill missing values
    portfolio_data = portfolio_data.sort_values('date')
    portfolio_data['total_equity'] = portfolio_data['total_equity'].ffill()
    portfolio_data['daily_return'] = portfolio_data['total_equity'].pct_change(fill_method=None)
    
    # Calculate metrics
    initial_equity = float(portfolio_data['total_equity'].iloc[0])
    final_equity = float(portfolio_data['total_equity'].iloc[-1])
    net_profit = final_equity - initial_equity
    
    # Avoid division by zero
    total_return = ((final_equity / initial_equity - 1) * 100) if initial_equity > 0 else 0.0
    
    avg_daily_return = portfolio_data['daily_return'].mean() * 100
    
    # Calculate maximum drawdown
    portfolio_data['rolling_max'] = portfolio_data['total_equity'].cummax()
    portfolio_data['drawdown'] = (portfolio_data['total_equity'] / portfolio_data['rolling_max'] - 1) * 100
    max_drawdown = portfolio_data['drawdown'].min()
    
    # Count trading days
    num_days = len(portfolio_data)
    
    return {
        'initial_equity': initial_equity,
        'final_equity': final_equity,
        'net_profit': net_profit,
        'total_return': total_return,
        'avg_daily_return': avg_daily_return,
        'max_drawdown': max_drawdown,
        'num_days': num_days
    }

def display_kpis(kpis: dict, col_meta) -> None:
    """Display KPIs in the metadata column."""
    col_meta.subheader("Performance Summary")
    
    metrics = [
        ("Total Return (%)", f"{kpis['total_return']:.2f}%"),
        ("Net Profit ($)", f"${kpis['net_profit']:.2f}"),
        ("Initial Equity", f"${kpis['initial_equity']:.2f}"),
        ("Final Equity", f"${kpis['final_equity']:.2f}"),
        ("Max Drawdown (%)", f"{kpis['max_drawdown']:.2f}%"),
        ("Number of Trading Days", f"{kpis['num_days']}"),
        ("Average Daily Return (%)", f"{kpis['avg_daily_return']:.2f}%"),
    ]
    
    for label, value in metrics:
        col_meta.metric(label, value)

def highlight_stop(row: pd.Series) -> list[str]:
    """Return a list of styles to highlight stop loss breaches."""
    styles = [''] * len(row)
    if 'Current Price' in row and 'Stop Loss' in row:
        if pd.notna(row['Stop Loss']) and row['Current Price'] <= row['Stop Loss']:
            styles = ['background-color: #ffcdd2'] * len(row)
    return styles

def main() -> None:
    history = load_portfolio_history(str(settings.paths.db_file))

    # Handle empty portfolio history
    if history.empty:
        st.info("📊 No portfolio history available yet. Start trading to see performance data!")
        st.markdown("""
        **To get started:**
        1. Go to the Dashboard
        2. Add some cash to your account
        3. Buy some stocks
        4. Your performance will appear here over time
        """)
        return

    min_date = history["date"].min().date()
    max_date = history["date"].max().date()
    start_date, end_date = st.date_input(
        "Select date range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )

    mask = (history["date"] >= pd.to_datetime(start_date)) & (
        history["date"] <= pd.to_datetime(end_date)
    )
    hist_filtered = history.loc[mask]

    col_chart, col_meta = st.columns([2, 1])

    with col_chart:
        if not hist_filtered.empty:
            fig = create_performance_chart(hist_filtered)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No data available for the selected date range.")

    if hist_filtered.shape[0] < 2:
        st.warning("Not enough data available for selected date range.")
        return

    with col_meta:
        kpis = calculate_kpis(hist_filtered)
        display_kpis(kpis, col_meta)


if __name__ == "__main__":
    main()

