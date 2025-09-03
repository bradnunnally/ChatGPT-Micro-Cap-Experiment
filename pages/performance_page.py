import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app_settings import settings
from components.nav import navbar

try:
    # set_page_config can only be called once and must be the first Streamlit
    # call on a page. When this module is imported after the app has already
    # set a page config (for example, during dynamic imports from
    # `render_dashboard()`), Streamlit raises StreamlitAPIException. Guard
    # against that to keep imports safe during runtime and tests.
    st.set_page_config(page_title="Performance", layout="wide", initial_sidebar_state="collapsed")
except Exception:
    # Ignore errors occurring when page config has already been set.
    # This keeps module import safe when used as a helper (not as the main
    # entry script) while preserving the configuration when possible.
    pass

navbar(Path(__file__).name)

st.subheader("Performance Dashboard")


@st.cache_data
def load_portfolio_history(db_path: str) -> pd.DataFrame:
    """Load portfolio history from the database including individual tickers."""
    conn = sqlite3.connect(db_path)
    query = """
        SELECT date, ticker, shares, cost_basis, stop_loss, current_price, total_value, pnl, action, cash_balance, total_equity
        FROM portfolio_history 
        ORDER BY date;
    """
    df = pd.read_sql_query(query, conn, parse_dates=["date"])
    conn.close()

    # Replace empty strings safely and convert relevant columns to numeric without deprecated downcasting
    for col in [
        "shares",
        "cost_basis",
        "stop_loss",
        "current_price",
        "total_value",
        "pnl",
        "cash_balance",
        "total_equity",
    ]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].mask(df[col] == "", np.nan), errors="coerce")

    # Drop rows where both total_equity and total_value are NaN (no meaningful data)
    if "total_equity" in df.columns and "total_value" in df.columns:
        df = df.dropna(subset=["total_equity", "total_value"], how="all")

    return df


def load_portfolio_history_snapshot(db_path: str, months: int = 6) -> pd.DataFrame:
    """Return a snapshot of portfolio history for the past `months` months (by calendar days).

    This is a convenience used by summary/KPI generation to obtain a recent window
    without re-running the full page logic.
    """
    df = load_portfolio_history(db_path)
    if df.empty:
        return df
    end = df["date"].max()
    start = end - pd.DateOffset(months=months)
    mask = (df["date"] >= start) & (df["date"] <= end)
    return df.loc[mask]


def create_performance_chart(hist_filtered: pd.DataFrame) -> tuple[go.Figure, dict]:
    """Create a performance chart with overall and individual ticker lines.
    
    Returns:
        tuple: (figure, legend_info) where legend_info contains ticker-color mappings
    """
    fig = go.Figure()
    legend_info = {}

    # Define a color palette for consistency
    colors = [
        "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", 
        "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf"
    ]
    
    # Do not plot the overall portfolio line on the chart (KPIs still use TOTAL rows).
    # Add individual ticker performance lines
    color_index = 0
    for ticker in hist_filtered["ticker"].unique():
        if ticker != "TOTAL":
            ticker_data = hist_filtered[hist_filtered["ticker"] == ticker]
            ticker_color = colors[color_index % len(colors)]
            fig.add_trace(
                go.Scatter(
                    x=ticker_data["date"],
                    y=ticker_data["total_value"],
                    name=ticker,
                    line=dict(width=1, color=ticker_color),
                    opacity=0.7,
                )
            )
            legend_info[ticker] = ticker_color
            color_index += 1

    fig.update_layout(
        title="Portfolio Performance",
        xaxis_title="Date",
        yaxis_title="Value ($)",
        hovermode="x unified",
        showlegend=False,  # Hide the default legend
    )
    return fig, legend_info


def display_chart_legend(legend_info: dict) -> None:
    """Display a custom legend below the chart showing ticker-color mappings."""
    if not legend_info:
        return
        
    st.markdown("#### Chart Legend")
    
    # Create columns for the legend items
    legend_items = list(legend_info.items())
    cols = st.columns(min(len(legend_items), 4))  # Max 4 columns
    
    for i, (ticker, color) in enumerate(legend_items):
        col_idx = i % len(cols)
        with cols[col_idx]:
            # Create a colored indicator using HTML/CSS
            st.markdown(
                f'<div style="display: flex; align-items: center; margin-bottom: 5px;">'
                f'<div style="width: 20px; height: 3px; background-color: {color}; margin-right: 8px; '
                f'border-radius: 2px;"></div>'
                f'<span style="font-size: 14px;">{ticker}</span>'
                f'</div>',
                unsafe_allow_html=True
            )


