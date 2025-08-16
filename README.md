# ChatGPT Micro-Cap Experiment

Welcome to the repository behind my live trading experiment where ChatGPT manages a real-money micro-cap portfolio, now enhanced with a comprehensive **Streamlit Portfolio Management Application**.

## 🎯 The Concept

Starting with just $100, this project answers a simple but powerful question:

**Can large language models like ChatGPT actually generate alpha using real-time market data?**

### Daily Trading Process:
- ChatGPT receives real-time trading data on portfolio holdings
- Strict stop-loss rules and risk management apply  
- Weekly deep research sessions for portfolio reevaluation
- Performance data tracked and published regularly

## 📊 Current Performance

Check out the latest results in [`docs/experiment_details`](docs/experiment_details) and follow weekly updates on [SubStack](https://nathanbsmith729.substack.com).

---

![Week 4 Performance](docs/results-6-30-7-25.png)

*Currently outperforming the Russell 2K benchmark*

---

## 🚀 Portfolio Management Application

This repository now includes a **full-featured Streamlit web application** for portfolio management and analysis.

## 📦 Release Notes v0.5.0 (Governance + Risk Monitor)

This tagged release consolidates prior functionality (Phases 7, 9, selected 14) and introduces core Governance & partial Advanced Risk Monitoring (Phases 10 & partial 11):

### Highlights
- Governance schema & hash chains: `audit_event`, `config_snapshot`, `breach_log`, `risk_event` (all append-only with SHA‑256 prev_hash linking).
- Pre‑trade rule engine (blocking) with rule types: `position_weight`, `max_trade_notional_pct`, `sector_aggregate_weight`.
- Governance Console UI: rule CRUD, snapshots, audit chain verify, breaches panel, risk events panel.
- Risk Monitor: snapshot metrics (equity, cash, top1/top3 concentration, rolling 20d vol, max drawdown, VaR95) + heuristic risk_event emission.
- Exposure Scalar: regime probabilities + open breaches → gross exposure multiplier heuristic.
- Turnover Budget module (rolling window predictive BUY blocking) integrated (from Phase 14 subset).
- Sustained test coverage ≥80% (current ~82.5%).

### Backward Compatibility
- Only additive schema changes (migrations 0002, 0003). Existing pre‑governance DBs require running `make migrate`.
- Execution governance blocking remains opt‑in (`enforce_governance=True` when calling execution path).

### Manual Smoke Checklist
1. `cp .env.example .env` (set APP_ENV=dev_stage) → `make install && make migrate`.
2. Launch: `make run` (or `streamlit run app.py`).
3. Add cash & a few positions; verify Dashboard metrics update.
4. Governance page → create a config snapshot; verify audit chain success.
5. Add a low threshold position weight rule and attempt exceeding BUY → order blocked + breach logged.
6. Trigger a risk event (e.g., concentrate portfolio) → risk events table shows new entry (hash & prev_hash populated).
7. Run `make release-smoke` → tests + audit chain integrity message.
8. (Optional) Tamper test: manually edit a hash in `audit_event`; `verify_audit_chain()` (UI button) should fail.

### Deferred (Not in 0.5.0)
- Scheduled hash integrity audits & alerts.
- Breach notes editing UI & JSON params editor (sector map management).
- Strategy parameter versioning & advanced execution microstructure refinements.

For a detailed change log see `CHANGELOG.md`.

### Key Features (Phases 1–9):
 - **📱 Real-time Portfolio Dashboard** – Live tracking (Finnhub production; deterministic synthetic dev mode)
 - **📈 Performance Analytics** – Historical charts, KPIs, extended risk (MDD, rolling vol, Sharpe*, Sortino*, placeholder beta, concentration, VaR/ES 95 & 99, rolling multi-window betas, correlation matrix, VaR95 hit ratio, position VaR contributions)
 - **🧩 PnL Attribution** – Price vs position effect decomposition
 - **🧪 Backtest Sandbox** – SMA crossover + rotating mini grid sweeps
 - **🎯 Price Source Provenance** – Source badge (BULK/API/MANUAL/ZERO/INIT)
 - **💰 Trading Interface** – Order forms, validation, trade logging
 - **👁️ Watchlist Management** – Quick monitor & trade
 - **💵 Money Value Object** – Decimal‑safe formatting & math
 - **📤 Data Export** – Snapshots & trade log
 - **⏱️ In‑App Scheduler** – Benchmarks, snapshots, fundamentals cache, mini backtests, alerts
 - **🚨 Risk Alerts** – Drawdown, top1 concentration, VaR95 thresholds
 - **🗄️ SQLite Database** – Local persistence layer
 - **🧠 Multi-Strategy Allocation (Phase 7)** – Strategy registry, capital weights, composite targets, regime heuristic, order generation, execution engine (dry‑run, scaling, partial fills, slippage cost), risk overlays (ticker & sector caps)
 - **🧮 Advanced Optimization (Phase 9)** – Mean-Variance, Risk Parity, Min-Variance, Constrained Risk Parity strategies; factor exposure estimation & neutralization, turnover penalty, volatility cap, regime risk scaling overlay, diagnostics & profiling

### Quick Start (Synthetic Dev Mode):

```bash
# Clone the repository
git clone https://github.com/bradnunnally/ChatGPT-Micro-Cap-Experiment.git
cd ChatGPT-Micro-Cap-Experiment

# Install dependencies
pip install -r requirements.txt

## Launch the application (synthetic data, no network)
cp .env.example .env   # ensure APP_ENV=dev_stage
streamlit run app.py  # or: APP_ENV=dev_stage streamlit run app.py
```

By default in dev_stage the app now synthesizes ~90 calendar days (business-day sampled) of deterministic OHLCV data for any ticker you reference (seeded for reproducibility). Two extra illustrative tickers (e.g. NVDA, TSLA) are supported out of the box just like AAPL/MSFT—simply add them to your watchlist or trade them; synthetic history is generated on demand.

### Production (Real Data)

```bash
python app.py --env production
```

Strategy selection uses APP_ENV: `dev_stage` -> deterministic synthetic data (90d history window), `production` -> Finnhub with per-endpoint JSON caching under `data/cache`.

### Provider Architecture (Finnhub + Synthetic)

Legacy Yahoo Finance code has been removed. A unified provider layer now supports:

| Mode | Source | Usage |
| ---- | ------ | ----- |
| Production | Finnhub | Live quotes, profiles, news, earnings (API key required) |
| Development (`dev_stage`) | Synthetic | Deterministic OHLCV + placeholder fundamentals (offline) |

Automatic capability detection hides unsupported columns (e.g. Spread, ADV20) when plan lacks bid/ask or candles. Synthetic mode guarantees offline operation and stable test runs.

Caching (production):
- Quotes: 30s TTL
- Candles: 1h TTL
- Profile / News / Earnings / Bid-Ask: 1d TTL

The app will open at `http://localhost:8501` with a clean interface ready for portfolio management.

### Application Architecture:
- **Frontend**: Streamlit web interface with responsive design (Dashboard, Performance, Backtests, Watchlist, User Guide)
- **Backend**: Python services for trading, market data, portfolio management & analytics (risk + attribution)
- **Database**: SQLite for reliable local data persistence
- **Market Data**: Finnhub (production) or deterministic synthetic generator (dev)
- **Analytics Layer**: Risk metrics, PnL attribution, equity curve backtesting
- **Testing**: Comprehensive test suite (current ≈81% coverage, target ≥80%)

## 🛠️ Technical Stack

- **Python 3.13+** – Core application runtime
- **Streamlit** – Web UI
- **Pandas + NumPy** – Data manipulation & analytics
- **Plotly** – Interactive visualizations (performance & backtests)
- **finnhub-python** – Production market data (pluggable providers)
- **SQLite** – Local persistence
- **Typer** – CLI (snapshot, metrics, backtest, import/export)
- **Pytest + Coverage** – Test harness (≥80% enforced)

## 📁 Project Structure

```
ChatGPT-Micro-Cap-Experiment/
├── app.py                      # Main Streamlit application entry point
├── config/                     # Configuration package (settings & providers)
├── portfolio.py                # Portfolio management logic
├── requirements.txt            # Python dependencies
├── pytest.ini                 # Pytest configuration
├── .streamlit/config.toml      # Streamlit configuration
├── components/                 # Reusable UI components
│   └── nav.py                  # Navigation component
├── data/                       # Data management layer
│   ├── db.py                   # Database connection and operations
│   ├── portfolio.py            # Portfolio data models
│   ├── watchlist.py            # Watchlist data models
│   └── trading.db              # SQLite database file
├── pages/                      # Streamlit pages
│   ├── user_guide_page.py       # User guide and help page
│   ├── performance_page.py     # Portfolio performance analytics (risk + attribution)
│   ├── backtest_page.py        # Interactive strategy backtesting
│   └── watchlist.py            # Stock watchlist management
├── services/                   # Business logic layer
│   ├── logging.py              # Application logging
│   ├── market.py               # Market data services (metrics + circuit breaker)
│   ├── risk.py                 # Risk metrics & PnL attribution utilities
│   ├── backtest.py             # Simple SMA backtest scaffold
│   ├── money.py                # Money value object & formatting
│   ├── portfolio_service.py    # Portfolio business logic
│   ├── session.py              # Session management
│   ├── trading.py              # Trading operations
│   └── watchlist_service.py    # Watchlist business logic
├── ui/                         # UI components and layouts
│   ├── cash.py                 # Cash management interface
│   ├── dashboard.py            # Main dashboard interface
│   ├── forms.py                # Trading forms
│   ├── summary.py              # Portfolio summary views
│   └── user_guide.py           # User guide content
├── tests/                      # Test suite (~89% coverage)
│   ├── conftest.py             # Pytest configuration
│   ├── test_*.py               # Individual test files
│   └── mock_streamlit.py       # Streamlit mocking utilities
├── scripts/                    # Development and utility scripts
│   └── run_tests_with_coverage.py  # Test runner with coverage
├── archive/                    # Archived legacy scripts
│   ├── generate_graph.py       # Legacy data visualization
│   └── migrate_csv_to_sqlite.py    # Legacy data migration
└── docs/                       # Documentation and analysis
    ├── experiment_details/     # Detailed experiment documentation
    └── results-6-30-7-25.png   # Performance results
```

## 🧪 Development & Testing

### Quick dev setup

```bash
make install   # create .venv and install deps + dev tools
make lint      # ruff + black check + mypy (scoped)
make test      # run pytest
make run       # streamlit run app.py
```

Notes:
- Python 3.13 is expected; a local .venv is used by Makefile targets.
- Ruff is configured to sort imports and ignore style in tests; run `ruff --fix` to auto-apply safe fixes.
- Mypy is run on `services/core/*` for a clean, incremental type baseline; expand scope later as desired.

CI: A GitHub Actions workflow runs lint, type-checks, and tests on PRs to `dev_stage` and `main`.

Core validation and models: shared validators live in `services/core/validation.py` and are consumed by immutable dataclasses in `services/core/models.py`. Trading helpers delegate to these validators while keeping legacy boolean return semantics.

### Running Tests:
```bash
# Run full test suite
pytest

# Run with coverage report
pytest --cov=. --cov-report=html

# Run test suite with coverage helper script
python scripts/run_tests_with_coverage.py

# Run specific test file
pytest tests/test_portfolio_manager.py
```

### Code Quality:
- **~82% Test Coverage (≥80% gate)** – Broad testing across services, data layer & analytics
- **Type Hints** – Progressive typing of core & analytics modules
- **Modular Architecture** – Clear separation (UI / services / data / analytics)
- **Resilience & Observability** – Circuit breaker + metrics persistence for price fetching

## 🧪 Multi-Strategy Allocation (Phase 7)

Phase 7 adds a complete multi‑strategy portfolio construction and execution loop:

Core modules:
- `services/strategy.py` – Registry, capital weighting, combination, delta & order generation, weight capping utilities
- `services/regime.py` – Lightweight regime classifier (bull / bear / high_vol / sideways / unknown)
- `services/rebalance.py` – Order execution engine (scaling, partial fills, slippage modeling, trade logging)
- `pages/strategies_page.py` – Streamlit UI for end‑to‑end workflow

Implemented capabilities:
1. Strategy Registry
  - Register/unregister strategies (equal-weight + top‑N momentum reference implementations)
  - Toggle active status & set per‑strategy capital weights (auto-normalized)
  - Persistence to SQLite (`strategy_registry` table) with parameter round‑trip
2. Allocation Combination
  - Capital‑weighted blend of raw strategy targets → composite weights
  - Normalization over positive weights; fallback to absolute sum if all non‑positive
3. Risk & Constraints (initial overlays)
  - Per‑ticker max weight cap (`cap_composite_weights`)
  - Sector aggregate cap (`apply_sector_caps`) with proportional re-scaling when breached
4. Regime Awareness
  - Heuristic regime detection surfaced in UI
  - One‑click regime heuristic to adjust capital weights (e.g., damp momentum in high_vol)
5. Delta & Order Pipeline
  - Compute per‑ticker value & shares deltas vs targets (`compute_allocation_deltas`)
  - Materiality filters: min shares, min value, weight tolerance (`generate_rebalance_orders`)
6. Execution Engine
  - Proportional scaling of buys if aggregate cost exceeds cash
  - Optional partial fills for insufficient cash / shares
  - Dry‑run mode (no state mutation or trade log writes)
  - Slippage (bps) adjustment and slippage cost attribution per order
  - Trade log integration (persisted via existing `append_trade_log`)
7. UI Integration
  - Strategy management, regime display, capital input controls
  - Composite allocation & per‑strategy contribution detail
  - Orders preview + execution panel (slippage, partials, scaling, dry‑run)
8. Test Coverage
  - Unit tests for registry, regime fallback, delta→orders, execution flow, caps, slippage cost

Example (minimal):
```python
from services.strategy import (
   StrategyContext, EqualWeightStrategy, TopNPriceMomentumStrategy,
   register_strategy, combine_strategy_targets, compute_allocation_deltas,
   generate_rebalance_orders
)
from services.rebalance import execute_orders

register_strategy(EqualWeightStrategy())
register_strategy(TopNPriceMomentumStrategy(top_n=3))
ctx = StrategyContext(as_of=pd.Timestamp.utcnow(), portfolio=portfolio_df, prices=latest_prices_df)
alloc_long = combine_strategy_targets(ctx=ctx, strategy_capital={"equal_weight":0.5, "mom_top3":0.5})
delta = compute_allocation_deltas(portfolio_df, alloc_long, price_map, total_equity)
orders = generate_rebalance_orders(delta, min_shares=1, min_value=5.0, weight_tolerance=0.001)
new_pf, new_cash, report = execute_orders(portfolio_df, cash, orders, slippage_bps=5)
```

Next phase ideas: volatility targeting, advanced factor momentum overlays, liquidity & turnover constraints, scenario stress testing, adaptive regime weight models.

## 🔍 Advanced Optimization & Overlays (Phase 9)

Phase 9 extends the allocation engine with lightweight, dependency‑minimal portfolio optimization and risk overlays designed for transparency and testability.

Core module: `services/optimization.py`

Implemented components:

1. Strategies
  - MeanVarianceStrategy (Σ⁻¹μ heuristic, inverse‑vol fallback when all weights collapse)
  - RiskParityStrategy (inverse volatility approximation)
  - MinVarianceStrategy (Σ⁻¹1 normalized; long‑only clamp)
  - ConstrainedRiskParityStrategy (iterative equal risk contribution with max weight & convergence tolerance)
2. Estimation Utilities
  - `estimate_returns` (mean / EMA) & `estimate_covariance` (sample with simple shrinkage)
  - `compute_factor_exposures` rolling OLS betas (no intercept) with stability guards (min obs, pseudo‑inverse fallback)
3. Overlays
  - Factor Neutralization (orthogonal projection; skips constant exposures; degeneracy fallback to original normalized weights)
  - Turnover Penalty (L1 soft‑threshold vs current using cost_bps * λ)
  - Volatility Cap (uniform scaling to target annual vol introducing implicit cash buffer)
  - Regime Risk Scaling (gross exposure dampening in high_vol / bear / sideways regimes before vol targeting)
4. Diagnostics
  - Expected returns, daily vol, correlations, pre/post weight deltas, factor betas, pre/post portfolio annual vol, gross exposure
5. Performance Profiling
  - `profile_optimization_pipeline` timing breakdown (returns, covariance, strategy eval, overlays)
6. Registration Helper
  - `register_phase9_strategies()` idempotently registers all optimization strategies
7. Tests & Quality
  - Dedicated optimization test suite + smoke tests (markers) covering estimators, overlays, fallback paths, volatility cap, regime scaling
  - Maintains overall coverage ≥80%

Example (factor neutralization & volatility cap):
```python
from services.optimization import (
   register_phase9_strategies, RiskParityStrategy, factor_neutral_overlay,
   compute_factor_exposures, apply_volatility_cap
)
from services.strategy import StrategyContext

register_phase9_strategies()
ctx = StrategyContext(as_of=pd.Timestamp.utcnow(), extra={"returns_history": asset_returns})
weights = RiskParityStrategy().target_weights(ctx)
exposures = compute_factor_exposures(asset_returns, factor_returns)
adj = factor_neutral_overlay(weights, exposures, exposures.columns)
scaled = apply_volatility_cap(adj, asset_returns, target_annual_vol_pct=15.0)
```

Profiling:
```python
from services.optimization import profile_optimization_pipeline, MeanVarianceStrategy
timings = profile_optimization_pipeline(asset_returns, [MeanVarianceStrategy()], ctx, overlays=True)
```

Future enhancements: convex solver integration for exact ERC / MV with constraints, liquidity & turnover budgeting, dynamic factor selection, adaptive shrinkage, regime‑aware target volatility, transaction cost preview UI.

## 📦 Local Snapshot Deployment (No Docker)

Create an immutable self-contained copy (code + its own virtualenv) you can launch independently of your dev workspace.

### Create a snapshot
```
make freeze VERSION=1.0.0
```
This produces: `dist/release-1.0.0/`

Contents:
- `app.py` and all source files
- `.venv/` isolated virtual environment
- `launch.sh` startup script
- `VERSION` file containing the version string

### Launch the snapshot
```
./dist/release-1.0.0/launch.sh
```
The script sets `APP_ENV=production` by default (override when calling: `APP_ENV=dev_stage ./dist/release-1.0.0/launch.sh`).

### Create new versions
```
make freeze VERSION=1.0.1
make freeze VERSION=1.0.2
```
Each run creates a fresh directory; older ones remain untouched for rollback/comparison.

### Optional: Compress and archive
```
tar -czf portfolio_release_v1.0.0.tgz -C dist release-1.0.0
```

### Clean up old snapshots
```
rm -rf dist/release-1.0.0
```

### Why this approach?
- Zero external dependencies (no Docker)
- Stable snapshot insulated from active development
- Simple rollback (keep previous folder)
- Fast rebuild time (rsync + pip install)

If you need a single-file binary later, you can explore PyInstaller—see project notes or ask for a recipe.
