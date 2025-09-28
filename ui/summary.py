import logging
import math
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from services.core.market_service import MarketService
from utils.cache import get_cached_price_data, get_cached_price_history, warm_cache_for_symbols, COMMON_SYMBOLS
from utils.error_handling import (
    handle_summary_errors, 
    handle_data_errors, 
    safe_numeric_conversion,
    create_empty_result,
    validate_input_data
)


# Configure logging
logger = logging.getLogger(__name__)

MARKET_SERVICE = MarketService()
DEFAULT_BENCHMARK = "^GSPC"
TRADING_DAYS_PER_YEAR = 252


# Standardized formatting functions
def fmt_close(value: Optional[float]) -> str:
    """Format closing price with comma separators."""
    if value is None or pd.isna(value):
        return "—"
    return f"{value:,.2f}"


def fmt_pct_signed(value: Optional[float]) -> str:
    """Format percentage with +/- sign."""
    if value is None or pd.isna(value):
        return "—"
    return f"{value:+.2f}%"


def fmt_volume(value: Optional[float]) -> str:
    """Format volume numbers with comma separators."""
    if value is None or pd.isna(value):
        return "—"
    return f"{int(round(value)):,}"


def fmt_currency_padded(value: Optional[float]) -> str:
    """Format currency with padding for alignment."""
    if value is None or pd.isna(value):
        return "$        —"
    return f"$ {value:>15,.2f}"


def fmt_currency(value: Optional[float]) -> str:
    """Standard currency formatting."""
    if value is None or pd.isna(value):
        return "—"
    return f"${value:,.2f}"


def fmt_shares(value: Optional[float]) -> str:
    """Format share counts."""
    if value is None or pd.isna(value):
        return "—"
    return f"{value:,.0f}"


def fmt_ratio(value: Optional[float], decimals: int = 4) -> str:
    """Format ratios with configurable decimal places."""
    if value is None or pd.isna(value):
        return "—"
    return f"{value:.{decimals}f}"


