import pandas as pd

from config import COL_COST, COL_PRICE, COL_SHARES, COL_STOP, COL_TICKER, TODAY
from config.providers import is_dev_stage
from data.db import get_connection, init_db
from portfolio import ensure_schema

from services.core.portfolio_service import compute_snapshot as _compute_snapshot
from services.market import fetch_prices
import os


class PortfolioResult(pd.DataFrame):
    """A DataFrame that also unpacks into (portfolio_df, cash, is_first_time).

    This helps satisfy tests that expect load_portfolio to return a DataFrame in some
    cases and a tuple in others.
    """

    _metadata = ["cash", "is_first_time"]

    def __init__(self, data, cash: float, is_first_time: bool):
        super().__init__(data)
        self.cash = float(cash)
        self.is_first_time = bool(is_first_time)

    def __iter__(self):  # type: ignore[override]
        # Allows: portfolio, cash, is_first_time = load_portfolio()
        yield pd.DataFrame(self).copy()
        yield self.cash
        yield self.is_first_time


def _ensure_database_ready() -> None:
    """Initialize database connection and schema.
    
    Raises:
        RepositoryError: If database initialization fails
    """
    from core.error_utils import log_and_raise_domain_error
    from core.errors import RepositoryError
    from infra.logging import get_logger
    
    logger = get_logger(__name__)
    try:
        init_db()
    except Exception as exc:
        log_and_raise_domain_error(
            logger, exc, RepositoryError, "database_initialization"
        )


def _load_portfolio_from_database(portfolio_id: int | None = None) -> tuple[pd.DataFrame, float | None]:
    """Load portfolio and cash data from database for a specific portfolio.
    
    Args:
        portfolio_id: Portfolio ID to load. If None, uses current portfolio context.
    
    Returns:
        Tuple of (portfolio_df, cash_balance) where cash_balance is None if not found
        
    Raises:
        RepositoryError: If database access fails
    """
    from core.error_utils import log_and_raise_domain_error
    from core.errors import RepositoryError
    from infra.logging import get_logger
    from services.portfolio_service import ensure_portfolio_context_in_queries
    
    logger = get_logger(__name__)
    
    # Get portfolio ID from context if not provided (maintains backward compatibility)
    if portfolio_id is None:
        portfolio_id = ensure_portfolio_context_in_queries()
    
    try:
        with get_connection() as conn:
            try:
                # Load portfolio data for specific portfolio
                portfolio_df = pd.read_sql_query(
                    "SELECT ticker, shares, stop_loss, buy_price, cost_basis FROM portfolio WHERE portfolio_id = ?", 
                    conn, params=(portfolio_id,)
                )
            except Exception:
                # Fallback for tests that provide a mocked connection
                rows = conn.execute(
                    "SELECT ticker, shares, stop_loss, buy_price, cost_basis FROM portfolio WHERE portfolio_id = ?",
                    (portfolio_id,)
                ).fetchall()
                portfolio_df = pd.DataFrame(
                    rows, columns=["ticker", "shares", "stop_loss", "buy_price", "cost_basis"]
                ).copy()
            
            try:
                cash_row = conn.execute("SELECT balance FROM cash WHERE portfolio_id = ?", (portfolio_id,)).fetchone()
                cash_balance = float(cash_row[0]) if cash_row is not None else None
            except Exception:
                cash_balance = None
                
        return portfolio_df, cash_balance
        
    except Exception as exc:
        log_and_raise_domain_error(
            logger, exc, RepositoryError, "portfolio_database_load"
        )


def _enrich_portfolio_with_current_prices(portfolio_df: pd.DataFrame) -> pd.DataFrame:
    """Add current price and percentage change data to portfolio.
    
    Args:
        portfolio_df: Portfolio DataFrame to enrich with price data
        
    Returns:
        Portfolio DataFrame with current_price and pct_change columns added
        
    Raises:
        MarketDataError: If price fetching fails completely
    """
    from core.error_utils import log_and_return_default
    from core.errors import MarketDataError
    from infra.logging import get_logger
    
    logger = get_logger(__name__)
    
    if portfolio_df.empty:
        # Ensure columns exist even when empty
        portfolio_df = portfolio_df.copy()
        portfolio_df["current_price"] = pd.Series(dtype=float)
        portfolio_df["pct_change"] = pd.Series(dtype=float)
        return portfolio_df
    
    # Try bulk price fetch first
    try:
        prices_df = fetch_prices(portfolio_df[COL_TICKER].tolist())
        if not prices_df.empty:
            portfolio_with_prices = portfolio_df.merge(
                prices_df[["ticker", "current_price", "pct_change"]],
                on="ticker",
                how="left",
            )
            return portfolio_with_prices
    except Exception as exc:
        logger.warning("Bulk price fetch failed, attempting individual lookups", extra={
            "operation": "bulk_price_fetch",
            "exception_type": type(exc).__name__,
            "exception_message": str(exc)
        })
    
    # Fall back to individual price lookups
    from services.market import get_current_price
    
    portfolio_with_prices = portfolio_df.copy()
    current_prices = []
    
    for ticker in portfolio_df[COL_TICKER].tolist():
        try:
            price = get_current_price(ticker)
            current_prices.append(price if price is not None else 0.0)
            if price is not None:
                logger.info(f"Individual price loaded for {ticker}: ${price}")
        except Exception as exc:
            logger.warning(f"Individual price fetch failed for {ticker}", extra={
                "ticker": ticker,
                "exception_type": type(exc).__name__,
                "exception_message": str(exc)
            })
            current_prices.append(0.0)
    
    portfolio_with_prices["current_price"] = current_prices
    portfolio_with_prices["pct_change"] = 0.0
    return portfolio_with_prices


