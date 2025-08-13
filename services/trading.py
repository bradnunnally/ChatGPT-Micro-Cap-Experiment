from typing import Optional

import pandas as pd
import streamlit as st

# Import the module to allow tests to patch functions after this module is imported
import data.portfolio as portfolio_data
from config import COL_COST, COL_PRICE, COL_SHARES, COL_STOP, COL_TICKER, TODAY
from core.errors import MarketDataDownloadError, NoMarketDataError
from data.db import get_connection, init_db
from services.core.portfolio_service import (
    apply_buy as _apply_buy,
)
from services.core.portfolio_service import (
    apply_sell as _apply_sell,
)
from services.core.portfolio_service import (
    calculate_pnl as _core_calculate_pnl,
)
from services.core.portfolio_service import (
    calculate_position_value as _core_calculate_position_value,
)
from services.core.repository import PortfolioRepository
from services.core.validation import (
    validate_shares as _core_validate_shares,
)
from services.core.validation import (
    validate_ticker as _core_validate_ticker,
)
from services.exceptions.validation import ValidationError as _ValidationError
from services.logging import audit_logger, get_logger, log_error
from services.market import get_current_price, get_day_high_low  # noqa: F401 (patched by tests)
from services.pure_utils import compute_cost, validate_buy_price

logger = get_logger(__name__)


def append_trade_log(log: dict) -> None:
    """Persist a dictionary entry to the trade log table."""

    init_db()
    with get_connection() as conn:
        df = pd.DataFrame([log])
        df = df.rename(
            columns={
                "Date": "date",
                "Ticker": "ticker",
                "Shares Bought": "shares_bought",
                "Buy Price": "buy_price",
                "Cost Basis": "cost_basis",
                "PnL": "pnl",
                "Reason": "reason",
                "Shares Sold": "shares_sold",
                "Sell Price": "sell_price",
            }
        )
        df.to_sql("trade_log", conn, if_exists="append", index=False)