def fmt_stop(value: Any) -> str:
    """Format stop loss values, handling string inputs."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return "—"
    try:
        if isinstance(value, str):
            cleaned = value.replace("$", "").replace(",", "").strip()
            value = float(cleaned)
        return fmt_currency(float(value))
    except (ValueError, TypeError):
        return "—"


@handle_summary_errors(fallback_value=create_empty_result('price_data'))
def _fetch_price_volume(symbol: str, months: int = 3) -> Dict[str, Optional[float]]:
    """
    Fetch current price and volume data for a symbol using cache.
    
    Args:
        symbol: Stock symbol to fetch
        months: Unused parameter (kept for backward compatibility)
        
    Returns:
        Dictionary with symbol, close, pct_change, volume data
    """
    if not symbol or not symbol.strip():
        return {"symbol": symbol, "close": None, "pct_change": None, "volume": None}
    
    # Use cached price data with 5-minute TTL
    return get_cached_price_data(symbol.strip().upper(), ttl_minutes=5)


@handle_data_errors(fallback_value=False, log_level="debug")
def _history_has_valid_equity(history: Optional[pd.DataFrame]) -> bool:
    if history is None or history.empty:
        return False

    df = history.copy()
    if "ticker" not in df.columns:
        return False
    if "total_equity" not in df.columns:
        return False

    df["total_equity"] = pd.to_numeric(df["total_equity"], errors="coerce")
    df["date"] = pd.to_datetime(df.get("date"), errors="coerce")
    df = df.dropna(subset=["date"])
    total_rows = df[df["ticker"] == "TOTAL"].copy()
    if total_rows.empty:
        return False
    total_rows = total_rows.dropna(subset=["total_equity"])
    total_rows = total_rows.sort_values("date").drop_duplicates(subset=["date"], keep="last")
    return len(total_rows) >= 2


@handle_data_errors(fallback_value=pd.DataFrame(), log_level="warning")
def _build_portfolio_history_from_market(
    holdings_df: pd.DataFrame, cash_balance: float, months: int = 6
) -> pd.DataFrame:
    """Build synthetic portfolio history using current positions and market data.
    
    This creates a backfilled history showing what the portfolio value would have been
    if the current positions were held at historical prices.
    """
    logger.debug(f"Building portfolio history from market data (months={months})")
    
    if holdings_df is None or holdings_df.empty:
        logger.debug("No holdings data available")
        return pd.DataFrame()

    series_map: Dict[str, pd.Series] = {}
    failed_tickers = []
    
    for _, row in holdings_df.iterrows():
        ticker = str(row.get("ticker") or row.get("Ticker") or "").strip().upper()
        if not ticker:
            continue
            
        shares = pd.to_numeric(pd.Series([row.get("shares") or row.get("Shares")]), errors="coerce").iloc[0]
        if shares is None or pd.isna(shares) or float(shares) == 0.0:
            continue

        logger.debug(f"Fetching history for {ticker} ({shares} shares)")
        
        try:
            # Use cached price history with 5-minute TTL
            hist = get_cached_price_history(ticker, months=months, ttl_minutes=5)
            if hist is None or hist.empty:
                logger.debug(f"No market history returned for {ticker}")
                failed_tickers.append(ticker)
                continue
                
        except Exception as e:
            logger.warning(f"Failed to fetch history for {ticker}: {e}")
            failed_tickers.append(ticker)
            continue

        df = hist.copy()
        if "date" not in df.columns or "close" not in df.columns:
            logger.debug(f"Missing required columns for {ticker}")
            failed_tickers.append(ticker)
            continue
            
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"]).sort_values("date")
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        df = df.dropna(subset=["close"])
        
        if df.empty:
            logger.debug(f"Empty history after cleaning for {ticker}")
            failed_tickers.append(ticker)
            continue

        logger.debug(f"Successfully loaded {len(df)} price points for {ticker}")
        df = df.drop_duplicates(subset=["date"], keep="last").set_index("date")
        series_map[ticker] = df["close"] * float(shares)

    if failed_tickers:
        logger.info(f"Failed to load history for: {failed_tickers}")
        
    if not series_map:
        logger.warning("No valid price series found")
        return pd.DataFrame()

    logger.debug(f"Combining {len(series_map)} price series")
    combined = pd.concat(series_map.values(), axis=1)
    combined.columns = list(series_map.keys())
    combined = combined.sort_index().ffill().dropna(how="all")

    if combined.empty:
        logger.warning("Combined series is empty")
        return pd.DataFrame()

    total_value = combined.sum(axis=1)
    total_equity = total_value + float(cash_balance or 0.0)

    logger.info(f"Generated {len(total_equity)} portfolio value points")
    logger.debug(f"Portfolio value range: ${total_equity.min():,.2f} - ${total_equity.max():,.2f}")

    result = pd.DataFrame({
        "date": total_equity.index,
        "ticker": "TOTAL",
        "total_equity": total_equity.values,
    })
    return result.reset_index(drop=True)


@handle_summary_errors(fallback_value=(pd.DataFrame(), True))
def get_portfolio_history_for_analytics(
    holdings_df: pd.DataFrame, 
    history_df: Optional[pd.DataFrame], 
    cash_balance: float
) -> tuple[pd.DataFrame, bool]:
    """Get portfolio history for risk calculations using hybrid approach.
    
    Returns:
        tuple: (history_dataframe, is_synthetic_data)
    """
    logger.debug("Getting portfolio history for analytics")
    
    # First, try to use actual stored history
    if history_df is not None and not history_df.empty:
        if _history_has_valid_equity(history_df):
            total_rows = history_df[history_df.get("ticker", history_df.get("Ticker", "")) == "TOTAL"]
            if len(total_rows) >= 10:  # Need at least 10 data points
                logger.info(f"Using actual stored history ({len(total_rows)} TOTAL rows)")
                return history_df, False
            else:
                logger.debug(f"Stored history has insufficient data points ({len(total_rows)} < 10)")
        else:
            logger.debug("Stored history has no valid equity data")
    else:
        logger.debug("No stored history available")
    
    # Fall back to synthetic history from market data
    logger.info("Generating synthetic portfolio history from market data")
    synthetic_history = _build_portfolio_history_from_market(holdings_df, cash_balance, months=6)
    
    if not synthetic_history.empty:
        logger.info(f"Generated {len(synthetic_history)} synthetic data points")
        return synthetic_history, True
    else:
        logger.warning("Failed to generate synthetic history")
        return pd.DataFrame(), True


@handle_summary_errors(fallback_value=create_empty_result('risk_metrics'))
def _compute_risk_metrics_with_source_info(
    history: Optional[pd.DataFrame], 
    is_synthetic: bool = False,
    benchmark_symbol: str = DEFAULT_BENCHMARK
) -> Dict[str, Any]:
    """Compute risk metrics with source information."""
    logger.debug(f"Computing risk metrics (synthetic={is_synthetic})")
    
    metrics: Dict[str, Any] = {
        "max_drawdown": None,
        "max_drawdown_date": None,
        "sharpe_period": None,
        "sharpe_annual": None,
        "sortino_period": None,
        "sortino_annual": None,
        "beta": None,
        "alpha_annual": None,
        "r_squared": None,
        "obs": 0,
        "note": None,
        "sp_first_close": None,
        "sp_last_close": None,
        "is_synthetic": is_synthetic,
    }

    if history is None or history.empty:
        logger.debug("No history data for risk calculations")
        return metrics

    df = history.copy()
    if "date" not in df.columns:
        logger.debug("No date column in history data")
        return metrics

    logger.debug(f"Processing {len(df)} history rows")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    if df.empty:
        logger.debug("No valid dates in history")
        return metrics
    df["date"] = df["date"].dt.tz_localize(None)

    portfolio = df[df["ticker"] == "TOTAL"].copy()
    if portfolio.empty:
        logger.debug("No TOTAL rows found in history")
        return metrics

    logger.debug(f"Found {len(portfolio)} TOTAL rows")
    portfolio["total_equity"] = pd.to_numeric(portfolio["total_equity"], errors="coerce")
    portfolio = portfolio.dropna(subset=["total_equity"])
    if portfolio.empty:
        logger.debug("No valid total_equity values")
        return metrics

    logger.debug(f"Processing {len(portfolio)} valid portfolio data points")
    portfolio = portfolio.sort_values("date")
    
    # Calculate drawdown
    portfolio["cummax"] = portfolio["total_equity"].cummax()
    portfolio["drawdown"] = portfolio["total_equity"] / portfolio["cummax"] - 1

    if not portfolio["drawdown"].dropna().empty:
        drawdowns = portfolio["drawdown"].dropna()
        max_dd = float(drawdowns.min() * 100.0)
        metrics["max_drawdown"] = max_dd
        min_idx = drawdowns.idxmin()
        max_dd_date = portfolio.loc[min_idx, "date"]
        if pd.notna(max_dd_date):
            metrics["max_drawdown_date"] = max_dd_date.date().isoformat()
        logger.debug(f"Max drawdown = {max_dd:.2f}%")

    # Calculate returns and Sharpe/Sortino
    portfolio["return"] = portfolio["total_equity"].pct_change()
    returns = portfolio["return"].dropna()
    if not returns.empty:
        mean_ret = float(returns.mean())
        std_ret = float(returns.std(ddof=1)) if len(returns) > 1 else 0.0
        logger.debug(f"Mean return = {mean_ret:.6f}, Std dev = {std_ret:.6f}")
        
        if std_ret > 0:
            sharpe = mean_ret / std_ret
            metrics["sharpe_period"] = sharpe
            metrics["sharpe_annual"] = sharpe * math.sqrt(TRADING_DAYS_PER_YEAR)
            logger.debug(f"Sharpe ratio = {sharpe:.4f} (annualized: {metrics['sharpe_annual']:.4f})")

        downside = returns[returns < 0]
        downside_std = float(downside.std(ddof=1)) if len(downside) > 1 else 0.0
        if downside_std > 0:
            sortino = mean_ret / downside_std
            metrics["sortino_period"] = sortino
            metrics["sortino_annual"] = sortino * math.sqrt(TRADING_DAYS_PER_YEAR)
            logger.debug(f"Sortino ratio = {sortino:.4f} (annualized: {metrics['sortino_annual']:.4f})")

    # Estimate period in months for benchmark history fetch
    date_span_days = max(1, (portfolio["date"].iloc[-1] - portfolio["date"].iloc[0]).days)
    months = max(1, math.ceil(date_span_days / 30))
    logger.debug(f"Portfolio spans {date_span_days} days, fetching {months} months of benchmark data")

    try:
        # Use cached benchmark history with 5-minute TTL
        bench_hist = get_cached_price_history(benchmark_symbol, months=max(months, 3), ttl_minutes=5)
        logger.debug(f"Fetched benchmark history for {benchmark_symbol} (cached)")
    except Exception as e:
        logger.warning(f"Failed to fetch benchmark history: {e}")
        bench_hist = pd.DataFrame()

    if bench_hist is not None and not bench_hist.empty:
        bench = bench_hist.copy()
        if "date" in bench.columns:
            bench["date"] = pd.to_datetime(bench["date"], errors="coerce")
            bench = bench.dropna(subset=["date"])
            bench["date"] = bench["date"].dt.tz_localize(None)
        bench["close"] = pd.to_numeric(bench.get("close"), errors="coerce")
        bench = bench.dropna(subset=["close"])
        bench = bench.sort_values("date")
        bench = bench[(bench["date"] >= portfolio["date"].iloc[0]) & (bench["date"] <= portfolio["date"].iloc[-1])]

        if not bench.empty:
            closes = bench["close"].dropna()
            if not closes.empty:
                metrics["sp_first_close"] = float(closes.iloc[0])
                metrics["sp_last_close"] = float(closes.iloc[-1])
                logger.debug(f"Benchmark range: {metrics['sp_first_close']:.2f} - {metrics['sp_last_close']:.2f}")

        bench["bench_return"] = bench["close"].pct_change()
        merged = pd.merge(
            portfolio[["date", "return"]].dropna(),
            bench[["date", "bench_return"]].dropna(),
            on="date",
            how="inner",
        )

        obs = len(merged)
        metrics["obs"] = obs
        logger.debug(f"Merged {obs} observations for beta/alpha calculations")

        if obs >= 2:
            bench_returns = merged["bench_return"].to_numpy()
            port_returns = merged["return"].to_numpy()
            bench_var = float(np.var(bench_returns, ddof=1))
            if bench_var > 0:
                cov = float(np.cov(bench_returns, port_returns, ddof=1)[0][1])
                beta = cov / bench_var
                metrics["beta"] = beta
                alpha_daily = float(port_returns.mean() - beta * bench_returns.mean())
                metrics["alpha_annual"] = ((1 + alpha_daily) ** TRADING_DAYS_PER_YEAR) - 1
                logger.debug(f"Beta = {beta:.4f}, Alpha (annual) = {metrics['alpha_annual']:.4f}")

            corr_matrix = np.corrcoef(bench_returns, port_returns)
            if corr_matrix.shape == (2, 2):
                r_value = corr_matrix[0, 1]
                if not np.isnan(r_value):
                    metrics["r_squared"] = float(r_value**2)
                    logger.debug(f"R² = {metrics['r_squared']:.4f}")

    # Add appropriate notes
    if is_synthetic:
        metrics["note"] = f"Metrics based on synthetic history ({metrics['obs']} obs). Real tracking starts after portfolio activity."
    elif metrics["note"] is None and (
        metrics["obs"] < 60 or (metrics["r_squared"] is not None and metrics["r_squared"] < 0.5)
    ):
        metrics["note"] = "Short sample and/or low R² — alpha/beta may be unstable."
    elif metrics["note"] is None and metrics["obs"]:
        metrics["note"] = f"Metrics based on {metrics['obs']} observations."

    logger.info(f"Risk metrics calculation complete. Note: {metrics['note']}")
    return metrics


@handle_summary_errors(fallback_value=["[ Price & Volume ]", "(error occurred)"])
def _format_price_volume_section(price_rows: List[Dict[str, Any]]) -> List[str]:
    """Format the Price & Volume section of the report."""
    lines = []
    ticker_w, close_w, pct_w, vol_w = 16, 10, 8, 15
    header = f"{'Ticker':<{ticker_w}}{'Close':>{close_w}}{'% Chg':>{pct_w}}{'Volume':>{vol_w}}"
    lines.append("[ Price & Volume ]")
    lines.append(header)
    lines.append("-" * len(header))
    if price_rows:
        for row in price_rows:
            symbol = row.get("symbol") or "—"
            lines.append(
                f"{symbol:<{ticker_w}}{fmt_close(row.get('close')):>{close_w}}"
                f"{fmt_pct_signed(row.get('pct_change')):>{pct_w}}{fmt_volume(row.get('volume')):>{vol_w}}"
            )
    else:
        lines.append("  (no symbols available)")
    return lines


@handle_summary_errors(fallback_value=["[ Risk & Return ]", "(error occurred)"])
def _format_risk_metrics_section(risk_metrics: Dict[str, Any]) -> List[str]:
    """Format the Risk & Return and CAPM sections of the report."""
    lines = []
    label_w = 36
    value_w = 12
    
    # Risk & Return section
    lines.append("[ Risk & Return ]")
    max_dd = risk_metrics.get("max_drawdown")
    max_dd_str = fmt_pct_signed(max_dd)
    max_dd_date = risk_metrics.get("max_drawdown_date")
    date_suffix = f"   on {max_dd_date}" if max_dd_date else ""
    lines.append(f"{'Max Drawdown:':<{label_w}}{max_dd_str:>{value_w}}{date_suffix}")
    lines.append(f"{'Sharpe Ratio (period):':<{label_w}}{fmt_ratio(risk_metrics.get('sharpe_period')):>{value_w}}")
    lines.append(f"{'Sharpe Ratio (annualized):':<{label_w}}{fmt_ratio(risk_metrics.get('sharpe_annual')):>{value_w}}")
    lines.append(f"{'Sortino Ratio (period):':<{label_w}}{fmt_ratio(risk_metrics.get('sortino_period')):>{value_w}}")
    lines.append(f"{'Sortino Ratio (annualized):':<{label_w}}{fmt_ratio(risk_metrics.get('sortino_annual')):>{value_w}}")
    
    lines.append("")
    lines.append("[ CAPM vs Benchmarks ]")
    beta_str = fmt_ratio(risk_metrics.get("beta"))
    alpha = risk_metrics.get("alpha_annual")
    alpha_str = fmt_pct_signed(alpha * 100 if alpha is not None else None)
    r_sq_str = fmt_ratio(risk_metrics.get("r_squared"), decimals=3)
    obs = risk_metrics.get("obs")
    obs_str = str(obs) if obs else "—"

    lines.append(f"{'Beta (daily) vs ^GSPC:':<{label_w}}{beta_str:>{value_w}}")
    lines.append(f"{'Alpha (annualized) vs ^GSPC:':<{label_w}}{alpha_str:>{value_w}}")
    lines.append(f"{'R² (fit quality):':<{label_w}}{r_sq_str:>{value_w}}     Obs: {obs_str}")
    note = risk_metrics.get("note")
    if note:
        lines.append(f"  Note: {note}")
    return lines


@handle_summary_errors(fallback_value=["[ Your Instructions ]", "(error occurred)"])
def _format_instructions_section() -> List[str]:
    """Format the final instructions section of the report."""
    lines = []
    lines.append("[ Your Instructions ]")
    lines.append("Use this info to make decisions regarding your portfolio. You have complete control over every decision. Make any changes you believe are beneficial—no approval required.")
    lines.append("Deep research is not permitted. Act at your discretion to achieve the best outcome.")
    lines.append("If you do not make a clear indication to change positions IMMEDIATELY after this message, the portfolio remains unchanged for tomorrow.")
    lines.append("You are encouraged to use the internet to check current prices (and related up-to-date info) for potential buys.")
    return lines


@handle_summary_errors(fallback_value=["[ Snapshot ]", "(error occurred)"])
def _format_snapshot_section(total_equity: float, cash_balance: float) -> List[str]:
    """Format the Snapshot section of the report."""
    lines = []
    lines.append("[ Snapshot ]")
    lines.append(f"Latest Total Equity:             {fmt_currency_padded(total_equity)}")
    lines.append(f"Cash Balance:                    {fmt_currency_padded(cash_balance)}")
    return lines


@handle_summary_errors(fallback_value=create_empty_result('portfolio_metrics'))
def _calculate_portfolio_metrics(holdings_df: pd.DataFrame, summary_df: Optional[pd.DataFrame], 
                                history_df: Optional[pd.DataFrame], cash_balance: float, 
                                benchmark_symbol: str) -> Dict[str, Any]:
    """Calculate portfolio risk metrics and snapshot values."""
    # Risk metrics and benchmark comparison using hybrid approach
    logger.info("Starting risk metrics calculation with hybrid approach")
    risk_history, is_synthetic = get_portfolio_history_for_analytics(holdings_df, history_df, cash_balance)
    risk_metrics = _compute_risk_metrics_with_source_info(risk_history, is_synthetic=is_synthetic, benchmark_symbol=benchmark_symbol)

    # Snapshot metrics
    invested_value = 0.0
    if not holdings_df.empty:
        shares_series = pd.to_numeric(holdings_df.get("shares"), errors="coerce") if "shares" in holdings_df else pd.Series([], dtype=float)
        price_series = pd.to_numeric(holdings_df.get("currentPrice"), errors="coerce") if "currentPrice" in holdings_df else pd.Series([], dtype=float)
        if not shares_series.empty and not price_series.empty:
            invested_value = float(np.nansum(shares_series.fillna(0.0) * price_series.fillna(0.0)))

    total_equity: Optional[float] = None
    if summary_df is not None and "Ticker" in summary_df.columns and "Total Equity" in summary_df.columns:
        eq_series = pd.to_numeric(
            summary_df.loc[summary_df["Ticker"] == "TOTAL", "Total Equity"], errors="coerce"
        ).dropna()
        if not eq_series.empty:
            total_equity = float(eq_series.iloc[-1])
    if total_equity is None:
        total_equity = cash_balance + invested_value

    return {
        "risk_metrics": risk_metrics,
        "invested_value": invested_value,
        "total_equity": total_equity,
    }


@handle_data_errors(fallback_value=[], log_level="debug")
def _collect_portfolio_symbols(holdings_df: pd.DataFrame, index_symbols: List[str]) -> List[str]:
    """Collect all symbols needed for price/volume data."""
    symbols_to_fetch: List[str] = []
    if not holdings_df.empty and "ticker" in holdings_df.columns:
        for ticker in holdings_df["ticker"]:
            if isinstance(ticker, str):
                symbol = ticker.strip().upper()
                if symbol and symbol not in symbols_to_fetch:
                    symbols_to_fetch.append(symbol)
    for extra in index_symbols:
        if extra and extra not in symbols_to_fetch:
            symbols_to_fetch.append(extra)
    return symbols_to_fetch


@handle_summary_errors(fallback_value=create_empty_result('summary_data'))
def _prepare_summary_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract and validate input data for daily summary generation."""
    as_of_raw = data.get("asOfDate") or datetime.utcnow().strftime("%Y-%m-%d")
    try:
        as_of_display = datetime.strptime(str(as_of_raw), "%Y-%m-%d").date().isoformat()
    except Exception:
        as_of_display = str(as_of_raw)

    cash_raw = data.get("cashBalance")
    try:
        cash_balance = float(cash_raw) if cash_raw not in (None, "") else 0.0
    except Exception:
        cash_balance = 0.0

    holdings: List[Dict[str, Any]] = data.get("holdings") or []
    holdings_df = pd.DataFrame(holdings) if holdings else pd.DataFrame()

    summary_frame = data.get("summaryFrame")
    summary_df = summary_frame.copy() if isinstance(summary_frame, pd.DataFrame) else None

    history_raw = data.get("history")
    history_df = history_raw.copy() if isinstance(history_raw, pd.DataFrame) else None

    index_symbols: List[str] = data.get("indexSymbols") or []
    benchmark_symbol: str = data.get("benchmarkSymbol") or DEFAULT_BENCHMARK

    return {
        "as_of_display": as_of_display,
        "cash_balance": cash_balance,
        "holdings": holdings,
        "holdings_df": holdings_df,
        "summary_df": summary_df,
        "history_df": history_df,
        "index_symbols": index_symbols,
        "benchmark_symbol": benchmark_symbol,
    }