def _seed_initial_portfolio_if_empty(portfolio_df: pd.DataFrame, cash_balance: float | None, depth: int) -> bool:
    """Seed sample data if portfolio is empty and in dev stage.
    
    Args:
        portfolio_df: Current portfolio DataFrame
        cash_balance: Current cash balance (None if not set)
        depth: Recursion depth to prevent infinite loops
        
    Returns:
        True if seeding was performed, False otherwise
        
    Raises:
        RepositoryError: If database seeding fails
    """
    from core.error_utils import log_and_return_default
    from core.errors import RepositoryError
    from infra.logging import get_logger
    
    logger = get_logger(__name__)
    
    if not (portfolio_df.empty and cash_balance is None):
        return False
        
    if not (is_dev_stage() and depth == 0 and os.getenv("NO_DEV_SEED") != "1"):
        return False
    
    try:
        _seed_dev_stage_portfolio()
        return True
    except Exception as exc:
        log_and_return_default(
            logger, exc, False, "dev_stage_portfolio_seeding"
        )
        return False


def load_portfolio(_depth: int = 0) -> PortfolioResult:
    """Load the complete portfolio from database with current market data.

    Returns a PortfolioResult containing:
    - portfolio DataFrame with current prices and percentage changes
    - current cash balance
    - boolean indicating if portfolio was initially empty

    Handles seeding of sample data in dev stage when portfolio is empty.
    Gracefully handles missing market data by falling back to individual price lookups.
    """

    from core.error_utils import log_and_return_default
    from infra.logging import get_logger
    
    logger = get_logger(__name__)
    empty_portfolio = pd.DataFrame(columns=ensure_schema(pd.DataFrame()).columns)

    try:
        # Step 1: Ensure database is ready
        _ensure_database_ready()
        
        # Step 2: Load existing portfolio and cash data
        portfolio_df, cash_balance = _load_portfolio_from_database()
        
        # Step 3: Handle empty portfolio seeding
        if _seed_initial_portfolio_if_empty(portfolio_df, cash_balance, _depth):
            return load_portfolio(_depth=1)
        
        # Step 4: Handle truly empty portfolio
        if portfolio_df.empty and cash_balance is None:
            return PortfolioResult(empty_portfolio, 0.0, True)
        
        # Step 5: Ensure schema and enrich with current prices
        portfolio = ensure_schema(portfolio_df) if not portfolio_df.empty else empty_portfolio
        portfolio_with_prices = _enrich_portfolio_with_current_prices(portfolio)
        
        # Step 6: Prepare final result
        final_cash = cash_balance if cash_balance is not None else 0.0
        was_initially_empty = portfolio_df.empty
        
        return PortfolioResult(portfolio_with_prices, final_cash, was_initially_empty)
        
    except Exception as exc:
        # Log error and return safe defaults to maintain existing API contract
        return log_and_return_default(
            logger, exc, PortfolioResult(empty_portfolio, 0.0, True), "load_portfolio"
        )


