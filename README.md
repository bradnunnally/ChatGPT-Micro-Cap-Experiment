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

### Key Features (Phases 1–6):
- **📱 Real-time Portfolio Dashboard** – Live tracking (Finnhub in production, synthetic in dev)
- **📈 Performance Analytics** – Historical charts, KPIs, extended risk metrics (MDD, rolling volatility, Sharpe*, Sortino*, beta≈1 placeholder, concentration, VaR/ES 95 & 99, rolling multi-window betas, correlation matrix, VaR95 hit ratio, position VaR contributions)
- **🧩 PnL Attribution** – In‑memory per‑position decomposition (price vs position effect) displayed on Performance page
- **🧪 Backtest Sandbox** – SMA crossover strategy runner with equity curve & signals (see Backtests page) plus train/test overfit guard & scheduled mini SMA grid sweeps (rotating leaderboard snapshots)
- **🎯 Price Source Provenance** – Badge + raw code (BULK/API/MANUAL/ZERO/INIT) for transparency into pricing path
- **💰 Trading Interface** – Buy/sell stocks with validation & audit logging
- **👁️ Watchlist Management** – Track potential investments with Money formatting
- **💵 Money Value Object** – Centralized decimal‑safe currency handling and formatting
- ** Data Export** – Download snapshots & history
- **⏱️ In‑App Scheduler** – Benchmark & risk‑free refresh, portfolio snapshots, fundamentals cache, periodic SMA grid mini‑backtests, alert evaluation
- **🚨 Risk Alerts** – Threshold alerts (drawdown, top1 concentration, VaR95) with persisted log + state panel in UI
- **🗄️ SQLite Database** – Persistent local data storage

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
- **Testing**: Comprehensive test suite (current ≈82% coverage, target ≥80%)

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
- **Error Handling** – Domain error taxonomy with UI-friendly surfacing

## � Logging & Errors

This project emits structured JSON logs to stdout for easy ingestion and analysis.

- Format: one JSON object per line, including timestamp, level, message, logger, and correlation_id.
- Correlation ID: a stable ID is set per Streamlit session; CLI tools generate a new one per run. You can also set a temporary ID via a context manager for specific actions.
- Audit Trail: trades and domain events are recorded via an audit logger for traceability.

Key APIs
- Logging helpers live in `infra/logging.py`:
    - `get_logger(name)`: standard JSON logger
    - `get_correlation_id()`, `set_correlation_id(cid)`, `new_correlation_id()`
    - `audit.trade(action, *, ticker, shares, price, status="success", reason=None, **extra)`
    - `audit.event(name, **attrs)`

Domain Errors
- Centralized in `core/errors.py` and used across services/UI/CLI:
    - `ValidationError` (subclasses `ValueError`) – invalid user/model input
    - `MarketDataDownloadError` (subclasses `RuntimeError`) – download failures
    - `NoMarketDataError` (subclasses `ValueError`) – no market data available
    - `RepositoryError` (subclasses `RuntimeError`) – DB/repository failures
    - `ConfigError`, `NotFoundError`, `PermissionError` – additional categories
- Legacy shim: `services/exceptions/validation.ValidationError` aliases `core.errors.ValidationError` for backward compatibility.

Usage conventions
- Always raise domain-specific exceptions from services.
- UI/CLI layers should catch domain errors, log them (JSON), surface user-friendly messages, and avoid raw tracebacks in logs.
- Streamlit app seeds a session-level `correlation_id` so logs from interactions can be traced end-to-end.

Example patterns (conceptual)
- Create a logger: `logger = get_logger(__name__)`
- Emit audit entry: `audit.trade("buy", ticker="AAPL", shares=10, price=150.0, status="success")`
- Set a scoped correlation ID in scripts: `with new_correlation_id(): ...`

## �🔧 Configuration

The application uses SQLite for data storage in the `data/` directory. Configuration options are available in:
- `.streamlit/config.toml` - Streamlit app configuration and theming
- `pytest.ini` - Test configuration and coverage settings

## 📖 Usage Guide

### First Time Setup:
1. **Launch Application**: Run `streamlit run app.py`
2. **Add Initial Cash**: Use the cash management section to fund your account
3. **Start Trading**: Buy your first stocks using the trading interface
4. **Track Performance**: Monitor your portfolio's performance over time