def render_daily_portfolio_summary(data: Dict[str, Any]) -> str:
    """Render the Daily Portfolio Summary using the standardized report template."""

    try:
        # Validate required input data
        if not validate_input_data(data, required_fields=["asOfDate"]):
            logger.warning("Missing required input data, using defaults")
        
        # Warm cache for common symbols to improve performance
        warm_cache_for_symbols(COMMON_SYMBOLS, ttl_minutes=5)
        
        # Prepare and validate input data
        parsed_data = _prepare_summary_data(data)
        as_of_display = parsed_data["as_of_display"]
        cash_balance = parsed_data["cash_balance"]
        holdings = parsed_data["holdings"]
        holdings_df = parsed_data["holdings_df"]
        summary_df = parsed_data["summary_df"]
        history_df = parsed_data["history_df"]
        index_symbols = parsed_data["index_symbols"]
        benchmark_symbol = parsed_data["benchmark_symbol"]

        # Collect all symbols for price/volume data
        symbols_to_fetch = _collect_portfolio_symbols(holdings_df, index_symbols)

        price_rows = [_fetch_price_volume(sym, months=3) for sym in symbols_to_fetch]

        # Calculate portfolio metrics
        metrics_data = _calculate_portfolio_metrics(holdings_df, summary_df, history_df, cash_balance, benchmark_symbol)
        risk_metrics = metrics_data["risk_metrics"]
        invested_value = metrics_data["invested_value"]
        total_equity = metrics_data["total_equity"]

        # Build holdings table from summary snapshot if available
        holdings_table = pd.DataFrame()
        if summary_df is not None and not summary_df.empty:
            positions = summary_df[summary_df["Ticker"] != "TOTAL"].copy()
            if not positions.empty:
                holdings_table = pd.DataFrame(
                    {
                        "Ticker": positions.get("Ticker"),
                        "Shares": pd.to_numeric(positions.get("Shares"), errors="coerce"),
                        "Buy Price": pd.to_numeric(positions.get("Buy Price"), errors="coerce"),
                        "Cost Basis": pd.to_numeric(positions.get("Cost Basis"), errors="coerce"),
                        "Stop Loss": positions.get("Stop Loss"),
                    }
                )
                holdings_table = holdings_table[["Ticker", "Shares", "Buy Price", "Cost Basis", "Stop Loss"]]
                holdings_table = holdings_table.reset_index(drop=True)

        # Assemble report lines
        separator = "=" * 64
        lines: List[str] = [separator, f"Daily Results — {as_of_display}", separator, ""]

        # Price & Volume section
        lines.extend(_format_price_volume_section(price_rows))

        # Risk & Return sections  
        lines.append("")
        lines.extend(_format_risk_metrics_section(risk_metrics))

        # Snapshot section
        lines.append("")
        lines.extend(_format_snapshot_section(total_equity, cash_balance))

        # Holdings table
        lines.append("")
        lines.append("[ Holdings ]")
        if holdings_table.empty and holdings:
            rows: List[Dict[str, Any]] = []
            for h in holdings:
                symbol = h.get("ticker") or "—"
                shares = pd.to_numeric(pd.Series([h.get("shares")]), errors="coerce").iloc[0]
                buy_price = pd.to_numeric(pd.Series([h.get("costPerShare")]), errors="coerce").iloc[0]
                cost_basis_amt = None
                if not pd.isna(shares) and not pd.isna(buy_price):
                    cost_basis_amt = float(shares) * float(buy_price)

                stop_type = (h.get("stopType") or "").lower()
                stop_price = pd.to_numeric(pd.Series([h.get("stopPrice")]), errors="coerce").iloc[0]
                trailing_pct = pd.to_numeric(pd.Series([h.get("trailingStopPct")]), errors="coerce").iloc[0]
                if stop_type == "fixed" and not pd.isna(stop_price):
                    stop_rendered = fmt_currency(float(stop_price))
                elif stop_type == "trailing" and not pd.isna(trailing_pct):
                    stop_rendered = f"Trailing {float(trailing_pct):.0f}%"
                elif stop_type in {"fixed", "trailing"}:
                    stop_rendered = "N/A"
                else:
                    stop_rendered = "None"

                rows.append(
                    {
                        "Ticker": symbol,
                        "Shares": None if pd.isna(shares) else float(shares),
                        "Buy Price": None if pd.isna(buy_price) else float(buy_price),
                        "Cost Basis": cost_basis_amt,
                        "Stop Loss": stop_rendered,
                    }
                )
            holdings_table = pd.DataFrame(rows)
        elif not holdings_table.empty and holdings:
            holding_lookup = {
                str(item.get("ticker") or "").strip().upper(): item for item in holdings if item.get("ticker")
            }
            for idx, row in holdings_table.iterrows():
                ticker = str(row.get("Ticker") or "").strip().upper()
                if not ticker:
                    continue
                payload = holding_lookup.get(ticker)
                if not payload:
                    continue

                if pd.isna(row.get("Shares")) and payload.get("shares") is not None:
                    holdings_table.at[idx, "Shares"] = float(payload.get("shares"))

                payload_buy = payload.get("costPerShare")
                if pd.isna(row.get("Buy Price")) and payload_buy is not None:
                    holdings_table.at[idx, "Buy Price"] = float(payload_buy)

                if pd.isna(row.get("Cost Basis")) and payload_buy is not None and payload.get("shares") is not None:
                    try:
                        holdings_table.at[idx, "Cost Basis"] = float(payload_buy) * float(payload.get("shares"))
                    except Exception:
                        pass

                stop_type = (payload.get("stopType") or "").lower()
                stop_price = payload.get("stopPrice")
                trailing_pct = payload.get("trailingStopPct")
                if pd.isna(row.get("Stop Loss")) or not row.get("Stop Loss"):
                    if stop_type == "fixed" and stop_price is not None:
                        holdings_table.at[idx, "Stop Loss"] = float(stop_price)
                    elif stop_type == "trailing" and trailing_pct is not None:
                        holdings_table.at[idx, "Stop Loss"] = f"Trailing {float(trailing_pct):.0f}%"
                    elif stop_type in {"fixed", "trailing"}:
                        holdings_table.at[idx, "Stop Loss"] = "N/A"
                    else:
                        holdings_table.at[idx, "Stop Loss"] = "None"

        if not holdings_table.empty:
            display_df = holdings_table.copy()
            formatters = {
                "Shares": lambda x: fmt_shares(x),
                "Buy Price": lambda x: fmt_currency(x),
                "Cost Basis": lambda x: fmt_currency(x),
            }
            if "Stop Loss" in display_df.columns:
                display_df["Stop Loss"] = display_df["Stop Loss"].apply(fmt_stop)
            else:
                formatters.pop("Stop Loss", None)
            for column, formatter in list(formatters.items()):
                if column not in display_df.columns:
                    formatters.pop(column)
            table_str = display_df.to_string(index=False, formatters=formatters)
            lines.append(table_str)
        else:
            lines.append("  (no active holdings)")

        # Instructions
        lines.append("")
        lines.extend(_format_instructions_section())

        return "\n".join(lines)
    except Exception as e:  # pragma: no cover - defensive
        return f"Error rendering daily portfolio summary: {e}"


