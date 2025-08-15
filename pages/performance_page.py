import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app_settings import settings
from components.nav import navbar
from services.risk import (
    compute_risk_block,
    compute_rolling_betas,
    drawdown_table,
    compute_correlation_matrix,
    compute_var_hit_ratio,
    compute_position_var_contributions,
    compute_average_pairwise_correlation,
)
from services.benchmark import get_benchmark_series, BENCHMARK_SYMBOL_DEFAULT
from services.risk_free import get_risk_free_rate
from services.money import format_money
from services.fundamentals import batch_get_fundamentals
from services.alerts import load_alert_state
from services.factors import factors_summary, get_factor_returns, DEFAULT_FACTORS
from services.market import get_daily_price_series
from services.attribution import compute_factor_attribution, compute_position_contributions

st.set_page_config(page_title="Performance", layout="wide", initial_sidebar_state="collapsed")

navbar(Path(__file__).name)

st.subheader("Performance Dashboard")


@st.cache_data
def load_portfolio_history(db_path: str) -> pd.DataFrame:
    """Load portfolio history from the database including individual tickers."""
    query = """
        SELECT date, ticker, total_equity, total_value 
        FROM portfolio_history 
        ORDER BY date;
    """
    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query(query, conn, parse_dates=["date"])

    # Replace empty strings safely and convert to float without deprecated downcasting
    te = df["total_equity"]
    tv = df["total_value"]
    df["total_equity"] = pd.to_numeric(te.mask(te == "", np.nan), errors="coerce")
    df["total_value"] = pd.to_numeric(tv.mask(tv == "", np.nan), errors="coerce")

    # Drop rows where both values are NaN
    df = df.dropna(subset=["total_equity", "total_value"], how="all")

    return df


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
    
    # Add overall portfolio performance line
    portfolio_data = hist_filtered[hist_filtered["ticker"] == "TOTAL"]
    portfolio_color = "#1f77b4"
    fig.add_trace(
        go.Scatter(
            x=portfolio_data["date"],
            y=portfolio_data["total_equity"],
            name="Overall Portfolio",
            line=dict(width=3, color=portfolio_color),
        )
    )
    legend_info["Overall Portfolio"] = portfolio_color

    # Add individual ticker performance lines
    color_index = 1  # Start from second color since first is used for Overall Portfolio
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


