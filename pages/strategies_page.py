from pathlib import Path
import streamlit as st
import pandas as pd

from components.nav import navbar
from services.strategy import (
    StrategyContext,
    list_strategies,
    register_strategy,
    set_strategy_active,
    combine_strategy_targets,
    EqualWeightStrategy,
    TopNPriceMomentumStrategy,
    compute_allocation_deltas,
    save_strategy_registry,
    load_strategy_registry,
    generate_rebalance_orders,
)
from services.regime import detect_regime
from services.market import fetch_prices
from services.rebalance import execute_orders

st.set_page_config(page_title="Strategies", layout="wide", initial_sidebar_state="collapsed")
navbar(Path(__file__).name)
st.subheader("Strategy Registry & Allocation")

# Load persisted registry (one-time per session) if not yet loaded
if "_strategies_loaded" not in st.session_state:
    caps = load_strategy_registry()
    st.session_state["_strategies_loaded"] = True
    if caps:
        st.session_state["_persisted_capital"] = caps

# Ensure baseline strategies registered (idempotent)
if not any(s.name == "equal_weight" for s in list_strategies(active_only=False)):
    register_strategy(EqualWeightStrategy(), active=True, replace=False)

# Simple form to add a momentum strategy instance
with st.expander("Add Momentum Strategy"):
    col1, col2 = st.columns(2)
    top_n = col1.number_input("Top N by % Change", min_value=1, max_value=20, value=3)
    custom_name = col2.text_input("Name (optional)", value="")
    if st.button("Add Momentum Strategy"):
        name = custom_name.strip() or None
        register_strategy(TopNPriceMomentumStrategy(top_n=int(top_n), name=name), active=True)
        st.success("Strategy added")

all_strats = list_strategies(active_only=False)
if not all_strats:
    st.info("No strategies registered yet.")
else:
    st.markdown("### Registered Strategies")
    act_cols = ["Strategy", "Active"]
    data = []
    for s in all_strats:
        is_active = any(x.name == s.name for x in list_strategies(active_only=True))
        data.append({"Strategy": s.name, "Active": is_active})
    st.dataframe(pd.DataFrame(data), use_container_width=True)
    # Toggle
    with st.form("toggle_strats"):
        options = {row["Strategy"]: row["Active"] for row in data}
        toggles = {}
        cols = st.columns(min(4, len(options)))
        idx = 0
        for name, active in options.items():
            with cols[idx % len(cols)]:
                toggles[name] = st.checkbox(name, value=active)
                idx += 1
        submitted = st.form_submit_button("Update Active States")
        if submitted:
            for name, active in toggles.items():
                set_strategy_active(name, active)
            st.success("Updated strategy activation")
            st.experimental_rerun()

# Allocation blend section
st.markdown("### Multi-Strategy Allocation")
active_strats = list_strategies(active_only=True)
if not active_strats:
    st.warning("Activate at least one strategy to compute allocation.")