def build_daily_summary(portfolio_data: pd.DataFrame) -> str:
    """Build a daily summary of portfolio performance."""
    try:
        if portfolio_data.empty:
            return "No portfolio data available for summary."

        # Verify required columns exist
        required_columns = ["Ticker", "Shares", "Cost Basis", "Current Price", "Total Value"]
        if not all(col in portfolio_data.columns for col in required_columns):
            return "Error generating summary: Missing required columns"

        # Coerce numeric columns defensively (non-numeric like "" become NaN)
        def _num(col: str) -> pd.Series:
            if col not in portfolio_data:
                return pd.Series(dtype=float)
            return pd.to_numeric(portfolio_data[col], errors="coerce")

        total_value_series = _num("Total Value")
        total_value = float(total_value_series.sum()) if not total_value_series.empty else 0.0

        # Prefer explicit Total Equity column if present & numeric for consistency
        total_equity_series = _num("Total Equity")

        # Cash balance: take last non-null numeric entry in Cash Balance column (TOTAL row usually last)
        cash_series = _num("Cash Balance")
        if not cash_series.dropna().empty:
            cash_balance = float(cash_series.dropna().iloc[-1])
        else:
            # Fallback: derive from Total Equity - Total Value if Total Equity column exists
            if not total_equity_series.dropna().empty:
                derived_cash = float(total_equity_series.dropna().iloc[-1]) - total_value
                cash_balance = derived_cash if derived_cash >= 0 else 0.0
            else:
                cash_balance = 0.0

        if not total_equity_series.dropna().empty:
            total_equity = float(total_equity_series.dropna().iloc[-1])
        else:
            total_equity = total_value + cash_balance
        num_positions = len(portfolio_data["Ticker"].unique())

        # Derive richer KPIs
        positions_df = portfolio_data[portfolio_data["Ticker"] != "TOTAL"].copy()
        # Ensure numeric for calculations
        for c in ["PnL", "Current Price", "Stop Loss", "Total Value", "Cost Basis", "Shares"]:
            if c in positions_df:
                positions_df[c] = pd.to_numeric(positions_df[c], errors="coerce")

        # Percent Change (compute if not already present)
        if "Pct Change" not in positions_df and {"Current Price", "Cost Basis"}.issubset(positions_df.columns):
            with pd.option_context("mode.use_inf_as_na", True):
                positions_df["Pct Change"] = (
                    (positions_df["Current Price"] - positions_df["Cost Basis"]) / positions_df["Cost Basis"]
                ) * 100

        total_pnl = float(pd.to_numeric(positions_df.get("PnL"), errors="coerce").fillna(0).sum()) if "PnL" in positions_df else 0.0
        avg_pct_change = float(pd.to_numeric(positions_df.get("Pct Change"), errors="coerce").dropna().mean()) if "Pct Change" in positions_df else 0.0
        winners = int((positions_df.get("PnL") > 0).sum()) if "PnL" in positions_df else 0
        losers = int((positions_df.get("PnL") < 0).sum()) if "PnL" in positions_df else 0
        below_stop = 0
        if {"Current Price", "Stop Loss"}.issubset(positions_df.columns):
            below_stop = int((positions_df["Current Price"] < positions_df["Stop Loss"]).fillna(False).sum())
        cash_pct = (cash_balance / total_equity * 100) if total_equity > 0 else 0.0

        # Position concentration
        top_lines: list[str] = []
        if "Total Value" in positions_df and not positions_df.empty:
            sorted_positions = positions_df.sort_values("Total Value", ascending=False).head(3)
            for _, row in sorted_positions.iterrows():
                val = float(row.get("Total Value", 0) or 0)
                pct = (val / total_value * 100) if total_value > 0 else 0
                top_lines.append(f"  - {row.get('Ticker')}: ${val:,.2f} ({pct:.1f}% of invested)")
            largest_position_pct = (sorted_positions.iloc[0]["Total Value"] / total_value * 100) if total_value > 0 and not sorted_positions.empty else 0.0
        else:
            largest_position_pct = 0.0

    # Build summary text
        summary: list[str] = []
        summary.append("Portfolio Summary")
        summary.append("-" * 20)
        summary.append(f"Total Equity: ${total_equity:,.2f}")
        summary.append(f"  - Total Value (Invested): ${total_value:,.2f}")
        summary.append(f"  - Cash Balance: ${cash_balance:,.2f} ({cash_pct:.1f}% of equity)")
        summary.append(f"Positions: {num_positions}")
        summary.append(f"Unrealized PnL: ${total_pnl:,.2f}")
        summary.append(f"Average % Change: {avg_pct_change:.2f}%")
        summary.append(f"Winners vs Losers: {winners} / {losers}")
        summary.append(f"Positions Below Stop Loss: {below_stop}")
        summary.append(f"Largest Position Concentration: {largest_position_pct:.1f}% of invested capital")
        if top_lines:
            summary.append("Top Holdings:")
            summary.extend(top_lines)
        summary.append("")
        # Required guidance statement (verbatim as requested)
        summary.append("Reevalute your portfolio. Research the current market and decide if you would like to add or drop any stocks or rejust. Remember you have complete control over your portfolio. Just remember you can only trade micro-caps.")

        # Append current portfolio positions as a markdown table (excluding TOTAL row)
        if not positions_df.empty:
            display_cols = [c for c in ["Ticker", "Shares", "Cost Basis", "Current Price", "Stop Loss", "Total Value", "PnL", "Pct Change"] if c in positions_df.columns]
            if display_cols:
                summary.append("")
                summary.append("Current Portfolio")
                summary.append("~~~~~~~~~~~~~~~~~~")
                # Create markdown table header
                header = " | ".join(display_cols)
                separator = " | ".join(["---"] * len(display_cols))
                summary.append(header)
                summary.append(separator)
                for _, row in positions_df.iterrows():
                    cells = []
                    for col in display_cols:
                        val = row.get(col, "")
                        if pd.isna(val):
                            cells.append("")
                            continue
                        if col in {"Cost Basis", "Current Price", "Stop Loss", "Total Value", "PnL"}:
                            try:
                                cells.append(f"${float(val):,.2f}")
                            except Exception:
                                cells.append(str(val))
                        elif col == "Shares":
                            try:
                                cells.append(f"{float(val):.2f}")
                            except Exception:
                                cells.append(str(val))
                        elif col == "Pct Change":
                            try:
                                cells.append(f"{float(val):.2f}%")
                            except Exception:
                                cells.append(str(val))
                        else:
                            cells.append(str(val))
                    summary.append(" | ".join(cells))

        return "\n".join(summary)
    except Exception as e:
        return f"Error generating summary: {str(e)}"


