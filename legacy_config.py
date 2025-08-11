from pathlib import Path

from portfolio import PORTFOLIO_COLUMNS
from services.time import get_clock

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

PORTFOLIO_CSV = DATA_DIR / "chatgpt_portfolio_update.csv"
TRADE_LOG_CSV = DATA_DIR / "chatgpt_trade_log.csv"
WATCHLIST_FILE = DATA_DIR / "watchlist.json"

# SQLite database used for persistent storage of the portfolio and trade logs.
# The CSV paths above remain for backwards compatibility and migration only.
DB_FILE = DATA_DIR / "trading.db"

COL_TICKER, COL_SHARES, COL_STOP, COL_PRICE, COL_COST = PORTFOLIO_COLUMNS

TODAY = get_clock().today().strftime("%Y-%m-%d")