else:
    # Simple universe: current portfolio tickers; fetch price % changes for momentum
    portfolio_df = getattr(st.session_state, 'portfolio', pd.DataFrame(columns=['ticker','shares','buy_price']))
    tickers = sorted(set(portfolio_df['ticker'].astype(str))) if not portfolio_df.empty else []
    price_df = pd.DataFrame(columns=['ticker','current_price','pct_change'])
    if tickers:
        price_df = fetch_prices(tickers)
    ctx = StrategyContext(as_of=pd.Timestamp.utcnow(), portfolio=portfolio_df.rename(columns={'Ticker':'ticker','Shares':'shares'}) if 'Ticker' in portfolio_df.columns else portfolio_df, prices=price_df)

    # Strategy capital weights input
    st.caption("Specify capital weights (auto-normalized).")
    cap_inputs = {}
    cols = st.columns(min(5, len(active_strats)))
    persisted_caps = st.session_state.get("_persisted_capital", {})
    for i, strat in enumerate(active_strats):
        with cols[i % len(cols)]:
            default_cap = float(persisted_caps.get(strat.name, 1.0))
            cap_inputs[strat.name] = st.number_input(f"{strat.name}", min_value=0.0, value=default_cap, step=0.1, key=f"cap_{strat.name}")
    regime_info = detect_regime()
    regime_label = regime_info.get("label","unknown")
    st.caption(f"Detected regime: {regime_label} (vol {regime_info.get('vol_pct','?'):.2f}% avg_ret {regime_info.get('avg_ret_pct','?'):.3f}%)")
    # Regime heuristic button (simple illustrative rules)
    if st.button("Apply Regime Heuristic Weights"):
        # Use current capital inputs and adjust, then reassign to inputs by mutating session persisted caps
        adj_caps = {}
        for strat in active_strats:
            base = cap_inputs.get(strat.name, 1.0)
            new_val = base
            if regime_label == "high_vol" and "momentum" in strat.name.lower():
                new_val = base * 0.5
            elif regime_label == "bull" and "momentum" in strat.name.lower():
                new_val = base * 1.2
            elif regime_label == "bear" and "equal" in strat.name.lower():
                new_val = base * 1.1
            adj_caps[strat.name] = new_val
        st.session_state["_persisted_capital"] = adj_caps
        st.experimental_rerun()
    if st.button("Compute Composite Allocation"):
        alloc_long = combine_strategy_targets(active_strats, ctx=ctx, strategy_capital=cap_inputs)
        if alloc_long.empty:
            st.info("No allocation output.")
        else:
            # Build deltas
            price_map = {r.ticker: r.current_price for r in price_df.itertuples()} if not price_df.empty else {}
            total_equity = float(getattr(st.session_state, 'cash', 0.0))
            if not portfolio_df.empty and {'shares','buy_price'}.issubset(portfolio_df.columns):
                # approximate equity base as cash + current position value
                if 'Current Price' in portfolio_df.columns:
                    position_values = (portfolio_df['Shares'].astype(float) * portfolio_df['Current Price'].astype(float)) if 'Shares' in portfolio_df.columns else []
                elif 'price' in portfolio_df.columns:
                    position_values = (portfolio_df['shares'].astype(float) * portfolio_df['price'].astype(float))
                else:
                    position_values = []
                try:
                    pos_val_total = float(position_values.sum()) if hasattr(position_values, 'sum') else 0.0
                except Exception:
                    pos_val_total = 0.0
                total_equity += pos_val_total
            delta_df = compute_allocation_deltas(portfolio_df.rename(columns={'Ticker':'ticker','Shares':'shares'}) if 'Ticker' in portfolio_df.columns else portfolio_df, alloc_long, price_map, total_equity)
            with st.expander("Composite Allocation (Per-Strategy Detail)", expanded=True):
                show_cols = [c for c in ['strategy','ticker','raw_weight','strategy_capital','weighted_contribution','composite_weight'] if c in alloc_long.columns]
                st.dataframe(alloc_long[show_cols], use_container_width=True)
            with st.expander("Execution Deltas", expanded=True):
                st.dataframe(delta_df, use_container_width=True)
                st.caption("shares_delta is target - current (positive = buy, negative = sell)")
                orders = generate_rebalance_orders(delta_df, min_shares=1, min_value=1.0, weight_tolerance=0.0005)
                if orders:
                    st.markdown("**Proposed Orders**")
                    st.dataframe(pd.DataFrame(orders))
                else:
                    st.caption("No material orders after tolerances.")
                if st.button("Persist Strategies & Capital Weights"):
                    save_strategy_registry(cap_inputs)
                    st.success("Persisted strategy configuration")
                st.markdown("---")
                st.caption("Optional: Execute proposed orders (simulation modifies in-memory session portfolio & cash).")
                exec_cols = st.columns(4)
                exec_slip = exec_cols[0].number_input("Slippage (bps)", min_value=0.0, max_value=100.0, value=5.0, step=0.5)
                dry_run = exec_cols[1].checkbox("Dry Run", value=True)
                allow_partial = exec_cols[2].checkbox("Partial Fills", value=True)
                scale_buys = exec_cols[3].checkbox("Scale Buys", value=True)
                if st.button("Execute Orders") and orders:
                    pf_df = getattr(st.session_state, 'portfolio', pd.DataFrame(columns=['ticker','shares','buy_price','cost_basis','stop_loss']))
                    rename_map = {}
                    if 'Ticker' in pf_df.columns: rename_map['Ticker'] = 'ticker'
                    if 'Shares' in pf_df.columns: rename_map['Shares'] = 'shares'
                    if 'Cost Basis' in pf_df.columns: rename_map['Cost Basis'] = 'buy_price'
                    if rename_map:
                        pf_df = pf_df.rename(columns=rename_map)
                    pf_df['buy_price'] = pf_df.get('buy_price', 0.0)
                    cash_val = float(getattr(st.session_state, 'cash', 0.0))
                    new_pf, new_cash, exec_report = execute_orders(
                        pf_df, cash_val, orders, price_map=price_map, slippage_bps=exec_slip,
                        commit=not dry_run, proportional_scale=scale_buys, enable_partial=allow_partial, log_trades=not dry_run
                    )
                    if not dry_run:
                        out_df = new_pf.rename(columns={'ticker':'Ticker','shares':'Shares','buy_price':'Price'})
                        st.session_state.portfolio = out_df
                        st.session_state.cash = new_cash
                        st.success("Orders executed")
                    else:
                        st.info("Dry run only - no state changes")
                    st.dataframe(exec_report, use_container_width=True)
