import streamlit as st


def show_user_guide() -> None:
    """Display the user guide with helpful information."""
    with st.expander("📚 User Guide", expanded=True):
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
            - **Regime Heuristic**: Bull / Bear / High Vol / Sideways classification to nudge weights
            - **Execution Engine**: Scaling, partial fills, slippage bps, dry-run, trade logging
            - **Risk Overlays**: Per-ticker & sector weight caps (phase 7 foundation)
            - **Analytics**: Extended performance & risk metrics
            - **Persistence**: SQLite storage for portfolio, history, trade_log, strategy registry
            - **Testing**: ≥80% coverage gate
            """
        )

        st.subheader("�️ Risk & Overlays")
        st.markdown(
            """
            - **Ticker Cap**: Limits composite weight of any single name
            - **Sector Cap**: Scales sector constituents when threshold exceeded
            - **Alerts**: Drawdown, concentration, VaR95
            - **Slippage Tracking**: Execution report shows slippage_cost per order
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
            7. Dry run execution (no state change) – inspect statuses & slippage
            8. Execute to commit trades (trade log updated)
            9. Persist configuration (registry saved to DB)
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

            **Roadmap:** Liquidity-adjusted sizing, volatility targeting, turnover constraints, adaptive regime models.
            """
        )
