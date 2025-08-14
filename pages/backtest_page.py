from pathlib import Path
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sqlite3

from components.nav import navbar
from app_settings import settings
from services.backtest import run_backtest, simple_moving_average_strategy

st.set_page_config(page_title="Backtests", layout="wide", initial_sidebar_state="collapsed")
navbar(Path(__file__).name)
st.subheader("Backtest Sandbox")

@st.cache_data
def load_price_series(db_path: str, ticker: str) -> pd.Series:
    conn = sqlite3.connect(db_path)
    if ticker == "TOTAL":
        q = "SELECT date, total_equity as price FROM portfolio_history WHERE ticker='TOTAL' ORDER BY date"
    else:
        q = "SELECT date, current_price as price FROM portfolio_history WHERE ticker=? ORDER BY date"
    if ticker == "TOTAL":
        df = pd.read_sql_query(q, conn, parse_dates=["date"])  # no param
    else:
        df = pd.read_sql_query(q, conn, params=(ticker,), parse_dates=["date"])
    conn.close()
    if df.empty:
        return pd.Series(dtype=float)
    return df.set_index("date")["price"].astype(float)

with st.form("backtest_form"):
    col1, col2, col3, col4 = st.columns(4)
    ticker = col1.text_input("Ticker (or TOTAL)", value="TOTAL")
    fast = col2.number_input("Fast MA", min_value=2, max_value=50, value=5)
    slow = col3.number_input("Slow MA", min_value=fast+1, max_value=200, value=20)
    run_btn = col4.form_submit_button("Run Backtest")

if run_btn:
    series = load_price_series(str(settings.paths.db_file), ticker.upper())
    if series.empty:
        st.warning("No data for selected ticker.")
    else:
        def strat(pr):
            return simple_moving_average_strategy(pr, fast=int(fast), slow=int(slow))
        res = run_backtest(series, strat)  # type: ignore[arg-type]
        st.success("Backtest complete")
        # Equity curve
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=res.equity_curve.index, y=res.equity_curve.values, name="Equity", line=dict(color="#1f77b4")))
        fig.update_layout(title=f"Equity Curve ({ticker.upper()})", xaxis_title="Date", yaxis_title="Equity Multiple")
        st.plotly_chart(fig, use_container_width=True)
        # Metrics
        mcol1, mcol2, mcol3 = st.columns(3)
        mcol1.metric("Total Return (%)", f"{res.metrics['total_return_pct']:.2f}%")
        mcol2.metric("Max Drawdown (%)", f"{res.metrics['max_drawdown_pct']:.2f}%")
        mcol3.metric("Sharpe*", f"{res.metrics['sharpe_like']:.2f}")
        # Trades table (signals)
        with st.expander("Signals / Trades"):
            st.dataframe(res.trades[["price", f"fast_{fast}", f"slow_{slow}", "signal", "position"]])
else:
    st.info("Configure parameters and run a backtest.")
