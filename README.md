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

### Quick Start:

```bash
# Clone the repository
git clone https://github.com/bradnunnally/ChatGPT-Micro-Cap-Experiment.git
cd ChatGPT-Micro-Cap-Experiment

# Install dependencies
pip install -r requirements.txt

# Launch the application
streamlit run app.py
```

The app will open at `http://localhost:8501` with a clean interface ready for portfolio management.

### Application Architecture:
- **Frontend**: Streamlit web interface with responsive design
- **Backend**: Python services for trading, market data, and portfolio management  
- **Database**: SQLite for reliable local data persistence
- **Market Data**: Yahoo Finance integration for real-time stock prices
- **Testing**: Comprehensive test suite with 82% coverage

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
├── config.py                   # Configuration settings and constants
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
├── tests/                      # Test suite (82% coverage)
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
- **82% Test Coverage** - Comprehensive testing across all major modules
- **Type Hints** - Full type annotation for better code reliability
- **Modular Architecture** - Clean separation of concerns
- **Error Handling** - Robust error handling and user feedback

## 🔧 Configuration

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