def display_kpis(kpis: dict, risk_metrics, col_meta, hist_filtered: pd.DataFrame) -> None:
    """Display KPIs (performance & risk) in the metadata column."""
    col_meta.subheader("Performance Summary")

    perf_metrics = [
        ("Total Return (%)", f"{kpis['total_return']:.2f}%"),
        ("Net Profit", format_money(kpis['net_profit'])),
        ("Initial Equity", format_money(kpis['initial_equity'])),
        ("Final Equity", format_money(kpis['final_equity'])),
        ("Max Drawdown (%)", f"{kpis['max_drawdown']:.2f}%"),
        ("Number of Trading Days", f"{kpis['num_days']}"),
        ("Average Daily Return (%)", f"{kpis['avg_daily_return']:.2f}%"),
    ]

    risk_section = [
        ("Risk: MDD (%)", f"{risk_metrics.max_drawdown_pct:.2f}%"),
        ("Risk: 20d Vol (%)", f"{risk_metrics.rolling_volatility_pct:.2f}%"),
        ("Risk: Sharpe*", f"{risk_metrics.sharpe_like:.2f}"),
        ("Risk: Top1 Concentration (%)", f"{risk_metrics.concentration_top1_pct:.2f}%"),
        ("Risk: Top3 Concentration (%)", f"{risk_metrics.concentration_top3_pct:.2f}%"),
    ("Risk: Beta~", f"{getattr(risk_metrics,'beta_like',0.0):.2f}"),
    ("Risk: Sortino*", f"{getattr(risk_metrics,'sortino_like',0.0):.2f}"),
    ("Risk: VaR95 (%)", f"{getattr(risk_metrics,'var_95_pct',0.0):.2f}"),
    ("Risk: ES95 (%)", f"{getattr(risk_metrics,'es_95_pct',0.0):.2f}"),
    ("Risk: VaR99 (%)", f"{getattr(risk_metrics,'var_99_pct',0.0):.2f}"),
    ("Risk: ES99 (%)", f"{getattr(risk_metrics,'es_99_pct',0.0):.2f}"),
    ]

    for label, value in perf_metrics + risk_section:
        col_meta.metric(label, value)

    # Fundamentals expander (lazy load)
    with col_meta.expander("Fundamentals (cached daily)"):
        tickers = [t for t in hist_filtered["ticker"].unique() if t != "TOTAL"]
        if not tickers:
            st.caption("No ticker fundamentals to display.")
        else:
            force = st.checkbox("Force refresh fundamentals", value=False, key="force_funds")
            funds = batch_get_fundamentals(tickers) if not force else [
                # per-ticker refresh path
                __import__('services.fundamentals', fromlist=['get_fundamentals']).get_fundamentals(t, force_refresh=True)  # type: ignore
                for t in tickers
            ]
            rows = []
            for f in funds:
                rows.append({
                    "Ticker": f.ticker,
                    "Cash/Share": f"{f.cash_per_share:.2f}" if f.cash_per_share is not None else "-",
                    "Book/Share": f"{f.book_value_per_share:.2f}" if f.book_value_per_share is not None else "-",
                    "Dividend Yield (%)": f"{f.dividend_yield_pct:.2f}" if f.dividend_yield_pct is not None else "-",
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True)


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
        risk_metrics = compute_risk_block(hist_filtered)
    display_kpis(kpis, risk_metrics, col_meta, hist_filtered)

    # Rolling Beta Visualization (portfolio TOTAL vs benchmark)
    with st.expander("Rolling Beta (vs Benchmark)"):
        total_rows = hist_filtered[hist_filtered["ticker"] == "TOTAL"].sort_values("date")
        bench_series = get_benchmark_series(BENCHMARK_SYMBOL_DEFAULT)
        if total_rows.empty or not bench_series:
            st.caption("Insufficient data for rolling beta.")
        else:
            bench_df = pd.DataFrame(bench_series)
            bench_df["date"] = pd.to_datetime(bench_df["date"])  # ensure datetime
            merged = total_rows[["date", "total_equity"]].merge(bench_df, on="date", how="inner")
            merged = merged.sort_values("date")
            if merged.shape[0] < 40:  # require minimum data for 30d window + margin
                st.caption("Need more overlapping history to plot rolling betas.")
            else:
                betas = compute_rolling_betas(merged["total_equity"], merged["close"], windows=[30,60,90])
                if not betas:
                    st.caption("No beta series produced.")
                else:
                    fig_b = go.Figure()
                    palette = {30: "#1f77b4", 60: "#ff7f0e", 90: "#2ca02c"}
                    for w, series in betas.items():
                        fig_b.add_trace(go.Scatter(x=series.index, y=series.values, name=f"{w}d" , line=dict(color=palette.get(w, None))))
                    fig_b.add_hline(y=1.0, line=dict(color="#888", width=1, dash="dash"))
                    fig_b.update_layout(height=300, title="Rolling Beta", yaxis_title="Beta", xaxis_title="Date")
                    st.plotly_chart(fig_b, use_container_width=True)

    # Drawdown Table
    with st.expander("Top Drawdowns"):
        total_rows = hist_filtered[hist_filtered["ticker"] == "TOTAL"].sort_values("date")
        if total_rows.empty:
            st.caption("No equity data.")
        else:
            eq = pd.to_numeric(total_rows["total_equity"], errors="coerce").dropna()
            dd_df = drawdown_table(eq, top_n=5)
            if dd_df.empty:
                st.caption("No drawdowns detected.")
            else:
                fmt = dd_df.copy()
                if "Depth (%)" in fmt.columns:
                    fmt["Depth (%)"] = fmt["Depth (%)"].map(lambda v: f"{v:.2f}%")
                st.dataframe(fmt, use_container_width=True)

    # Correlation Matrix
    with st.expander("Correlation Matrix (Ticker Daily Returns)"):
        corr = compute_correlation_matrix(hist_filtered)
        if corr.empty:
            st.caption("Not enough data / tickers for correlation matrix.")
        else:
            st.dataframe(corr.round(2), use_container_width=True)

    # VaR Hit Ratio (requires sufficient history)
    with st.expander("VaR 95% Hit Ratio (Rolling 100d)"):
        tot = hist_filtered[hist_filtered["ticker"] == "TOTAL"].sort_values("date")
        if tot.shape[0] < 160:
            st.caption("Need at least 160 days of portfolio history to evaluate hit ratio.")
        else:
            # Build daily return series
            eq = pd.to_numeric(tot["total_equity"], errors="coerce").ffill()
            returns = eq.pct_change(fill_method=None)
            hit_ratio = compute_var_hit_ratio(returns, level=0.95, window=100)
            st.metric("Hit Ratio", f"{hit_ratio*100:.2f}%")
            st.caption("Expected exceedance frequency for VaR95 is ~5%. Values >>5% suggest VaR underestimates risk; values <<5% suggest it's conservative.")

    # Position VaR Contributions
    with st.expander("Position VaR Contributions (Parametric Approx)"):
        contrib_df = compute_position_var_contributions(hist_filtered)
        if contrib_df.empty:
            st.caption("Insufficient data to compute contributions (need positions & return history).")
        else:
            show_cols = [c for c in ["ticker","weight_pct","contrib_var_pct","contrib_var_pct_norm","marginal_contrib_pct"] if c in contrib_df.columns]
            st.dataframe(contrib_df[show_cols].round(2), use_container_width=True)

    # Average Pairwise Correlation Trend
    with st.expander("Average Pairwise Correlation (Rolling 30d)"):
        avg_corr = compute_average_pairwise_correlation(hist_filtered, window=30)
        if avg_corr.empty:
            st.caption("Need ≥2 tickers and sufficient overlapping history.")
        else:
            import plotly.express as px
            fig_corr = px.line(avg_corr.reset_index(), x="date", y=avg_corr.name, title="Avg Pairwise Correlation (30d)")
            st.plotly_chart(fig_corr, use_container_width=True)

    # Daily OHLC Rollup Viewer (from archived quotes)
    with st.expander("Daily OHLC (Archived Quotes Rollup)"):
        tickers = sorted([t for t in history["ticker"].unique() if t not in {"TOTAL"}])
        if not tickers:
            st.caption("No tickers in history to show OHLC data.")
        else:
            sel = st.multiselect("Select tickers", tickers, default=tickers[:1])
            limit = st.number_input("Rows (tail)", min_value=5, max_value=500, value=60, step=5)
            show_chart = st.checkbox("Show candlestick chart", value=True, key="show_candle")
            import plotly.graph_objects as _go
            tabs = st.tabs(sel) if sel else []
            for t, tab in zip(sel, tabs):
                with tab:
                    df_o = get_daily_price_series(t, limit=int(limit))
                    if df_o.empty:
                        st.caption("No daily rollup data yet for this ticker.")
                        continue
                    st.dataframe(df_o.tail(int(limit)), use_container_width=True)
                    if show_chart and {"open","high","low","close"}.issubset(df_o.columns):
                        cfig = _go.Figure(data=[_go.Candlestick(x=df_o["date"], open=df_o["open"], high=df_o["high"], low=df_o["low"], close=df_o["close"])])
                        cfig.update_layout(height=320, margin=dict(l=10,r=10,t=30,b=10), title=f"{t} Daily OHLC")
                        st.plotly_chart(cfig, use_container_width=True)

    # Factor / Style ETF Summary Panel
    with st.expander("Factor Summary (ETF Proxies)"):
        # Provide user control to limit symbols
        default_syms = DEFAULT_FACTORS
        sel = st.multiselect("Factor symbols", default_syms, default_syms)
        if not sel:
            st.caption("Select at least one factor symbol.")
        else:
            try:
                summary = factors_summary(sel)
            except Exception:
                summary = {}
            if not summary:
                st.caption("No factor data cached yet (will populate after background refresh / first access).")
            else:
                rows = []
                for k, v in summary.items():
                    rows.append({
                        "Symbol": k,
                        "Points": v.get("points"),
                        "Start": v.get("start"),
                        "End": v.get("end"),
                        "Mean Daily %": round(v.get("mean_daily", 0)*100, 3) if v.get("mean_daily") is not None else None,
                        "Vol Daily %": round(v.get("vol_daily", 0)*100, 3) if v.get("vol_daily") is not None else None,
                    })
                st.dataframe(pd.DataFrame(rows), use_container_width=True)

                # Optional correlation of factor daily returns
                if st.checkbox("Show factor return correlation", value=False, key="factor_corr"):
                    try:
                        rets = get_factor_returns(sel)
                        if rets:
                            ret_df = pd.DataFrame(rets)
                            corr = ret_df.corr().round(2)
                            st.dataframe(corr, use_container_width=True)
                    except Exception:
                        st.caption("Unable to compute factor correlations (insufficient data yet).")

    # Factor Attribution Panel
    with st.expander("Factor Attribution (Beta & Contribution)"):
        factor_syms = st.multiselect("Select factors", DEFAULT_FACTORS, DEFAULT_FACTORS[:3], key="attr_factors")
        window = st.number_input("Window (recent days, 0=all)", min_value=0, max_value=500, value=120, step=10)
        attr = compute_factor_attribution(history, factor_symbols=factor_syms, window=(window or None)) if factor_syms else None
        if attr is None:
            st.caption("Insufficient overlapping history to compute factor attribution.")
        else:
            beta_df = pd.DataFrame({"beta": attr.betas, "cum_return": attr.factor_cum_returns, "contribution": attr.factor_contributions, "contribution_pct": attr.contributions_pct}).sort_values("contribution", ascending=False)
            beta_df["cum_return_pct"] = beta_df["cum_return"] * 100.0
            beta_df["contribution_pct"] = beta_df["contribution_pct"].round(2)
            st.dataframe(beta_df[["beta","cum_return_pct","contribution","contribution_pct"]].round(4), use_container_width=True)
            st.metric("Residual %", f"{attr.residual_pct:.2f}%")
            st.caption("Betas estimated via OLS (no intercept) over selected window; contributions = beta * factor cumulative return. Residual is unexplained portion.")

    # Position Contribution Panel
    with st.expander("Position Return Contributions"):
        pos_window = st.number_input("Window (days)", min_value=20, max_value=365, value=60, step=10, key="pos_window")
        contrib_df = compute_position_contributions(history, window=pos_window)
        if contrib_df.empty:
            st.caption("Need position history to compute contributions.")
        else:
            st.dataframe(contrib_df.round(2), use_container_width=True)

    # Alerts State
    with st.expander("Alerts State"):
        state = load_alert_state()
        if not state:
            st.caption("No alert evaluations yet.")
        else:
            st.json(state)

    # Benchmark + risk-free details (after KPI display)
    with st.expander("Benchmark & Risk-Free Details"):
        bench_symbol = BENCHMARK_SYMBOL_DEFAULT
        series = get_benchmark_series(bench_symbol)
        rf = get_risk_free_rate()
        st.write({
            "benchmark_symbol": bench_symbol,
            "benchmark_points": len(series),
            "benchmark_last_date": series[-1]["date"] if series else None,
            "risk_free_annual": rf,
            "risk_free_daily_equiv": rf/252.0 if rf else 0.0,
        })

    # Attribution & position drill-down (current day)
    latest_date = hist_filtered["date"].max()
    todays_rows = hist_filtered[hist_filtered["date"] == latest_date].copy()
    pos_rows = todays_rows[todays_rows["ticker"] != "TOTAL"].copy()
    if not pos_rows.empty:
        # Derive simple attribution if possible (cost_basis/shares creates buy_price proxy)
        if {"pnl_price", "pnl_position", "pnl_total_attr"}.issubset(set(pos_rows.columns)):
            with st.expander("PnL Attribution (Price vs Position)"):
                show_cols = [c for c in ["ticker","shares","cost_basis","total_value","pnl_price","pnl_position","pnl_total_attr"] if c in pos_rows.columns]
                # Format monetary columns
                fmt_df = pos_rows[show_cols].copy()
                for c in ["cost_basis","total_value","pnl_price","pnl_position","pnl_total_attr"]:
                    if c in fmt_df.columns:
                        fmt_df[c] = fmt_df[c].apply(lambda v: format_money(v) if isinstance(v,(int,float)) else v)
                st.dataframe(fmt_df, use_container_width=True)
        else:
            with st.expander("Current Positions"):
                show_cols = [c for c in ["ticker","shares","cost_basis","total_value"] if c in pos_rows.columns]
                fmt_df = pos_rows[show_cols].copy()
                for c in ["cost_basis","total_value"]:
                    if c in fmt_df.columns:
                        fmt_df[c] = fmt_df[c].apply(lambda v: format_money(v) if isinstance(v,(int,float)) else v)
                st.dataframe(fmt_df, use_container_width=True)


if __name__ == "__main__":
    main()
