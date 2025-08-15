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
from services.optimization import (
    register_phase9_strategies,
    MeanVarianceStrategy,
    RiskParityStrategy,
    factor_neutral_overlay,
    apply_turnover_penalty,
    apply_volatility_cap,
    compute_factor_exposures,
    regime_risk_overlay,  # added
)
from services.factors import get_factor_returns, DEFAULT_FACTORS
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

# Register Phase 9 optimization strategies (idempotent)
register_phase9_strategies()

# Simple form to add a momentum strategy instance
with st.expander("Add Momentum Strategy"):
    col1, col2 = st.columns(2)
    top_n = col1.number_input("Top N by % Change", min_value=1, max_value=20, value=3)
    custom_name = col2.text_input("Name (optional)", value="")
    if st.button("Add Momentum Strategy"):
        name = custom_name.strip() or None
        register_strategy(TopNPriceMomentumStrategy(top_n=int(top_n), name=name), active=True)
        st.success("Strategy added")

with st.expander("Add Optimization Strategies"):
    col_a, col_b = st.columns(2)
    if col_a.button("Add Mean-Variance"):
        register_strategy(MeanVarianceStrategy(), active=True)
        st.success("Mean-Variance strategy added")
    if col_b.button("Add Risk Parity"):
        register_strategy(RiskParityStrategy(), active=True)
        st.success("Risk Parity strategy added")

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
            # Capture pre-overlay composite weights snapshot for diagnostics
            pre_overlay_weights = {r.ticker: r.composite_weight for r in alloc_long.drop_duplicates('ticker').itertuples()}
            # Optional Factor Neutral & Turnover Adjustments
            with st.expander("Phase 9 Optimization Overlays", expanded=False):
                turnover_pen = st.number_input("Turnover Penalty (λ)", min_value=0.0, value=0.0, step=0.1)
                cost_bps = st.number_input("Assumed Cost (bps)", min_value=0.0, value=10.0, step=1.0)
                col_fn1, col_fn2 = st.columns(2)
                apply_factor_neutral = col_fn1.checkbox(
                    "Factor Neutralization", value=False,
                    help="Neutralize selected factor ETF return exposures via projection (rolling betas)."
                )
                selected_factors = []
                if apply_factor_neutral:
                    default_sel = DEFAULT_FACTORS[:3]
                    selected_factors = col_fn2.multiselect(
                        "Factors", DEFAULT_FACTORS, default_sel,
                        help="Select factor/style ETF proxies to neutralize."
                    )
                vol_cap_enabled = st.checkbox("Volatility Cap", value=False)
                target_vol = None
                if vol_cap_enabled:
                    target_vol = st.number_input("Target Max Annual Vol (%)", min_value=1.0, max_value=100.0, value=15.0, step=1.0)
                apply_regime_scale = st.checkbox("Regime Risk Scaling", value=False, help="Uniformly scale risk based on detected market regime (reduces gross exposure in high_vol/bear).")
            # Build composite weights dict to apply overlays
            base_comp = alloc_long.drop_duplicates("ticker")["ticker"].to_list()
            comp_map = {r.ticker: r.composite_weight for r in alloc_long.drop_duplicates('ticker').itertuples()}
            # Turnover penalty vs current weights (approx current portfolio weights)
            current_weights = {}
            if not portfolio_df.empty and 'shares' in portfolio_df.columns and 'ticker' in portfolio_df.columns:
                pv = portfolio_df.copy()
                if 'price' in pv.columns:
                    pv['current_value'] = pv['shares'].astype(float) * pv['price'].astype(float)
                elif 'buy_price' in pv.columns:
                    pv['current_value'] = pv['shares'].astype(float) * pv['buy_price'].astype(float)
                else:
                    pv['current_value'] = 0.0
                totv = pv['current_value'].sum()
                if totv > 0:
                    current_weights = {row.ticker: float(row.current_value / totv) for row in pv.itertuples()}
            if turnover_pen > 0:
                comp_map = apply_turnover_penalty(current_weights, comp_map, cost_bps=cost_bps, penalty=turnover_pen, long_only=True)
            # Factor neutralization using rolling betas vs selected factor ETFs
            if apply_factor_neutral and selected_factors:
                # Build returns history (asset & factors) if available
                returns_hist = ctx.extra.get('returns_history') if ctx.extra else None
                factor_rets_dict = get_factor_returns(selected_factors)
                if returns_hist is not None and not returns_hist.empty and factor_rets_dict:
                    fac_df = pd.DataFrame(factor_rets_dict).dropna(how='all')
                    # Align asset subset to weights universe
                    asset_cols = [c for c in returns_hist.columns if c in comp_map]
                    asset_ret_sub = returns_hist[asset_cols].dropna(how='all')
                    exposures = compute_factor_exposures(asset_ret_sub, fac_df)
                    if not exposures.empty:
                        comp_map = factor_neutral_overlay(comp_map, exposures, exposures.columns, long_only=True)
                else:
                    st.caption("Factor neutralization skipped (insufficient asset or factor return history yet).")
            # Regime risk overlay scaling BEFORE volatility cap so vol cap sees scaled exposure
            if 'apply_regime_scale' in locals() and apply_regime_scale:
                comp_map = regime_risk_overlay(comp_map, regime_label)
            # Volatility cap scaling (introduces implicit cash if scaling <1)
            if vol_cap_enabled and target_vol:
                returns_hist = ctx.extra.get('returns_history') if ctx.extra else None
                scaled = apply_volatility_cap(comp_map, returns_hist, target_vol)
                if scaled:
                    comp_map = scaled
            # Sanity: remove NaN / inf and renormalize; if empty fallback to original snapshot
            import math
            cleaned = {k: float(v) for k, v in comp_map.items() if v is not None and not math.isinf(v) and not math.isnan(v) and v >= 0}
            tot_clean = sum(cleaned.values())
            if tot_clean > 0:
                cleaned = {k: v / tot_clean for k, v in cleaned.items() if v > 0}
            if not cleaned:
                cleaned = pre_overlay_weights  # revert
            comp_map = cleaned
            # Write back adjusted composite weights into alloc_long
            alloc_long = alloc_long.merge(pd.Series(comp_map, name='adj_weight'), left_on='ticker', right_index=True, how='left')
            alloc_long['composite_weight'] = alloc_long['adj_weight'].fillna(alloc_long['composite_weight'])
            alloc_long = alloc_long.drop(columns=['adj_weight'])
            # Diagnostics panel
            with st.expander("Optimization Diagnostics", expanded=False):
                # Expected returns & covariance estimation (ad hoc from context extra returns_history if available)
                returns_hist = ctx.extra.get('returns_history') if ctx.extra else None
                if returns_hist is not None and not returns_hist.empty:
                    # Provide simple stats
                    tail = returns_hist.tail(120)  # limit
                    mu_vec = tail.mean().to_frame(name='exp_ret_daily')
                    vol_vec = tail.std(ddof=0).to_frame(name='vol_daily')
                    diag_df = mu_vec.join(vol_vec)
                    st.markdown("**Estimated Return / Vol (daily)**")
                    st.dataframe(diag_df, use_container_width=True)
                    # Correlation matrix (small sets only)
                    if diag_df.shape[0] <= 25:
                        corr = tail.corr()
                        st.markdown("**Correlation Matrix**")
                        st.dataframe(corr, use_container_width=True)
                    # Portfolio volatility pre/post (using latest weights)
                    try:
                        active_cols = [c for c in tail.columns if c in pre_overlay_weights]
                        if len(active_cols) >= 2:
                            import math
                            pre_w = pd.Series(pre_overlay_weights)
                            pre_w = pre_w[active_cols] / pre_w[active_cols].sum()
                            cov_tail = tail[active_cols].cov().fillna(0.0)
                            pre_var = float(pre_w.values @ cov_tail.loc[pre_w.index, pre_w.index].values @ pre_w.values)
                            pre_vol_ann = math.sqrt(pre_var) * math.sqrt(252)
                            post_w = pd.Series(comp_map)
                            post_w = post_w[active_cols] / post_w[active_cols].sum()
                            post_var = float(post_w.values @ cov_tail.loc[post_w.index, post_w.index].values @ post_w.values)
                            post_vol_ann = math.sqrt(post_var) * math.sqrt(252)
                            # If regime scaling applied, also display gross exposure factor
                            gross_exposure = sum(comp_map.values())
                            st.caption(f"Annual Vol (pre overlays): {pre_vol_ann*100:.2f}% | (post overlays): {post_vol_ann*100:.2f}% | Gross Exposure: {gross_exposure:.2f}")
                    except Exception:
                        pass
                else:
                    st.caption("No returns history in context (use future Phase 9 data plumbing). Showing weights deltas only.")
                # Weight delta (pre vs post overlays)
                weight_delta_rows = []
                for t, pre_w in pre_overlay_weights.items():
                    post_w = comp_map.get(t, 0.0)
                    weight_delta_rows.append({"ticker": t, "pre_weight": pre_w, "post_weight": post_w, "delta": post_w - pre_w})
                wd_df = pd.DataFrame(weight_delta_rows).sort_values('delta', ascending=False)
                st.markdown("**Weight Adjustments (Pre vs Post Overlays)**")
                st.dataframe(wd_df, use_container_width=True)
                # Factor exposure diagnostics if factors neutralized
                if 'selected_factors' in locals() and selected_factors:
                    try:
                        factor_rets_dict = get_factor_returns(selected_factors)
                        if factor_rets_dict and returns_hist is not None and not returns_hist.empty:
                            fac_df = pd.DataFrame(factor_rets_dict).dropna(how='all')
                            asset_cols = [c for c in returns_hist.columns if c in pre_overlay_weights]
                            asset_ret_sub = returns_hist[asset_cols].dropna(how='all')
                            exposures_pre = compute_factor_exposures(asset_ret_sub, fac_df)
                            if not exposures_pre.empty:
                                # Aggregate portfolio beta = sum_i w_i * beta_i
                                beta_pre = (pd.Series(pre_overlay_weights) @ exposures_pre).reindex(fac_df.columns, fill_value=0)
                                exposures_post = compute_factor_exposures(asset_ret_sub, fac_df)
                                beta_post = (pd.Series(comp_map) @ exposures_post).reindex(fac_df.columns, fill_value=0)
                                betas_df = pd.DataFrame({"pre_beta": beta_pre, "post_beta": beta_post})
                                st.markdown("**Portfolio Factor Betas (Pre vs Post)**")
                                st.dataframe(betas_df, use_container_width=True)
                    except Exception:
                        pass
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
