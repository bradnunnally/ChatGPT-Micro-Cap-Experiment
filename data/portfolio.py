import pandas as pd

from config import TODAY, COL_TICKER, COL_SHARES, COL_STOP, COL_PRICE, COL_COST
from portfolio import ensure_schema
from services.market import fetch_prices, get_last_price
from data.db import init_db, get_connection


def load_portfolio() -> tuple[pd.DataFrame, float, bool]:
    """Return the latest portfolio and cash balance."""

    empty_portfolio = pd.DataFrame(columns=ensure_schema(pd.DataFrame()).columns)

    init_db()
    with get_connection() as conn:
        portfolio_df = pd.read_sql_query("SELECT * FROM portfolio", conn)
        cash_row = conn.execute("SELECT balance FROM cash WHERE id = 0").fetchone()

    if portfolio_df.empty and cash_row is None:
        return empty_portfolio, 0.0, True

    portfolio = ensure_schema(portfolio_df) if not portfolio_df.empty else empty_portfolio
    cash = float(cash_row[0]) if cash_row else 0.0
    return portfolio, cash, portfolio_df.empty


def save_portfolio_snapshot(portfolio_df: pd.DataFrame, cash: float) -> pd.DataFrame:
    """Recalculate today's portfolio values and persist them to ``PORTFOLIO_CSV``."""

    results: list[dict[str, float | str]] = []
    total_value = 0.0
    total_pnl = 0.0

    tickers = portfolio_df[COL_TICKER].tolist()
    data = fetch_prices(tickers)
    prices: dict[str, float] = {t: 0.0 for t in tickers}
    if not data.empty:
        if isinstance(data.columns, pd.MultiIndex):
            close = data["Close"].iloc[-1]
            for t in tickers:
                val = close.get(t)
                if val is not None and not pd.isna(val):
                    prices[t] = float(val)
        else:
            val = data["Close"].iloc[-1]
            if tickers and not pd.isna(val):
                prices[tickers[0]] = float(val)

    for _, row in portfolio_df.iterrows():
        ticker = row[COL_TICKER]
        shares = float(row[COL_SHARES])
        stop = float(row[COL_STOP])
        buy_price = float(row[COL_PRICE])

        # Choose current price with robust fallback order:
        # 1) batch-fetched price; 2) per-ticker last close; 3) buy_price
        source = "Live"
        price = prices.get(ticker)
        if price is None or pd.isna(price) or float(price) == 0.0:
            # Try per-ticker fallback via yfinance Ticker().history/fast_info
            try:
                last = get_last_price(str(ticker))
            except Exception:
                last = None
            if last is not None:
                price = float(last)
                source = "Last Close"
            else:
                price = buy_price
                source = "Manual"
        value = round(price * shares, 2)
        pnl = round((price - buy_price) * shares, 2)
        total_value += value
        total_pnl += pnl

        results.append(
            {
                "Date": TODAY,
                "Ticker": ticker,
                "Shares": shares,
                "Cost Basis": buy_price,
                "Stop Loss": stop,
                "Current Price": price,
                "Total Value": value,
                "PnL": pnl,
                "Action": "HOLD",
                "Price Source": source,
                "Cash Balance": "",
                "Total Equity": "",
            }
        )

    total_row = {
        "Date": TODAY,
        "Ticker": "TOTAL",
        "Shares": "",
        "Cost Basis": "",
        "Stop Loss": "",
        "Current Price": "",
        "Total Value": round(total_value, 2),
        "PnL": round(total_pnl, 2),
        "Action": "",
        "Price Source": "",
        "Cash Balance": round(cash, 2),
        "Total Equity": round(total_value + cash, 2),
    }
    results.append(total_row)

    df = pd.DataFrame(results)

    # Create a lower-case version for DB insertion and returning to UI
    df = df.rename(
        columns={
            "Date": "date",
            "Ticker": "ticker",
            "Shares": "shares",
            "Cost Basis": "cost_basis",
            "Stop Loss": "stop_loss",
            "Current Price": "current_price",
            "Total Value": "total_value",
            "PnL": "pnl",
            "Action": "action",
            "Price Source": "price_source",
            "Cash Balance": "cash_balance",
            "Total Equity": "total_equity",
        }
    )

    # Prepare DB-aligned DataFrame (subset to schema columns only)
    df_db = df[
        [
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
    ]

    init_db()
    with get_connection() as conn:
        # Update current holdings - filter to only include database columns
        conn.execute("DELETE FROM portfolio")
        
        # Only save the core portfolio columns that exist in the database schema
        # But only if the DataFrame is not empty and has the required columns
        if not portfolio_df.empty:
            core_columns = ['ticker', 'shares', 'stop_loss', 'buy_price', 'cost_basis']
            # Only include columns that actually exist in the DataFrame
            available_columns = [col for col in core_columns if col in portfolio_df.columns]
            if available_columns:
                portfolio_core = portfolio_df[available_columns].copy()
                portfolio_core.to_sql("portfolio", conn, if_exists="append", index=False)

        # Update cash balance (single row table)
        conn.execute("INSERT OR REPLACE INTO cash (id, balance) VALUES (0, ?)", (cash,))

        # Store daily snapshot
        conn.execute("DELETE FROM portfolio_history WHERE date = ?", (TODAY,))
        df_db.to_sql("portfolio_history", conn, if_exists="append", index=False)

    # Return the UI-friendly DataFrame (lowercase keys plus price_source)
    return df
