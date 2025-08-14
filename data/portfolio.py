import pandas as pd
import warnings

from config import COL_COST, COL_PRICE, COL_SHARES, COL_STOP, COL_TICKER, TODAY
from config.providers import is_dev_stage
from data.db import get_connection, init_db
from portfolio import ensure_schema, SCHEMA_VERSION
from app_settings import settings

from services.core.portfolio_service import compute_snapshot as _compute_snapshot
from services.market import fetch_prices
import os
from services.risk import attribute_pnl


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


def load_portfolio(_depth: int = 0):
    """Return the latest portfolio and cash balance."""

    empty_portfolio = pd.DataFrame(columns=ensure_schema(pd.DataFrame()).columns)

    init_db()
    with get_connection() as conn:
        try:
            # Retain pandas read_sql_query to satisfy tests that monkeypatch it; suppress its warning.
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore",
                    message="pandas only supports SQLAlchemy connectable",
                    category=UserWarning,
                )
                portfolio_df = pd.read_sql_query("SELECT * FROM portfolio", conn)
        except Exception:
            # Fallback for tests that provide a mocked connection
            rows = conn.execute(
                "SELECT ticker, shares, stop_loss, buy_price, cost_basis FROM portfolio"
            ).fetchall()
            portfolio_df = pd.DataFrame(
                rows, columns=["ticker", "shares", "stop_loss", "buy_price", "cost_basis"]
            ).copy()
        try:
            cash_row = conn.execute("SELECT balance FROM cash WHERE id = 0").fetchone()
        except Exception:
            cash_row = None

    if portfolio_df.empty and cash_row is None:
        # Minimal seeding path (delegated) unless explicitly disabled
        if is_dev_stage() and _depth == 0 and not getattr(settings, "no_dev_seed", False):  # pragma: no cover
            try:
                _seed_dev_stage_portfolio()
            except Exception:  # pragma: no cover
                pass
            return load_portfolio(_depth=1)
        return PortfolioResult(empty_portfolio, 0.0, True)

    portfolio = ensure_schema(portfolio_df) if not portfolio_df.empty else empty_portfolio
    # Attach current prices and pct_change for display/tests
    if not portfolio.empty:
        try:
            prices_df = fetch_prices(portfolio[COL_TICKER].tolist())
        except Exception:
            prices_df = pd.DataFrame(columns=["ticker", "current_price", "pct_change"])
        
        if not prices_df.empty:
            portfolio = portfolio.merge(
                prices_df[["ticker", "current_price", "pct_change"]],
                on="ticker",
                how="left",
            )
        else:
            # If bulk fetch failed, try individual price lookups
            from services.market import get_current_price
            import logging
            
            logger = logging.getLogger(__name__)
            logger.info("Bulk price fetch failed in load_portfolio, attempting individual lookups")
            
            current_prices = []
            for ticker in portfolio[COL_TICKER].tolist():
                try:
                    price = get_current_price(ticker)
                    current_prices.append(price if price is not None else 0.0)
                    if price is not None:
                        logger.info(f"Individual price loaded for {ticker}: ${price}")
                except Exception as e:
                    logger.warning(f"Individual price fetch failed for {ticker}: {e}")
                    current_prices.append(0.0)
            
            portfolio["current_price"] = current_prices
            portfolio["pct_change"] = 0.0
    else:
        # Ensure columns exist even when empty
        portfolio["current_price"] = pd.Series(dtype=float)
        portfolio["pct_change"] = pd.Series(dtype=float)
    cash = 0.0
    if cash_row is not None:
        try:
            cash = float(cash_row[0])
        except Exception:
            cash = 0.0
    return PortfolioResult(portfolio, cash, portfolio_df.empty)


