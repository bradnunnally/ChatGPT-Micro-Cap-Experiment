from pathlib import Path
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sqlite3

from components.nav import navbar
from app_settings import settings
from services.backtest import run_backtest, simple_moving_average_strategy, BacktestResult
from services.backtest_store import save_backtest, list_runs, load_runs
import time
from strategies.grid import run_sma_grid, summarize_results

st.set_page_config(page_title="Backtests", layout="wide", initial_sidebar_state="collapsed")
navbar(Path(__file__).name)
st.subheader("Backtest Sandbox (Run, Save & Compare)")

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
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    ticker = col1.text_input("Ticker (or TOTAL)", value="TOTAL")
    fast = col2.number_input("Fast MA", min_value=2, max_value=50, value=5)
    slow = col3.number_input("Slow MA", min_value=fast+1, max_value=200, value=20)
    slippage_single = col4.number_input("Slippage (bps)", min_value=0.0, max_value=100.0, value=0.0, step=0.5)
    commission_single = col5.number_input("Commission (bps)", min_value=0.0, max_value=100.0, value=0.0, step=0.5)
    run_btn = col6.form_submit_button("Run Backtest")

with st.expander("Parameter Grid Runner"):
    gcol1, gcol2, gcol3, gcol4, gcol5 = st.columns(5)
    fast_range = gcol1.text_input("Fast values (comma)", value="3,5,8")
    slow_range = gcol2.text_input("Slow values (comma)", value="20,30,50")
    slippage_bps = gcol3.number_input("Slippage (bps)", min_value=0.0, max_value=100.0, value=0.0, step=0.5)
    commission_bps = gcol4.number_input("Commission (bps)", min_value=0.0, max_value=100.0, value=0.0, step=0.5)
    run_grid = gcol5.button("Run Grid")
    if run_grid:
        series_grid = load_price_series(str(settings.paths.db_file), ticker.upper())
        if series_grid.empty:
            st.warning("No data for selected ticker.")
        else:
            try:
                fast_vals = [int(x.strip()) for x in fast_range.split(",") if x.strip()]
                slow_vals = [int(x.strip()) for x in slow_range.split(",") if x.strip()]
                grid_results = run_sma_grid(series_grid, fast_vals, slow_vals, slippage_bps=slippage_bps, commission_bps=commission_bps)
                summary = summarize_results(grid_results)
                if summary.empty:
                    st.info("No valid parameter combinations (ensure fast < slow).")
                else:
                    st.dataframe(summary, use_container_width=True)
                    # Optionally save top 1 run
                    top_params = summary.iloc[0][["fast","slow"]].to_dict()
                    if st.button("Save Top Run"):
                        # Re-run top for persistence with labeling
                        top_strat_series = simple_moving_average_strategy(series_grid, fast=int(top_params['fast']), slow=int(top_params['slow']))
                        top_strat_series.ticker = ticker.upper()
                        save_backtest(top_strat_series, label=f"GRID_TOP_{top_params['fast']}_{top_params['slow']}")
                        st.success("Top run saved")
            except ValueError:
                st.error("Invalid integer list for fast/slow values")

if run_btn:
    series = load_price_series(str(settings.paths.db_file), ticker.upper())
    if series.empty:
        st.warning("No data for selected ticker.")
    else:
        def strat(pr):
            return simple_moving_average_strategy(pr, fast=int(fast), slow=int(slow), slippage_bps=float(slippage_single), commission_bps=float(commission_single))
        res: BacktestResult = run_backtest(series, strat)  # type: ignore[arg-type]
        res.ticker = ticker.upper()
        st.success("Backtest complete")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=res.equity_curve.index, y=res.equity_curve.values, name="Equity", line=dict(color="#1f77b4")))
        fig.update_layout(title=f"Equity Curve ({ticker.upper()})", xaxis_title="Date", yaxis_title="Equity Multiple")
        st.plotly_chart(fig, use_container_width=True)
        mcol1, mcol2, mcol3, mcol4, mcol5 = st.columns(5)
        mcol1.metric("Net Return (%)", f"{res.metrics['total_return_pct']:.2f}%")
        mcol2.metric("Gross Return (%)", f"{res.metrics.get('gross_total_return_pct',0):.2f}%")
        mcol3.metric("Net Sharpe*", f"{res.metrics['sharpe_like']:.2f}")
        mcol4.metric("Gross Sharpe*", f"{res.metrics.get('gross_sharpe_like',0):.2f}")
        mcol5.metric("Txn Cost (bps)", f"{res.metrics.get('transaction_cost_bps_total',0):.1f}")
        with st.expander("Signals / Trades"):
            trade_cols = ["price", f"fast_{fast}", f"slow_{slow}", "signal", "position"]
            for extra in ["gross_ret", "net_ret", "transaction_cost_bps"]:
                if extra in res.trades.columns:
                    trade_cols.append(extra)
            st.dataframe(res.trades[trade_cols])
        with st.expander("Save this run"):
            label = st.text_input("Optional Label", value=f"{ticker.upper()}_SMA_{fast}_{slow}")
            if st.button("Save Backtest", key="save_backtest_btn"):
                run_id = save_backtest(res, label=label)
                st.success(f"Saved run {run_id}")
                st.session_state.setdefault("saved_hint", time.time())
else:
    st.info("Configure parameters and run a backtest.")

with st.sidebar:
    st.markdown("### Saved Runs")
    runs_df = list_runs(limit=50)
    if runs_df.empty:
        st.caption("No saved runs yet.")
    else:
        runs_df["when"] = pd.to_datetime(runs_df["timestamp"], unit="s")
        runs_df["display"] = runs_df.apply(lambda r: f"{r['run_id']} | {r.get('label') or r.get('ticker')} | {r['strategy']}", axis=1)
        selected = st.multiselect("Select runs to compare", options=runs_df["display"].tolist())
        if selected:
            sel_ids = [s.split(" | ")[0] for s in selected]
            loaded = load_runs(sel_ids)
            if loaded:
                figc = go.Figure()
                for rid, rres in loaded.items():
                    figc.add_trace(go.Scatter(x=rres.equity_curve.index, y=rres.equity_curve.values, name=rid))
                figc.update_layout(height=400, title="Equity Curve Comparison")
                st.plotly_chart(figc, use_container_width=True)
                metrics_names = sorted(next(iter(loaded.values())).metrics.keys())
                comp = {rid: {m: rres.metrics.get(m) for m in metrics_names} for rid, rres in loaded.items()}
                metrics_df = pd.DataFrame(comp)
                st.dataframe(metrics_df)