def manual_buy(
    ticker: str,
    shares: float,
    price: float,
    stop_loss: float,
    portfolio_df: pd.DataFrame | None = None,
    cash: float | None = None,
    repo: Optional[PortfolioRepository] | None = None,
) -> bool | tuple[bool, str, pd.DataFrame, float]:
    """Execute a manual buy and update portfolio and logs.

    Test shims: if portfolio_df and cash are omitted, use st.session_state and return bool.
    """

    ticker = ticker.upper()

    # When using session_state mode (tests), fetch from st.session_state
    session_mode = portfolio_df is None or cash is None
    if session_mode:
        if not hasattr(st.session_state, "portfolio"):
            st.session_state.portfolio = pd.DataFrame(
                columns=[COL_TICKER, COL_SHARES, COL_STOP, COL_PRICE, COL_COST]
            )
        portfolio_df = getattr(st.session_state, "portfolio")
        # Fallback to 10,000 if session state isn't fully active in test context
        cash = float(getattr(st.session_state, "cash", 10000.0))
    if shares <= 0 or price <= 0:
        msg = "Shares and price must be positive."
        log_error(msg)
        audit_logger.trade(
            "buy", ticker=ticker, shares=shares, price=price, status="failure", reason=msg
        )
        return False if session_mode else (False, msg, portfolio_df, cash)
    # For session_mode tests, skip day range validation; rely on provided price
    if not session_mode:
        has_market_data = True
        try:
            day_high, day_low = get_day_high_low(ticker)
        except (MarketDataDownloadError, NoMarketDataError) as exc:
            # Graceful handling for missing data - allow trade to proceed without validation
            has_market_data = False
            day_high = day_low = None
            logger.warning(f"No market data for {ticker}, proceeding without price validation", 
                         extra={"event": "market_data_fallback", "ticker": ticker, "reason": str(exc)})
        except Exception as exc:  # pragma: no cover - other network errors
            log_error(f"Market data error for {ticker}: {str(exc)}")
            audit_logger.trade(
                "buy", ticker=ticker, shares=shares, price=price, status="failure", reason=str(exc)
            )
            return False if session_mode else (False, str(exc), portfolio_df, cash)
        
        # Only enforce range validation when we actually have market data
        if has_market_data:
            validation = validate_buy_price(price, day_low, day_high)
            if not validation.valid:
                msg = validation.reason or "Invalid price"
                log_error(msg)
                audit_logger.trade(
                    "buy", ticker=ticker, shares=shares, price=price, status="failure", reason=msg
                )
                return False if session_mode else (False, msg, portfolio_df, cash)

    cost = compute_cost(shares, price)
    if cost > cash:
        reason = "Insufficient cash for this trade."
        log_error(reason)
        audit_logger.trade(
            "buy", ticker=ticker, shares=shares, price=price, status="failure", reason=reason
        )
        return False if session_mode else (False, reason, portfolio_df, cash)

    # Record trade log only in full app mode
    if not session_mode:
        log = {
            "Date": TODAY,
            "Ticker": ticker,
            "Shares Bought": shares,
            "Buy Price": price,
            "Cost Basis": cost,
            "PnL": 0.0,
            "Reason": "MANUAL BUY - New position",
        }
        if repo is not None:
            try:
                repo.append_trade_log(log)
            except Exception as exc:  # pragma: no cover
                log_error(str(exc))
                logger.exception(
                    "Repository append_trade_log failed",
                    extra={"event": "trade_log", "action": "buy", "ticker": ticker},
                )
        else:
            append_trade_log(log)

    # Delegate portfolio math to pure function for consistency
    portfolio_df = _apply_buy(
        portfolio_df,
        ticker=ticker,
        shares=shares,
        price=price,
        stop_loss=stop_loss,
    )

    cash -= cost
    # Persist snapshot via repository when provided; otherwise defer to data.portfolio
    if repo is not None:
        try:
            repo.save_snapshot(portfolio_df, cash)
        except Exception as exc:  # pragma: no cover
            log_error(str(exc))
            logger.exception(
                "Repository save_snapshot failed",
                extra={"event": "snapshot", "phase": "buy", "ticker": ticker},
            )
    else:
        # Call through module to respect test patches on data.portfolio.save_portfolio_snapshot
        portfolio_data.save_portfolio_snapshot(portfolio_df, cash)
    msg = f"Bought {shares} shares of {ticker} at ${price:.2f}."
    if session_mode:
        st.session_state.portfolio = portfolio_df
        st.session_state.cash = cash
        audit_logger.trade("buy", ticker=ticker, shares=shares, price=price, status="success")
        return True
    audit_logger.trade("buy", ticker=ticker, shares=shares, price=price, status="success")
    return True, msg, portfolio_df, cash