def calculate_kpis(hist_filtered: pd.DataFrame) -> dict:
    """Calculate key performance indicators from filtered history data."""

    # Filter for only TOTAL rows for portfolio-level metrics
    portfolio_data = hist_filtered[hist_filtered["ticker"] == "TOTAL"].copy()

    if portfolio_data.empty:
        return {
            "initial_equity": 0.0,
            "final_equity": 0.0,
            "net_profit": 0.0,
            "total_return": 0.0,
            "avg_daily_return": 0.0,
            "max_drawdown": 0.0,
            "num_days": 0,
        }

    # Sort and forward-fill missing values
    portfolio_data = portfolio_data.sort_values("date")
    portfolio_data["total_equity"] = portfolio_data["total_equity"].ffill()
    portfolio_data["daily_return"] = portfolio_data["total_equity"].pct_change(fill_method=None)

    # Calculate metrics
    initial_equity = float(portfolio_data["total_equity"].iloc[0])
    final_equity = float(portfolio_data["total_equity"].iloc[-1])
    net_profit = final_equity - initial_equity

    # Avoid division by zero
    total_return = ((final_equity / initial_equity - 1) * 100) if initial_equity > 0 else 0.0

    avg_daily_return = portfolio_data["daily_return"].mean() * 100

    # Calculate maximum drawdown
    portfolio_data["rolling_max"] = portfolio_data["total_equity"].cummax()
    portfolio_data["drawdown"] = (
        portfolio_data["total_equity"] / portfolio_data["rolling_max"] - 1
    ) * 100
    max_drawdown = portfolio_data["drawdown"].min()

    # Count trading days
    num_days = len(portfolio_data)

    return {
        "initial_equity": initial_equity,
        "final_equity": final_equity,
        "net_profit": net_profit,
        "total_return": total_return,
        "avg_daily_return": avg_daily_return,
        "max_drawdown": max_drawdown,
        "num_days": num_days,
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
    styles = [""] * len(row)
    if "Current Price" in row and "Stop Loss" in row:
        if pd.notna(row["Stop Loss"]) and row["Current Price"] <= row["Stop Loss"]:
            styles = ["background-color: #ffcdd2"] * len(row)
    return styles


def main() -> None:
    history = load_portfolio_history(str(settings.paths.db_file))

    # Handle empty portfolio history
    if history.empty:
        st.info("📊 No portfolio history available yet. Start trading to see performance data!")
        st.markdown(
            """
        **To get started:**
        1. Go to the Dashboard
        2. Add some cash to your account
        3. Buy some stocks
        4. Your performance will appear here over time
        """
        )
        return

    # Default to last 6 months for exploration, fallback to full range if not available
    max_date = history["date"].max().date()
    six_months_ago = (history["date"].max() - pd.DateOffset(months=6)).date()
    min_date = history["date"].min().date()
    default_start = six_months_ago if six_months_ago > min_date else min_date
    # Use two separate calendar widgets for Start and End dates to avoid
    # unpacking issues and improve UX. Display the selected dates formatted
    # as MM-DD-YYYY for clarity below the inputs.
    default_start = six_months_ago if six_months_ago > min_date else min_date
    # Use two native calendar widgets for Start and End dates. Display the
    # selected range beneath them formatted as MM-DD-YYYY for readability.
    col_start, col_end = st.columns(2)
    with col_start:
        start_date = st.date_input(
            "Start date",
            value=default_start,
            min_value=min_date,
            max_value=max_date,
            key="perf_start",
        )
    with col_end:
        end_date = st.date_input(
            "End date",
            value=max_date,
            min_value=min_date,
            max_value=max_date,
            key="perf_end",
        )

    # Ensure start_date <= end_date; swap if user selected in reverse order
    if start_date > end_date:
        start_date, end_date = end_date, start_date

    # Show formatted selected range
    st.markdown(f"**Selected range:** {start_date.strftime('%m-%d-%Y')} — {end_date.strftime('%m-%d-%Y')}")

    mask = (history["date"] >= pd.to_datetime(start_date)) & (
        history["date"] <= pd.to_datetime(end_date)
    )
    hist_filtered = history.loc[mask]

    col_chart, col_meta = st.columns([2, 1])

    with col_chart:
        if not hist_filtered.empty:
            fig, legend_info = create_performance_chart(hist_filtered)
            st.plotly_chart(fig, use_container_width=True)
            
            # Display the custom legend below the chart
            display_chart_legend(legend_info)
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