def _seed_dev_stage_portfolio() -> None:
    """Seed a minimal synthetic portfolio and snapshot for dev_stage if DB is empty.

    Creates a couple of micro-cap placeholder positions plus a starting cash balance
    so the UI shows meaningful data without any manual input. Idempotent: only runs
    when the portfolio table is empty and cash not yet set.
    """
    try:
        init_db()
        from services.portfolio_service import ensure_portfolio_context_in_queries
        portfolio_id = ensure_portfolio_context_in_queries()
        
        with get_connection() as conn:
            existing = conn.execute("SELECT COUNT(*) FROM portfolio WHERE portfolio_id = ?", (portfolio_id,)).fetchone()[0]
            cash_row = conn.execute("SELECT balance FROM cash WHERE portfolio_id = ?", (portfolio_id,)).fetchone()
            if existing > 0 or cash_row is not None:
                return
            seed_rows = [
                ("SYNAAA", 100.0, 4.50, 5.00, 500.0),  # ticker, shares, stop_loss, buy_price, cost_basis
                ("SYNBBB", 50.0, 7.25, 8.00, 400.0),
            ]
            for r in seed_rows:
                conn.execute(
                    "INSERT INTO portfolio (ticker, shares, stop_loss, buy_price, cost_basis, portfolio_id) VALUES (?, ?, ?, ?, ?, ?)",
                    r + (portfolio_id,),
                )
            # Seed starting cash
            conn.execute("INSERT OR REPLACE INTO cash (id, balance, portfolio_id) VALUES (0, ?, ?)", (10_000.00, portfolio_id))
            # Generate deterministic multi-day history inline for tests
            from datetime import datetime, timedelta
            total_equity_static = 10_000.00 + sum(x[1] * x[3] for x in seed_rows)
            for days_ago in range(20, 0, -1):
                date_str = (datetime.utcnow() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
                for r in seed_rows:
                    shares = r[1]
                    buy_price = r[3]
                    current_price = buy_price * (1 + 0.01 * (20 - days_ago))
                    value = shares * current_price
                    conn.execute(
                        "INSERT INTO portfolio_history (date, ticker, shares, cost_basis, stop_loss, current_price, total_value, pnl, action, cash_balance, total_equity, portfolio_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            date_str,
                            r[0],
                            shares,
                            buy_price,
                            r[2],
                            current_price,
                            value,
                            0.0,
                            "HOLD",
                            "",
                            "",
                            portfolio_id,
                        ),
                    )
                conn.execute(
                    "INSERT INTO portfolio_history (date, ticker, shares, cost_basis, stop_loss, current_price, total_value, pnl, action, cash_balance, total_equity, portfolio_id) VALUES (?, 'TOTAL', '', '', '', '', ?, 0.0, '', ?, ?, ?)",
                    (
                        date_str,
                        sum(x[1] * x[3] for x in seed_rows),
                        10_000.00,
                        total_equity_static,
                        portfolio_id,
                    ),
                )
    except Exception:
        # Best-effort; failures here should not break application startup
        pass


def _generate_historical_data(days_back: int = 30) -> None:
    """Generate historical portfolio snapshots for realistic data visualization."""
    try:
        from datetime import datetime, timedelta
        import random
        
        with get_connection() as conn:
            # Check if historical data already exists
            existing_count = conn.execute(
                "SELECT COUNT(DISTINCT date) FROM portfolio_history WHERE date != ? AND ticker != 'TOTAL'",
                (datetime.now().strftime("%Y-%m-%d"),)
            ).fetchone()[0]
            
            if existing_count >= days_back // 2:
                return  # Historical data already exists
            
            # Base positions and prices for simulation
            base_positions = [
                {"ticker": "SYNAAA", "shares": 100.0, "buy_price": 5.0, "stop_loss": 4.5},
                {"ticker": "SYNBBB", "shares": 50.0, "buy_price": 8.0, "stop_loss": 7.25},
            ]
            cash_balance = 10000.0
            base_prices = {"SYNAAA": 5.0, "SYNBBB": 8.0}
            
            # Clear existing historical data (keep today's)
            today = datetime.now().strftime("%Y-%m-%d")
            conn.execute("DELETE FROM portfolio_history WHERE date != ?", (today,))
            
            # Generate historical data
            for i in range(days_back, 0, -1):
                date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
                total_value = 0.0
                total_pnl = 0.0
                
                for pos in base_positions:
                    ticker = pos["ticker"]
                    shares = pos["shares"]
                    buy_price = pos["buy_price"]
                    stop_loss = pos["stop_loss"]
                    
                    # Generate realistic price movement
                    days_from_start = days_back - i
                    trend_factor = 1 + (days_from_start * 0.02)  # 2% growth per day on average
                    volatility = random.uniform(0.85, 1.15)  # ±15% daily volatility
                    current_price = base_prices[ticker] * trend_factor * volatility
                    current_price = max(current_price, buy_price * 0.5)  # Floor price
                    
                    value = round(current_price * shares, 2)
                    pnl = round((current_price - buy_price) * shares, 2)
                    
                    total_value += value
                    total_pnl += pnl
                    
                    # Insert position row
                    conn.execute("""
                        INSERT INTO portfolio_history 
                        (date, ticker, shares, cost_basis, stop_loss, current_price, total_value, pnl, action, cash_balance, total_equity)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        date, ticker, shares, buy_price, stop_loss, current_price, value, pnl, "HOLD", "", ""
                    ))
                
                # Insert TOTAL row
                total_equity = total_value + cash_balance
                conn.execute("""
                    INSERT INTO portfolio_history 
                    (date, ticker, shares, cost_basis, stop_loss, current_price, total_value, pnl, action, cash_balance, total_equity)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    date, "TOTAL", "", "", "", "", round(total_value, 2), round(total_pnl, 2), "", round(cash_balance, 2), round(total_equity, 2)
                ))
    except Exception:
        pass  # Best-effort historical data generation