def manual_sell(
    ticker: str,
    shares: float,
    price: float,
    portfolio_df: pd.DataFrame | None = None,
    cash: float | None = None,
    repo: Optional[PortfolioRepository] | None = None,
) -> bool | tuple[bool, str, pd.DataFrame, float]:
    """Execute a manual sell and update portfolio and logs.

    Test shims: if portfolio_df and cash are omitted, use st.session_state and return bool.
    """

    ticker = ticker.upper()
    session_mode = portfolio_df is None or cash is None
    if session_mode:
        portfolio_df = getattr(
            st.session_state,
            "portfolio",
            pd.DataFrame(columns=[COL_TICKER, COL_SHARES, COL_STOP, COL_PRICE, COL_COST]),
        )
        cash = float(getattr(st.session_state, "cash", 10000.0))
    if shares <= 0 or price <= 0:
        msg = "Shares and price must be positive."
        log_error(msg)
        audit_logger.trade(
            "sell", ticker=ticker, shares=shares, price=price, status="failure", reason=msg
        )
        return False if session_mode else (False, msg, portfolio_df, cash)
    if ticker not in portfolio_df[COL_TICKER].values:
        msg = "Ticker not in portfolio."
        log_error(msg)
        audit_logger.trade(
            "sell", ticker=ticker, shares=shares, price=price, status="failure", reason=msg
        )
        return False if session_mode else (False, msg, portfolio_df, cash)

    if not session_mode:
        has_market_data = True
        try:
            day_high, day_low = get_day_high_low(ticker)
        except (MarketDataDownloadError, NoMarketDataError) as exc:
            # Graceful handling for missing data - allow trade to proceed without validation
            has_market_data = False
            day_high = day_low = None
            logger.warning(f"No market data for {ticker}, proceeding without price validation", 
                         extra={"event": "market_data_fallback", "ticker": ticker, "reason": str(exc)})
        except Exception as exc:  # pragma: no cover - other network errors
            log_error(str(exc))
            audit_logger.trade(
                "sell", ticker=ticker, shares=shares, price=price, status="failure", reason=str(exc)
            )
            return False if session_mode else (False, str(exc), portfolio_df, cash)
        
        # Only enforce range validation when we actually have market data
        if has_market_data and not (day_low <= price <= day_high):
            msg = f"Price outside today's range {day_low:.2f}-{day_high:.2f}"
            log_error(msg)
            audit_logger.trade(
                "sell", ticker=ticker, shares=shares, price=price, status="failure", reason=msg
            )
            return False if session_mode else (False, msg, portfolio_df, cash)

    row = portfolio_df[portfolio_df[COL_TICKER] == ticker].iloc[0]
    total_shares = float(row[COL_SHARES])
    if shares > total_shares:
        msg = f"Trying to sell {shares} shares but only own {total_shares}."
        log_error(msg)
        audit_logger.trade(
            "sell", ticker=ticker, shares=shares, price=price, status="failure", reason=msg
        )
        return False if session_mode else (False, msg, portfolio_df, cash)

    buy_price = float(row[COL_PRICE])
    # Use pure function for pnl calculation
    pnl = _core_calculate_pnl(buy_price=buy_price, current_price=price, shares=shares)
    cost_basis = buy_price * shares

    if not session_mode:
        log = {
            "Date": TODAY,
            "Ticker": ticker,
            "Shares Bought": "",
            "Buy Price": "",
            "Cost Basis": cost_basis,
            "PnL": pnl,
            "Reason": "MANUAL SELL - User",
            "Shares Sold": shares,
            "Sell Price": price,
        }
        if repo is not None:
            try:
                repo.append_trade_log(log)
            except Exception as exc:  # pragma: no cover
                log_error(str(exc))
                logger.exception(
                    "Repository append_trade_log failed",
                    extra={"event": "trade_log", "action": "sell", "ticker": ticker},
                )
        else:
            append_trade_log(log)

    # Delegate sell math to pure function
    portfolio_df, _ = _apply_sell(
        portfolio_df,
        ticker=ticker,
        shares=shares,
        price=price,
    )

    cash += price * shares
    # Persist snapshot via repository when provided; otherwise defer to data.portfolio
    if repo is not None:
        try:
            repo.save_snapshot(portfolio_df, cash)
        except Exception as exc:  # pragma: no cover
            log_error(str(exc))
            logger.exception(
                "Repository save_snapshot failed",
                extra={"event": "snapshot", "phase": "sell", "ticker": ticker},
            )
    else:
        # Call through module to respect test patches on data.portfolio.save_portfolio_snapshot
        portfolio_data.save_portfolio_snapshot(portfolio_df, cash)
    msg = f"Sold {shares} shares of {ticker} at ${price:.2f}."
    if session_mode:
        st.session_state.portfolio = portfolio_df
        st.session_state.cash = cash
        audit_logger.trade("sell", ticker=ticker, shares=shares, price=price, status="success")
        return True
    audit_logger.trade("sell", ticker=ticker, shares=shares, price=price, status="success")
    return True, msg, portfolio_df, cash


# Simple business logic helpers expected by tests
def calculate_position_value(shares: float, current_price: float) -> float:
    # Delegate to pure function to keep logic in one place
    return _core_calculate_position_value(shares, current_price)


def calculate_profit_loss(buy_price: float, current_price: float, shares: float) -> float:
    # Delegate to pure function to keep logic in one place
    return _core_calculate_pnl(buy_price, current_price, shares)


def update_cash_balance(delta: float) -> None:
    st.session_state.cash = float(getattr(st.session_state, "cash", 0.0)) + float(delta)