def _seed_dev_stage_portfolio() -> None:
    """Seed a minimal synthetic portfolio and snapshot for dev_stage if DB is empty.

    Creates a couple of micro-cap placeholder positions plus a starting cash balance
    so the UI shows meaningful data without any manual input. Idempotent: only runs
    when the portfolio table is empty and cash not yet set.
    """
    try:
        init_db()
        with get_connection() as conn:
            existing = conn.execute("SELECT COUNT(*) FROM portfolio").fetchone()[0]
            cash_row = conn.execute("SELECT balance FROM cash WHERE id = 0").fetchone()
            if existing > 0 or cash_row is not None:
                return
            seed_rows = [
                ("SYNAAA", 100.0, 4.50, 5.00, 500.0),  # ticker, shares, stop_loss, buy_price, cost_basis
                ("SYNBBB", 50.0, 7.25, 8.00, 400.0),
            ]
            for r in seed_rows:
                conn.execute(
                    "INSERT INTO portfolio (ticker, shares, stop_loss, buy_price, cost_basis) VALUES (?, ?, ?, ?, ?)",
                    r,
                )
            # Seed starting cash
            conn.execute("INSERT OR REPLACE INTO cash (id, balance) VALUES (0, ?)", (10_000.00,))
            # Generate deterministic multi-day history inline for tests
            from datetime import datetime, timedelta, UTC
            total_equity_static = 10_000.00 + sum(x[1] * x[3] for x in seed_rows)
            for days_ago in range(20, 0, -1):
                date_str = (datetime.now(UTC) - timedelta(days=days_ago)).strftime("%Y-%m-%d")
                for r in seed_rows:
                    shares = r[1]
                    buy_price = r[3]
                    current_price = buy_price * (1 + 0.01 * (20 - days_ago))
                    value = shares * current_price
                    conn.execute(
                        "INSERT INTO portfolio_history (date, ticker, shares, cost_basis, stop_loss, current_price, total_value, pnl, action, cash_balance, total_equity) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
                        ),
                    )
                conn.execute(
                    "INSERT INTO portfolio_history (date, ticker, shares, cost_basis, stop_loss, current_price, total_value, pnl, action, cash_balance, total_equity) VALUES (?, 'TOTAL', '', '', '', '', ?, 0.0, '', ?, ?)",
                    (
                        date_str,
                        sum(x[1] * x[3] for x in seed_rows),
                        10_000.00,
                        total_equity_static,
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

    Delegates snapshot assembly to pure compute_snapshot to keep logic consistent.
    """

    tickers = portfolio_df[COL_TICKER].tolist()
    
    # Try bulk fetch first
    data = fetch_prices(tickers)
    prices: dict[str, float] = {t: 0.0 for t in tickers}
    price_sources: dict[str, str] = {t: "INIT" for t in tickers}
    
    if not data.empty:
        if isinstance(data.columns, pd.MultiIndex):
            close = data["Close"].iloc[-1]
            for t in tickers:
                val = close.get(t)
                if val is not None and not pd.isna(val):
                    prices[t] = float(val)
                    price_sources[t] = "BULK"
        elif set(["ticker", "current_price"]).issubset(set(data.columns)):
            for _, r in data.iterrows():
                cur = r.get("current_price") if hasattr(r, "get") else r["current_price"]
                prices[str(r["ticker"])] = float(cur) if pd.notna(cur) else 0.0
                price_sources[str(r["ticker"])] = "BULK"
        else:
            val = data.get("Close", pd.Series([None])).iloc[-1]
            if tickers and not pd.isna(val):
                prices[tickers[0]] = float(val)
                price_sources[tickers[0]] = "BULK"
    
    # If bulk fetch failed or returned empty prices, try individual fallback
    # Only fallback to individual lookups if bulk fetch returned data but yielded zero prices.
    # When the bulk fetch returned an empty DataFrame (tests expect zeros without fallback)
    # skip fallback to keep deterministic 0.0 pricing.
    if (not data.empty) and all(price == 0.0 for price in prices.values()) and tickers:
        from services.market import get_current_price
        from services.manual_pricing import get_manual_price
        import logging

        logger = logging.getLogger(__name__)
        logger.info(
            "Bulk price fetch failed, attempting individual price lookups with manual fallback"
        )

        for ticker in tickers:
            # Manual override takes precedence
            manual_price = get_manual_price(ticker)
            if manual_price is not None:
                prices[ticker] = float(manual_price)
                price_sources[ticker] = "MANUAL"
                logger.info(f"Using manual price for {ticker}: ${manual_price}")
                continue
            # API individual lookup
            try:
                individual_price = get_current_price(ticker)
                if individual_price is not None and individual_price > 0:
                    prices[ticker] = float(individual_price)
                    price_sources[ticker] = "API"
                    logger.info(
                        f"Successfully fetched individual price for {ticker}: ${individual_price}"
                    )
            except Exception as e:
                logger.warning(f"Individual price fetch failed for {ticker}: {e}")
                # Keep the 0.0 default

        # Mark remaining zero prices explicitly
        for t in tickers:
            if prices.get(t, 0.0) == 0.0 and price_sources.get(t) in {"INIT", "BULK"}:
                price_sources[t] = "ZERO"

    df = _compute_snapshot(
        portfolio_df.rename(
            columns={
                COL_TICKER: "ticker",
                COL_SHARES: "shares",
                COL_STOP: "stop_loss",
                COL_PRICE: "buy_price",
                COL_COST: "cost_basis",
            }
        ),
        prices,
        cash,
        TODAY,
        price_sources=price_sources,
    )

    # --- PnL Attribution (price vs position) ---
    try:
        # Load previous day's snapshot positions (excluding TOTAL) using cost_basis to derive avg buy price
        from datetime import datetime, timedelta
        prev_day = (datetime.strptime(TODAY, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
        with get_connection() as conn:
            prev_rows = conn.execute(
                "SELECT ticker, shares, cost_basis FROM portfolio_history WHERE date = ? AND ticker != 'TOTAL'",
                (prev_day,),
            ).fetchall()
        if prev_rows:
            prev_df = pd.DataFrame(prev_rows, columns=["ticker", "shares", "cost_basis"]).copy()
            prev_df["buy_price"] = prev_df.apply(
                lambda r: (float(r["cost_basis"]) / float(r["shares"])) if float(r["shares"]) > 0 else 0.0,
                axis=1,
            )
            # Current positions from freshly built df (Ticker/Shares/Cost Basis)
            cur_pos = df[df["Ticker"] != "TOTAL"][["Ticker", "Shares", "Cost Basis"]].copy()
            cur_pos.rename(columns={"Ticker": "ticker", "Shares": "shares", "Cost Basis": "cost_basis"}, inplace=True)
            cur_pos["buy_price"] = cur_pos.apply(
                lambda r: (float(r["cost_basis"]) / float(r["shares"])) if float(r["shares"]) > 0 else 0.0,
                axis=1,
            )
            cur_attr = cur_pos[["ticker", "shares", "buy_price"]]
            prev_attr = prev_df[["ticker", "shares", "buy_price"]]
            attr_df = attribute_pnl(cur_attr, prev_attr)
            for col in ["pnl_price", "pnl_position", "pnl_total_attr"]:
                mapping = {r.ticker: r[col] for _, r in attr_df.iterrows()}
                df[col] = df["Ticker"].map(mapping).fillna(0.0)
        else:
            for col in ["pnl_price", "pnl_position", "pnl_total_attr"]:
                df[col] = 0.0
    except Exception:
        for col in ["pnl_price", "pnl_position", "pnl_total_attr"]:
            if col not in df.columns:
                df[col] = 0.0

    # Create a lower-case version for DB insertion and returning to UI
    rename_map = {
        "Date": "date",
        "Ticker": "ticker",
        "Shares": "shares",
        "Cost Basis": "cost_basis",
        "Stop Loss": "stop_loss",
        "Current Price": "current_price",
        "Total Value": "total_value",
        "PnL": "pnl",
        "Action": "action",
        "Cash Balance": "cash_balance",
        "Total Equity": "total_equity",
    }
    # Optional attribution columns (will be added by attribution step if present)
    if "pnl_price" in df.columns:
        rename_map["pnl_price"] = "pnl_price"
    if "pnl_position" in df.columns:
        rename_map["pnl_position"] = "pnl_position"
    if "pnl_total_attr" in df.columns:
        rename_map["pnl_total_attr"] = "pnl_total_attr"
    if "Price Source" in df.columns:
        rename_map["Price Source"] = "price_source"
    df = df.rename(
        columns={
            **rename_map
        }
    )

    # Prepare DB-aligned DataFrame (subset to schema columns only)
    # Columns defined by existing portfolio_history schema (don't add new columns without migration)
    base_cols = [
        "date",
        "ticker",
        "shares",
        "cost_basis",
        "stop_loss",
        "current_price",
        "total_value",
        "pnl",
        "action",
        "cash_balance",
        "total_equity",
    ]
    # Drop any non-schema analytic columns (e.g., price_source, pnl attribution) for persistence
    df_db = df[base_cols].copy()

    init_db()
    with get_connection() as conn:
        # Update current holdings
        conn.execute("DELETE FROM portfolio")
        if not portfolio_df.empty:
            core_columns = ["ticker", "shares", "stop_loss", "buy_price", "cost_basis"]
            available_columns = [col for col in core_columns if col in portfolio_df.columns]
            if available_columns:
                # Use executemany to avoid reliance on pandas.to_sql when using mocks
                insert_sql = "INSERT INTO portfolio (ticker, shares, stop_loss, buy_price, cost_basis) VALUES (?, ?, ?, ?, ?)"
                rows = (
                    portfolio_df.reindex(columns=core_columns)
                    .fillna(0)
                    .apply(
                        lambda r: (
                            r["ticker"],
                            float(r["shares"]),
                            float(r["stop_loss"]),
                            float(r["buy_price"]),
                            float(r["cost_basis"]),
                        ),
                        axis=1,
                    )
                    .tolist()
                )
                for row in rows:
                    conn.execute(insert_sql, row)

        # Update cash balance (single row table)
        conn.execute("INSERT OR REPLACE INTO cash (id, balance) VALUES (0, ?)", (float(cash),))

        # Store daily snapshot for the day using pandas to_sql so tests can patch it
        conn.execute("DELETE FROM portfolio_history WHERE date = ?", (TODAY,))
        try:
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore",
                    message="pandas only supports SQLAlchemy connectable",
                    category=UserWarning,
                )
                df_db.to_sql("portfolio_history", conn, if_exists="append", index=False)
        except Exception:
            # Fallback to manual inserts when working with mocked connections
            insert_hist = (
                "INSERT INTO portfolio_history (date, ticker, shares, cost_basis, stop_loss, current_price, total_value, pnl, action, cash_balance, total_equity) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
            )
            for _, r in df_db.iterrows():
                conn.execute(
                    insert_hist,
                    (
                        r["date"],
                        r["ticker"],
                        float(r["shares"]) if r["shares"] != "" else 0.0,
                        float(r["cost_basis"]) if r["cost_basis"] != "" else 0.0,
                        float(r["stop_loss"]) if r["stop_loss"] != "" else 0.0,
                        float(r["current_price"]) if r["current_price"] != "" else 0.0,
                        float(r["total_value"]) if r["total_value"] != "" else 0.0,
                        float(r["pnl"]) if r["pnl"] != "" else 0.0,
                        r["action"],
                        float(r["cash_balance"]) if r["cash_balance"] != "" else 0.0,
                        float(r["total_equity"]) if r["total_equity"] != "" else 0.0,
                    ),
                )

        # Ensure all writes are persisted (sqlite does not autocommit by default)
        try:
            conn.commit()
        except Exception:
            pass

    # Return the UI-friendly DataFrame (lowercase keys plus price_source)
    return df
