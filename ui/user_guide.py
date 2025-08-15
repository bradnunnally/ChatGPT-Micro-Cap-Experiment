import streamlit as st


def show_user_guide() -> None:
    """Display the user guide as a full standalone page (no collapsible container)."""
    st.subheader("🚀 Getting Started")
    st.markdown(
            """
            Welcome to the **AI Assisted Trading Portfolio Manager** – a Streamlit application providing live (or deterministic synthetic) pricing, analytics, multi‑strategy allocation, and execution.

            ### 1. **Initial Setup**
            - **Add Cash**: Use the Dashboard cash panel
            - **Environment**: `APP_ENV=dev_stage` (synthetic) or `APP_ENV=production` (Finnhub)
            - **Fresh Start**: Starts empty; import or create positions

            ### 2. **Dashboard**
            - Holdings table with real‑time (or synthetic) prices & unrealized PnL
            - Cash, equity, allocations summary
            - Quick trade forms

            ### 3. **Trading Operations**
            - **Buying / Selling**: Submit orders via forms
            - **Validation**: Basic price & quantity checks
            - **Execution Log**: Filled trades appended to trade log (persisted)
            - **Dry Run (Strategies Page)**: Simulate rebalance without committing

            ### 4. **Watchlist**
            - Track tickers, view live/simulated price
            - One‑click trade entry

            ### 5. **Performance & Risk**
            - Equity curve, drawdown, rolling vol, Sharpe/Sortino
            - VaR / ES (95,99), concentration, hit ratios
            - PnL attribution (price vs position effect)
            """
        )

    st.subheader("💡 Key Features (Overview)")
    st.markdown(
            """
            - **Unified Market Data**: Finnhub (production) or deterministic synthetic (dev_stage)
            - **Multi-Strategy Allocation**: Combine strategies via capital weights
            - **Regime Engine (Phase 14)**: Feature extraction → probabilistic classification (Bull / Bear / High Vol / Sideways) → blended risk targets (dynamic vol & gross exposure)
            - **Execution Engine**: Scaling, partial fills, slippage bps, dry-run, trade logging
            - **Risk Overlays**: Per-ticker & sector weight caps (phase 7 foundation)
            - **Optimization (Phase 9)**: Mean-Variance, Risk Parity, Min-Variance, Constrained Risk Parity strategies; turnover penalty, factor neutralization, volatility cap, regime risk scaling overlay, profiling diagnostics
            - **Turnover Budget (Phase 14 add-on)**: Rolling window % of average equity cap with pre‑trade blocking & ledger (see section below)
            - **Analytics**: Extended performance & risk metrics
            - **Persistence**: SQLite storage for portfolio, history, trade_log, strategy registry
            - **Testing**: ≥80% coverage gate
            """
        )

    st.subheader("🛡️ Risk & Overlays")
    st.markdown(
            """
            - **Ticker Cap**: Limits composite weight of any single name
            - **Sector Cap**: Scales sector constituents when threshold exceeded
            - **Alerts**: Drawdown, concentration, VaR95
            - **Slippage Tracking**: Execution report shows slippage_cost per order
            - **Turnover Enforcement**: BUY orders can be blocked if predicted window % exceeds configured cap
            """
        )

    st.subheader("🧠 Strategies Page Workflow")
    st.markdown(
            """
            1. Register strategies (Equal Weight auto, add Momentum Top-N)
            2. Set capital weights (auto-normalized)
            3. (Optional) Apply regime heuristic adjustments
            4. Combine into composite allocation
            5. Review deltas & generated orders (filters: min shares/value, weight tolerance)
            6. (Optional) Apply risk overlays (ticker/sector caps)
            7. (Optional) Apply optimization overlays (turnover penalty, factor neutralization, regime risk scaling, volatility cap)
            8. Inspect Optimization Diagnostics (expected return, vol, correlations, weight deltas, factor betas, pre/post portfolio vol, gross exposure)
            9. (Optional) Run profiling to view timing breakdown (estimators / strategies / overlays)
            10. Dry run execution (no state change) – inspect statuses & slippage
            11. Execute to commit trades (trade log updated)
            12. Persist configuration (registry saved to DB)
            """
        )

    st.subheader("🔧 Technical Notes")
    st.markdown(
            """
            - **Synthetic Mode**: Deterministic OHLCV for reproducible tests & offline use
            - **Order Scaling**: Buys proportionally scaled if aggregate cost > cash
            - **Partial Fills**: Optional; otherwise rejected when insufficient cash/shares
            - **Slippage**: Basis point adjustment applied to execution price
            - **Extensibility**: Implement `target_weights(ctx)` and register new strategies
            - **Testing**: Run `pytest` (coverage gate enforced)
            - **Graceful Degradation**: Turnover module optional; if absent, execution ignores enforcement silently
            """
        )

    st.subheader("📊 Data Coverage & Provider Capabilities")
    st.markdown(
            """
            | Mode | Source | Typical Use | Notes |
            | ---- | ------ | ----------- | ----- |
            | Production | Finnhub | Live quotes, profile, news, earnings | Requires `FINNHUB_API_KEY` |
            | Development | Synthetic Generator | Deterministic offline quotes & history | Zero network usage |

            **Capability Detection:** Columns & metrics auto-hide when unsupported (e.g., Spread, ADV20).

            **Phase 7 Additions:** Strategy registry persistence, regime heuristic integration, execution slippage cost attribution, weight & sector cap overlays.

            **Phase 9 Additions:**
            - Optimization strategies (Mean-Variance Σ⁻¹μ heuristic, Risk Parity inverse-vol, Min-Variance Σ⁻¹1 normalized, Constrained Risk Parity with max weight & iterative risk contribution balancing)
            - Turnover penalty (L1 shrink vs current weights using cost-adjusted threshold)
            - Factor neutralization (rolling betas vs selected factor/style ETFs; constant exposures skipped; degeneracy fallback to original weights)
            - Volatility cap (uniform scaling to target max annualized vol; implicit cash buffer)
            - Regime risk scaling overlay (uniform gross exposure reduction in high_vol / bear regimes before vol targeting)
            - Diagnostics panel (expected returns, daily vol, correlations, weight deltas, factor betas, pre/post portfolio vol, gross exposure)
            - Performance profiling utility (timing: returns estimation, covariance, strategy evaluation, overlays)
            - Factor exposure estimation via rolling OLS (no intercept) with stability safeguards

            **Phase 14 Additions:** Adaptive regime probabilistic layer, turnover budget ledger & enforcement.

            **Roadmap:** Liquidity-adjusted sizing, realized volatility targeting loop, advanced turnover attribution, adaptive regime model calibration.
            """
        )

    st.subheader("🧭 Adaptive Regime Layer (Phase 14)")
    st.markdown(
        """
        The adaptive regime module converts rolling market features into **probabilities** across four regimes:
        `bull`, `bear`, `high_vol`, `sideways`. These probabilities are then mapped to blended **risk targets** used by overlays:

        - **Feature Extraction**: Rolling volatility (short/med/long), volatility ratios, medium-horizon return, drawdown depth, downside hit rate, simple trend flag.
        - **Scoring → Probabilities**: Transparent heuristic scores (trend, Sharpe proxy, downside pressure, drawdown stress, vol expansion) combined via softmax.
        - **Risk Translation**: Probabilities blend regime-specific target annualized volatility (e.g. Bull 18%, Bear 10%, High Vol 12%, Sideways 14%) and gross exposure scalers (Bull 1.00, Bear 0.60, High Vol 0.70, Sideways 0.85) into dynamic targets.
        - **Usage**: Downstream optimization / overlays can (next steps) scale composite weights to the blended gross target and optionally volatility-target the portfolio.
        - **Interpretation**: A mixed environment (e.g. 40% high_vol, 35% bear) produces intermediate risk targets instead of regime “flips”.

        Current defaults favor *rapid de‑risking* under combined deep drawdown + elevated short-term volatility + high downside hit rate (crisis composite).

        Upcoming steps will wire: (1) probability display & diagnostics, (2) dynamic gross scaler application, (3) optional realized vol targeting loop.
        """
    )

    # --- New Section: Turnover Budget & Enforcement ---
    st.subheader("♻️ Turnover Budget & Enforcement")
    st.markdown(
        """
        The **Turnover Budget** limits cumulative trade notional over a rolling window (default 30 days) to a
        configurable fraction of average portfolio equity (default 80%). This encourages *measured capital
        rotation* and reduces churn.

        **Mechanics**
        - Each committed BUY or SELL appends a ledger row with notional and an equity snapshot.
        - A pre‑trade check on BUY orders predicts post‑trade window %; if it would exceed the cap the order is tagged `blocked_turnover` and skipped.
        - SELLs are currently logged for transparency but do not trigger blocking (configurable later).
        - Average equity is approximated from recorded snapshots; future enhancement may weight recent observations.

        **Configuration**
        - Table: `turnover_budget` (single row) with `window_days`, `max_pct`.
        - Ledger: `turnover_ledger` capturing `timestamp`, `ticker`, `side`, `notional`, `equity_snapshot`, `blocked`.
        - Initialize / update using `init_turnover_budget(...)` in `services.turnover_budget` or via future UI panel.

        **Execution Report Tags**
        - `filled` / `partial_filled`: Executed normally.
        - `blocked_turnover`: Skipped due to projected budget breach.
        - `rejected`: Failed validation (cash / shares).
        - `skipped`: Non-actionable (e.g. price/share invalid or scaled_to_zero).

        **Design Choices**
        - BUY‑side pre‑block keeps realized turnover deterministic and avoids post‑hoc rollbacks.
        - Graceful fallback: if turnover module import fails, execution proceeds without enforcement.
        - Simplicity first: single rolling window; future roadmap could add per‑strategy buckets or decay weighting.

        **Monitoring (Planned UI)**
        - Remaining %, used %, total notional, recent ledger entries.
        - Visual gauge for current vs. cap.

        **Testing**
        - Unit tests validate initialization, predictive blocking, and ledger clearing.
        - Integration tests (planned) will assert `blocked_turnover` status within `execute_orders`.
        """
    )