### Daily Workflow:
- **Monitor Dashboard** – Positions, weights, ROI %, price source badges
- **Review Watchlist** – Track candidates with live/synthetic prices
- **Execute Trades** – Use trading forms (PnL updates in snapshot)
- **Analyze Performance** – Performance page: KPIs, extended risk, attribution table
- **Run Backtests** – Backtests page: choose ticker or TOTAL equity, set SMA windows
- **Export / Archive** – CLI or UI export for history snapshots

### Backtests Page
The Backtests page lets you experiment with a simple SMA crossover strategy:
1. Select a ticker (or use `TOTAL` to treat portfolio equity as the price series)
2. Choose fast / slow moving average windows
3. Run to view equity curve, performance metrics, and signal table

### Risk, Benchmark & Attribution
Risk metrics include:
- Max Drawdown, Rolling 20d Volatility, Sharpe (excess over daily risk-free), Sortino (excess downside), Beta (vs benchmark), Top 1 / Top 3 concentration.
    - Benchmark: Daily closes for SPY pulled from Stooq (no key) and cached locally under `data/benchmarks/SPY.json` (auto-refresh first access per UTC day or via CLI).
    - Risk-Free: Layered resolution: FRED 3M T-Bill (DGS3MO) if `FRED_API_KEY` set → `RISK_FREE_ANNUAL` environment override → 0.0. Cached per day at `data/risk_free.json`.
    - Daily risk-free used = annual / 252. Sharpe & Sortino use excess returns (return - rf_daily).
    - Beta falls back to self-beta (~1) if insufficient overlapping history ( <5 aligned daily points).
PnL attribution decomposes per-position change into:
- `pnl_price`: Prior shares * (Δ average cost proxy)
- `pnl_position`: (Δ shares) * current buy price proxy
- `pnl_total_attr`: Sum of the two (in-memory only; not persisted to DB yet)

#### Benchmark & Risk-Free CLI Helpers
```bash
make cli-benchmark   # Force benchmark refresh (SPY)
make cli-risk-free   # Show today's resolved risk-free annual rate
```
Environment overrides:
```bash
export FRED_API_KEY=YOUR_KEY_HERE
export RISK_FREE_ANNUAL=0.04   # 4% assumed annual rate if FRED not configured
```

### Price Source Codes
| Code | Meaning |
|------|---------|
| BULK | Bulk price fetch succeeded |
| API | Individual API fallback |
| MANUAL | User-entered override |
| ZERO | No price found → 0.0 placeholder |
| INIT | Initial placeholder before resolution |

Badges appear beside each position for rapid provenance inspection.

### Money Handling
`services/money.py` supplies a `Money` value object and `format_money` helper for consistent rounding (quantized to cents) across Dashboard, Watchlist, and Performance KPIs.

## 🚨 Important Notes

- **Live Market Data (production)**: Finnhub quotes subject to plan limits
- **Synthetic Mode**: Guarantees zero external calls (`APP_ENV=dev_stage`)
- **Data Persistence**: All portfolio data stored locally (SQLite)
- **Risk Management**: Always maintain appropriate position sizing and risk controls
- **Educational Purpose**: This application is for educational and experimental use

## 📌 Benchmark & Risk-Free Summary

| Component  | Default | Source            | Cache Path                     | Refresh                                |
|------------|---------|-------------------|--------------------------------|----------------------------------------|
| Benchmark  | SPY     | Stooq daily CSV   | `data/benchmarks/SPY.json`     | Auto (first access per day) / CLI      |
| Risk-Free  | DGS3MO  | FRED (if API key) | `data/risk_free.json`          | Auto (first access per day) / CLI      |

Fallback chain for risk-free: FRED → `RISK_FREE_ANNUAL` env (decimal) → 0.0. Daily equivalent = annual / 252.

## 📈 Experiment Status

**Timeline**: June 2025 - December 2025  
**Starting Capital**: $100  
**Current Status**: Active trading with performance tracking  
**Updates**: Weekly performance reports published on [SubStack](https://nathanbsmith729.substack.com)

## 🤝 Contributing

Feel free to:
- Report bugs or suggest improvements
- Submit pull requests for new features
- Use this as a blueprint for your own experiments
- Share feedback and results

## 📞 Contact

- **Email**: nathanbsmith.business@gmail.com
- **Blog**: [SubStack Updates](https://substack.com/@nathanbsmith)
- **Issues**: GitHub Issues for bug reports and feature requests

---

*Disclaimer: This is an experimental project for educational purposes. Past performance does not guarantee future results. Please invest responsibly.*

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