def load_cash_balance() -> float:
    """Return cash balance from DB or 0.0 if missing."""
    init_db()
    with get_connection() as conn:
        row = conn.execute("SELECT balance FROM cash WHERE id = 0").fetchone()
    return float(row[0]) if row else 0.0


def save_portfolio_snapshot(portfolio_df: pd.DataFrame, cash: float) -> pd.DataFrame:
    """Recalculate today's portfolio values and persist them to the database.

    This function orchestrates the complete portfolio snapshot process:
    1. Fetches current market prices for all tickers
    2. Computes portfolio snapshot with all metrics
    3. Persists data to database
    4. Returns UI-friendly snapshot DataFrame
    
    Args:
        portfolio_df: Current portfolio positions
        cash: Current cash balance
        
    Returns:
        Computed snapshot DataFrame with current prices and metrics
    """
    # Step 1: Fetch current prices for all tickers
    tickers = portfolio_df[COL_TICKER].tolist()
    prices = _fetch_current_prices(tickers)
    
    # Step 2: Compute portfolio snapshot with current prices
    snapshot_df = _compute_portfolio_snapshot(portfolio_df, prices, cash)
    
    # Step 3: Persist complete snapshot to database
    _save_snapshot_to_database(portfolio_df, snapshot_df, cash)
    
    # Return UI-friendly snapshot
    return snapshot_df


def _fetch_current_prices(tickers: list[str]) -> dict[str, float]:
    """Fetch current prices for the given tickers.
    
    Args:
        tickers: List of ticker symbols
        
    Returns:
        Dict mapping tickers to current prices
    """
    from services.price_fetching import get_current_prices_for_portfolio
    return get_current_prices_for_portfolio(tickers)


def _compute_portfolio_snapshot(portfolio_df: pd.DataFrame, prices: dict[str, float], cash: float) -> pd.DataFrame:
    """Compute portfolio snapshot with current prices and metrics.
    
    Args:
        portfolio_df: Portfolio positions
        prices: Current prices for tickers
        cash: Cash balance
        
    Returns:
        Computed snapshot DataFrame
    """
    from services.data_persistence import transform_for_snapshot_input, transform_snapshot_output
    
    # Transform input data for compute_snapshot
    input_df = transform_for_snapshot_input(portfolio_df)
    
    # Compute snapshot using pure business logic
    raw_snapshot = _compute_snapshot(input_df, prices, cash, TODAY)
    
    # Transform output for UI/database compatibility
    return transform_snapshot_output(raw_snapshot)


def _save_snapshot_to_database(portfolio_df: pd.DataFrame, snapshot_df: pd.DataFrame, cash: float) -> None:
    """Save complete portfolio snapshot to database.
    
    Args:
        portfolio_df: Current portfolio positions
        snapshot_df: Computed snapshot
        cash: Cash balance
    """
    from services.data_persistence import save_portfolio_data
    save_portfolio_data(portfolio_df, snapshot_df, cash)


def load_portfolio_for_id(portfolio_id: int) -> tuple[pd.DataFrame, float]:
    """Load portfolio data for a specific portfolio ID.
    
    Args:
        portfolio_id: The portfolio ID to load
        
    Returns:
        Tuple of (portfolio_df, cash_balance)
    """
    try:
        _ensure_database_ready()
        
        with get_connection() as conn:
            # Load portfolio positions for the specific portfolio
            portfolio_query = """
                SELECT ticker, shares, stop_loss, buy_price, cost_basis 
                FROM portfolio 
                WHERE portfolio_id = ?
            """
            portfolio_df = pd.read_sql_query(portfolio_query, conn, params=(portfolio_id,))
            
            # Load cash balance for the specific portfolio
            cash_query = "SELECT balance FROM cash WHERE portfolio_id = ?"
            cash_result = conn.execute(cash_query, (portfolio_id,)).fetchone()
            cash_balance = cash_result[0] if cash_result else 0.0
            
            # Ensure schema and enrich with current prices if not empty
            if not portfolio_df.empty:
                portfolio_df = ensure_schema(portfolio_df)
                portfolio_df = _enrich_portfolio_with_current_prices(portfolio_df)
            else:
                portfolio_df = pd.DataFrame(columns=ensure_schema(pd.DataFrame()).columns)
            
            return portfolio_df, cash_balance
            
    except Exception as e:
        from infra.logging import get_logger
        logger = get_logger(__name__)
        logger.warning(f"Failed to load portfolio for ID {portfolio_id}: {e}")
        # Return empty portfolio on error
        empty_df = pd.DataFrame(columns=ensure_schema(pd.DataFrame()).columns)
        return empty_df, 0.0
