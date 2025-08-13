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

### Key Features:
- **📱 Real-time Portfolio Dashboard** - Live portfolio tracking with current values and P&L
- **📈 Performance Analytics** - Historical charts, KPIs, and performance metrics  
- **💰 Trading Interface** - Buy/sell stocks with real-time price validation
- **👁️ Watchlist Management** - Track potential investments and market opportunities
- **📊 Data Export** - Download portfolio snapshots and historical data
- **🗄️ SQLite Database** - Persistent local data storage

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

Strategy selection uses APP_ENV: dev_stage -> deterministic synthetic data (90d history window), production -> Finnhub with a small JSON cache in data/cache for the included micro CLI app.

### Minimal CLI App (Finnhub integration)

This repo now includes a tiny standalone CLI (`micro_app.py`) that demonstrates using Finnhub in production and a synthetic provider in dev.

Setup:

```bash
pip install -r requirements.txt
cp .env.example .env  # set APP_ENV and FINNHUB_API_KEY for production
```

Usage examples:

```bash
# Dev mode (no network): seeds AAA/BBB demo portfolio on first run
APP_ENV=dev_stage python micro_app.py show

# Production (requires FINNHUB_API_KEY in env or .env)
APP_ENV=production FINNHUB_API_KEY=... python micro_app.py add AAPL 1 200 --stop 180
APP_ENV=production python micro_app.py show
APP_ENV=production python micro_app.py remove AAPL
```

Caching (production):
- quotes: quote_{ticker}.json (30s TTL)
- candles: candles_{ticker}_{start}_{end}.json (1h TTL)
- profile: profile_{ticker}.json (1d TTL)
- news/earnings/bid-ask: 1d TTL
```

The app will open at `http://localhost:8501` with a clean interface ready for portfolio management.

### Application Architecture:
- **Frontend**: Streamlit web interface with responsive design
- **Backend**: Python services for trading, market data, and portfolio management  
- **Database**: SQLite for reliable local data persistence
- **Market Data**: Yahoo Finance integration for real-time stock prices
- **Testing**: Comprehensive test suite with ~89% coverage (target ≥80%)

## 🛠️ Technical Stack

- **Python 3.13+** - Core application runtime
- **Streamlit** - Modern web application framework
- **Pandas + NumPy** - Data manipulation and analysis
- **yFinance** - Real-time market data integration
- **SQLite** - Local database for data persistence
- **Plotly** - Interactive data visualizations
- **Pytest** - Comprehensive testing framework

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
│   ├── performance_page.py     # Portfolio performance analytics
│   └── watchlist.py            # Stock watchlist management
├── services/                   # Business logic layer
│   ├── logging.py              # Application logging
│   ├── market.py               # Market data services
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
- **~89% Test Coverage** - Comprehensive testing across all major modules
- **Type Hints** - Full type annotation for better code reliability
- **Modular Architecture** - Clean separation of concerns
- **Error Handling** - Robust error handling and user feedback

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
- **Monitor Dashboard**: Check current positions and P&L
- **Review Watchlist**: Track potential investment opportunities  
- **Execute Trades**: Buy/sell positions based on your strategy
- **Analyze Performance**: Review historical performance and metrics

## 🚨 Important Notes

- **Live Market Data**: Prices update in real-time during market hours
- **Data Persistence**: All portfolio data is stored locally and persists between sessions
- **Risk Management**: Always maintain appropriate position sizing and risk controls
- **Educational Purpose**: This application is for educational and experimental use

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