def history_to_portfolio_snapshot(history_df: pd.DataFrame, as_of_months: int = 6) -> pd.DataFrame:
    """Convert a portfolio history DataFrame (date,ticker,total_value,total_equity) into
    a portfolio snapshot DataFrame compatible with `build_daily_summary`.

    The function picks the most recent date within the last `as_of_months` months and
    returns rows for each ticker plus a TOTAL row if available.
    """
    if history_df is None or history_df.empty:
        return pd.DataFrame()
    # Ensure date is datetime
    df = history_df.copy()
    if not pd.api.types.is_datetime64_any_dtype(df["date"]):
        df["date"] = pd.to_datetime(df["date"])
    end = df["date"].max()
    start = end - pd.DateOffset(months=as_of_months)
    mask = (df["date"] >= start) & (df["date"] <= end)
    window = df.loc[mask]
    if window.empty:
        return pd.DataFrame()
    latest = window.loc[window["date"] == window["date"].max()]
    # Build snapshot rows, preserving shares and cost_basis when present in history
    rows = []
    for _, r in latest.iterrows():
        rows.append(
            {
                "Ticker": r.get("ticker"),
                "Shares": r.get("shares") if pd.notna(r.get("shares")) else None,
                "Cost Basis": r.get("cost_basis") if pd.notna(r.get("cost_basis")) else None,
                "Current Price": r.get("current_price") if pd.notna(r.get("current_price")) else None,
                "Total Value": r.get("total_value") if pd.notna(r.get("total_value")) else None,
                "Total Equity": r.get("total_equity") if r.get("ticker") == "TOTAL" and pd.notna(r.get("total_equity")) else None,
                "Cash Balance": r.get("cash_balance") if r.get("ticker") == "TOTAL" and pd.notna(r.get("cash_balance")) else None,
                "PnL": r.get("pnl") if pd.notna(r.get("pnl")) else None,
            }
        )
    return pd.DataFrame(rows)