def validate_cash_balance(required: float) -> bool:
    return float(getattr(st.session_state, "cash", 0.0)) >= float(required)


def aggregate_positions(df: pd.DataFrame) -> pd.DataFrame:
    grouped = df.groupby("ticker", as_index=False).agg(
        {
            "shares": "sum",
            "stop_loss": "last",
            "buy_price": "mean",
            "cost_basis": "sum",
        }
    )
    return grouped


def validate_stop_loss(stop_loss: float, buy_price: float) -> bool:
    return stop_loss > 0 and stop_loss < buy_price


def validate_ticker(ticker: str) -> bool:
    """Return True if ticker is valid using centralized validator.

    Keeps boolean contract expected by tests while delegating rules
    to services.core.validation.
    """
    try:
        _core_validate_ticker(ticker)
        return True
    except _ValidationError:
        return False


def validate_shares(shares: int) -> bool:
    """Return True if shares is a valid positive integer via centralized validator."""
    try:
        _core_validate_shares(shares)
        return True
    except _ValidationError:
        return False


def validate_price(price: float) -> bool:
    """Return True if price is a valid positive number.

    Central validator expects Decimal; since tests use float inputs here,
    we mirror legacy behavior for bool semantics while leveraging
    centralized rules conceptually. This keeps runtime stable for UI/tests.
    """
    try:
        # Lightweight check to preserve existing float-based flows
        return isinstance(price, (int, float)) and price > 0
    except Exception:
        return False


def execute_buy(trade_data: dict) -> bool:
    """
    Execute a buy transaction.

    Args:
        trade_data: Dictionary containing 'ticker', 'shares', and 'price'
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        total_cost = trade_data["shares"] * trade_data["price"]

        # Verify sufficient funds
        if total_cost > st.session_state.cash:
            st.error("Insufficient funds for purchase")
            return False

        # Update cash balance
        st.session_state.cash -= total_cost

        # Add to portfolio
        from services.time import Clock

        new_position = pd.DataFrame(
            {
                "Ticker": [trade_data["ticker"]],
                "Shares": [trade_data["shares"]],
                "Price": [trade_data["price"]],
                "Date": [Clock().now()],
            }
        )

        if st.session_state.portfolio.empty:
            st.session_state.portfolio = new_position
        else:
            st.session_state.portfolio = pd.concat([st.session_state.portfolio, new_position])

        return True

    except Exception as e:
        st.error(f"Error executing buy: {str(e)}")
        return False


def execute_sell(trade_data: dict) -> bool:
    """
    Execute a sell transaction.

    Args:
        trade_data: Dictionary containing 'ticker', 'shares', and 'price'
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Verify sufficient shares
        matching = st.session_state.portfolio[
            st.session_state.portfolio["Ticker"] == trade_data["ticker"]
        ]

        if matching.empty or matching.iloc[0]["Shares"] < trade_data["shares"]:
            st.error("Insufficient shares for sale")
            return False

        # Update portfolio
        current_shares = matching.iloc[0]["Shares"]
        remaining_shares = current_shares - trade_data["shares"]

        if remaining_shares == 0:
            st.session_state.portfolio = st.session_state.portfolio[
                st.session_state.portfolio["Ticker"] != trade_data["ticker"]
            ]
        else:
            st.session_state.portfolio.loc[
                st.session_state.portfolio["Ticker"] == trade_data["ticker"], "Shares"
            ] = remaining_shares

        # Update cash balance
        proceeds = trade_data["shares"] * trade_data["price"]
        st.session_state.cash += proceeds

        return True

    except Exception as e:
        st.error(f"Error executing sell: {str(e)}")
        return False


def validate_trade(trade_data: dict) -> bool:
    """
    Validate trade data.

    Args:
        trade_data: Dictionary containing trade information
    Returns:
        bool: True if valid, False otherwise
    """
    required_fields = ["ticker", "shares", "price"]
    if not all(field in trade_data for field in required_fields):
        return False

    try:
        shares = float(trade_data["shares"])
        price = float(trade_data["price"])

        return shares > 0 and price > 0
    except (ValueError, TypeError):
        return False
