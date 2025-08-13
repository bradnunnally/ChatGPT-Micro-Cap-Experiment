from datetime import datetime
import os

import pandas as pd
import streamlit as st

from app_settings import settings
from core.errors import ValidationError
from data.portfolio import save_portfolio_snapshot
from services.core.market_service import MarketService
from services.core.portfolio_service import PortfolioService
from services.session import init_session_state
from services.time import TradingCalendar, get_clock
from ui.cash import show_cash_section
from ui.forms import show_buy_form, show_sell_form
from ui.manual_pricing import show_manual_pricing_section, show_api_status_warning
from ui.summary import build_daily_summary, render_daily_portfolio_summary


def fmt_currency(val: float) -> str:
    """Format value as currency."""
    try:
        val = float(val)
        return f"${val:,.2f}" if val >= 0 else f"-${abs(val):,.2f}"
    except (ValueError, TypeError):
        return ""


def fmt_percent(val: float) -> str:
    """Format value as percentage with arrow."""
    try:
        val = float(val)
        if val > 0:
            return f"+{val:.1f}% ↑"
        elif val < 0:
            return f"{val:.1f}% ↓"
        return f"{val:.1f}%"
    except (ValueError, TypeError):
        return ""


def fmt_percent_2dp(val: float) -> str:
    """Format percentage with 2 decimal places (no arrows)."""
    try:
        val = float(val)
        return f"{val:.2f}%"
    except (ValueError, TypeError):
        return ""


def fmt_shares(val: float) -> str:
    """Format share count."""
    try:
        return f"{int(float(val)):,}"
    except (ValueError, TypeError):
        return ""


def color_pnl(val: float) -> str:
    """Color formatting for P&L values."""
    try:
        val = float(val)
        if val > 0:
            return "color: green"
        elif val < 0:
            return "color: red"
        return ""
    except (ValueError, TypeError):
        return ""


def highlight_stop(row: pd.Series) -> list:
    """Highlight row if price is below stop loss."""
    try:
        return [
            "background-color: #ffcccc" if row["Current Price"] < row["Stop Loss"] else ""
            for _ in range(len(row))
        ]
    except (KeyError, TypeError):
        return [""] * len(row)


def highlight_pct(val) -> str:
    """Highlight percentage changes for individual values."""
    try:
        if pd.isna(val):
            return ""
        if val > 0:
            return "color: green"
        elif val < 0:
            return "color: red"
        else:
            return ""
    except (TypeError, ValueError):
        return ""


def initialize_services():
    """Initialize services in session state."""
    if "portfolio_service" not in st.session_state:
        st.session_state.portfolio_service = PortfolioService()
    if "market_service" not in st.session_state:
        st.session_state.market_service = MarketService()
        # cache flag for micro provider use
        if "use_micro_providers" not in st.session_state:
            st.session_state.use_micro_providers = bool(
                os.getenv("ENABLE_MICRO_PROVIDERS") == "1" or os.getenv("APP_USE_FINNHUB") == "1"
            )


def render_dashboard() -> None:
    """Render the main dashboard view."""

    init_session_state()
    # Ensure services + micro provider flag initialized early
    try:
        initialize_services()
    except Exception:
        pass

    feedback = st.session_state.pop("feedback", None)
    if feedback:
        kind, text = feedback
        getattr(st, kind)(text)

    if st.session_state.get("needs_cash", False):
        st.subheader("Initialize Portfolio")
        with st.form("init_cash_form", clear_on_submit=True):
            start_cash_raw = st.text_input(
                "Enter starting cash", key="start_cash", placeholder="0.00"
            )
            init_submit = st.form_submit_button("Set Starting Cash", type="primary")
        if init_submit:
            try:
                start_cash = float(start_cash_raw)
                if start_cash <= 0:
                    raise ValidationError("Starting cash must be positive.")
            except ValidationError:
                st.session_state.feedback = (
                    "error",
                    "Please enter a positive number.",
                )
            else:
                st.session_state.cash = start_cash
                st.session_state.needs_cash = False
                save_portfolio_snapshot(st.session_state.portfolio, st.session_state.cash)
                st.session_state.feedback = (
                    "success",
                    f"Starting cash of ${start_cash:.2f} recorded.",
                )
            st.session_state.pop("start_cash", None)
            st.rerun()
    else:
        summary_df = save_portfolio_snapshot(st.session_state.portfolio, st.session_state.cash)

        summary_df = summary_df.rename(
            columns={
                "date": "Date",
                "ticker": "Ticker",
                "shares": "Shares",
                "cost_basis": "Cost Basis",
                "stop_loss": "Stop Loss",
                "current_price": "Current Price",
                "total_value": "Total Value",
                "pnl": "PnL",
                "action": "Action",
                "price_source": "Price Source",
                "cash_balance": "Cash Balance",
                "total_equity": "Total Equity",
            }
        )

        # --- Derive replacement metrics for per-position rows (leave underlying Cash/Equity intact) ---
        try:
            total_equity_val = float(
                summary_df.loc[summary_df["Ticker"] == "TOTAL", "Total Equity"].iloc[0]
            )
        except Exception:
            total_equity_val = 0.0
        try:
            cash_balance_val = float(
                summary_df.loc[summary_df["Ticker"] == "TOTAL", "Cash Balance"].iloc[0]
            )
        except Exception:
            cash_balance_val = 0.0
        denom = total_equity_val if total_equity_val > 0 else None

        # Initialize new columns
        summary_df["Market/Value Metric"] = ""
        summary_df["Quality Metric"] = ""

        mask_positions = summary_df["Ticker"] != "TOTAL"
        if denom:
            # Position weight (%) of total equity
            with pd.option_context("mode.use_inf_as_na", True):
                summary_df.loc[mask_positions, "Market/Value Metric"] = (
                    (summary_df.loc[mask_positions, "Total Value"].astype(float) / denom) * 100.0
                ).round(2)
        else:
            summary_df.loc[mask_positions, "Market/Value Metric"] = 0.0

        # Quality metric: ROI % ((Current - Cost)/Cost) * 100; guard divide by zero
        cost = summary_df.loc[mask_positions, "Cost Basis"].replace({0: pd.NA}).astype(float)
        cur = summary_df.loc[mask_positions, "Current Price"].astype(float)
        roi = ((cur - cost) / cost * 100.0).round(2)
        roi = roi.fillna(0.0)
        summary_df.loc[mask_positions, "Quality Metric"] = roi

        # For TOTAL row provide overall cash % and aggregate ROI as empty (not meaningful)
        if "TOTAL" in summary_df["Ticker"].values and denom:
            # Cash weight relative to equity (cash / total_equity *100)
            try:
                summary_df.loc[summary_df["Ticker"] == "TOTAL", "Market/Value Metric"] = round(
                    (cash_balance_val / denom) * 100.0, 2
                )
            except Exception:
                pass
            summary_df.loc[summary_df["Ticker"] == "TOTAL", "Quality Metric"] = ""

        # Cash section (left) + Market status banner (right)
        cash_col, status_col = st.columns([1, 1])
        with cash_col:
            show_cash_section()
        with status_col:
            st.subheader("Market Status")
            clock = get_clock()
            cal = TradingCalendar(clock=clock)
            if settings.trading_holidays:
                try:
                    cal.holidays = set(settings.trading_holidays)  # type: ignore[attr-defined]
                except Exception:
                    pass
            now_ts = clock.now()
            is_open = cal.is_market_open(now_ts)

            # Helper to format a time in ET
            def _fmt(dt: datetime) -> str:
                return dt.strftime("%I:%M %p")

            if is_open:
                close_dt = datetime.combine(now_ts.date(), cal.market_close).replace(
                    tzinfo=clock.tz
                )
                st.success(f"Open — until {_fmt(close_dt)} ET")
            else:
                # Determine next open
                if (
                    cal.is_trading_day(now_ts.date())
                    and now_ts.timetz().replace(tzinfo=None) < cal.market_open
                ):
                    next_day = now_ts.date()
                else:
                    next_day = cal.next_trading_day(now_ts.date())
                next_open_dt = datetime.combine(next_day, cal.market_open).replace(tzinfo=clock.tz)
                day_label = (
                    "today" if next_day == now_ts.date() else next_open_dt.strftime("%a %b %d")
                )
                st.warning(f"Closed — opens {_fmt(next_open_dt)} ET {day_label}")

            # --- Provider Mode + Caption (always shown) ---
            app_env = os.getenv("APP_ENV", "production")
            if app_env != "production":
                st.caption("Provider Mode")
                toggled = st.toggle(
                    "Use micro providers (Finnhub/Synthetic)",
                    value=st.session_state.get("use_micro_providers", False),
                    help="When enabled and FINNHUB_API_KEY set (production), uses Finnhub; in dev uses synthetic.",
                )
                st.session_state.use_micro_providers = toggled

            # Decide caption text
            caption_txt = "Provider: "
            if st.session_state.get("use_micro_providers"):
                caption_txt += "Finnhub" if app_env == "production" else "Synthetic"
            else:
                caption_txt += "Disabled (fallback only)"
            st.caption(caption_txt)

        port_table = summary_df[summary_df["Ticker"] != "TOTAL"].copy()
        # Drop legacy cash/equity columns from per-position display
        for legacy_col in ["Cash Balance", "Total Equity"]:
            if legacy_col in port_table.columns:
                port_table.drop(columns=[legacy_col], inplace=True)
        header_cols = st.columns([4, 1, 1])
        with header_cols[0]:
            st.subheader("Current Portfolio")

        if port_table.empty:
            st.info("Your portfolio is empty. Use the Buy form below to add your first position.")
        else:
            try:  # pragma: no cover - optional dependency
                from streamlit_autorefresh import st_autorefresh

                # Refresh every 30 minutes (1,800,000 milliseconds)
                st_autorefresh(interval=1_800_000, key="portfolio_refresh")
            except ImportError:  # pragma: no cover - import-time failure
                st.warning("Install streamlit-autorefresh for auto refresh support.")

            if not st.session_state.portfolio.empty:
                # Safely get the timestamp or use current time as fallback
                if "timestamp" in st.session_state.portfolio.columns:
                    last_update = st.session_state.portfolio["timestamp"].max()
                else:
                    last_update = get_clock().now()

                formatted_time = last_update.strftime("%B %d, %Y at %I:%M %p")
                st.caption(f"Last updated: {formatted_time}")

            numeric_cols = [
                "Shares",
                "Cost Basis",
                "Current Price",
                "Stop Loss",
                "Total Value",
                "PnL",
            ]
            for col in numeric_cols:
                if col in port_table.columns:
                    port_table[col] = pd.to_numeric(port_table[col], errors="coerce")

            if {"Current Price", "Cost Basis"}.issubset(port_table.columns):
                port_table["Pct Change"] = (
                    (port_table["Current Price"] - port_table["Cost Basis"])
                    / port_table["Cost Basis"]
                ) * 100

            port_table.rename(
                columns={"Cost Basis": "Buy Price", "Total Value": "Value"},
                inplace=True,
            )
            # Cache micro provider capabilities once per session to avoid repeated API calls
            if st.session_state.get("use_micro_providers") and "micro_capabilities" not in st.session_state:
                try:
                    from micro_config import get_provider as _gp
                    prov = _gp()
                    caps = getattr(prov, "get_capabilities", lambda: {})()
                    st.session_state.micro_capabilities = caps
                except Exception:
                    st.session_state.micro_capabilities = {}

            # Hide unsupported columns based on capabilities (ADV20 relies on candles; Spread on bidask)
            caps = st.session_state.get("micro_capabilities") if st.session_state.get("use_micro_providers") else None
            if caps:
                if not caps.get("candles", True) and "ADV20" in port_table.columns:
                    port_table.drop(columns=["ADV20"], inplace=True)
                if not caps.get("bidask", True) and "Spread" in port_table.columns:
                    port_table.drop(columns=["Spread"], inplace=True)

            for col in [
                "Shares",
                "Buy Price",
                "Current Price",
                "Stop Loss",
                "Value",
                "PnL",
                "Pct Change",
                "Market/Value Metric",
                "Quality Metric",
            ]:
                if col in port_table:
                    port_table[col] = pd.to_numeric(port_table[col], errors="coerce")

            formatters = {}
            if "Shares" in port_table:
                formatters["Shares"] = fmt_shares
            for c in ["Buy Price", "Current Price", "Stop Loss", "Value", "PnL"]:
                if c in port_table:
                    formatters[c] = fmt_currency
            if "Pct Change" in port_table:
                formatters["Pct Change"] = fmt_percent
            if "Market/Value Metric" in port_table:
                formatters["Market/Value Metric"] = fmt_percent_2dp
            if "Quality Metric" in port_table:
                formatters["Quality Metric"] = fmt_percent_2dp

            numeric_display = list(formatters.keys())

            styled = port_table.style.format(formatters).set_properties(
                subset=numeric_display, **{"text-align": "right"}
            )
            # Pandas Styler.applymap deprecated -> use .map (element-wise) for new versions
            if "Pct Change" in port_table:
                styled = styled.map(highlight_pct, subset=["Pct Change"])  # type: ignore[attr-defined]
            if "PnL" in port_table:
                styled = styled.map(color_pnl, subset=["PnL"])  # type: ignore[attr-defined]
            styled = styled.apply(highlight_stop, axis=1).set_table_styles(
                [
                    {
                        "selector": "th",
                        "props": [
                            ("font-size", "16px"),
                            ("text-align", "center"),
                        ],
                    },
                    {
                        "selector": "td",
                        "props": [
                            ("font-size", "16px"),
                            ("color", "black"),
                        ],
                    },
                ]
            )

            column_config = {
                "Stop Loss": st.column_config.NumberColumn(
                    "Stop Loss", help="Price at which the stock will be sold to limit loss"
                ),
                "Pct Change": st.column_config.NumberColumn(
                    "Pct Change", help="Percentage change since purchase"
                ),
                "PnL": st.column_config.NumberColumn("PnL", help="Profit or loss"),
                "Value": st.column_config.NumberColumn("Value", help="Current market value"),
                "Buy Price": st.column_config.NumberColumn(
                    "Buy Price", help="Average price paid per share"
                ),
                "Price Source": st.column_config.TextColumn(
                    "Price Source", help="Source of current price (Live, Last Close, Manual)"
                ),
                "Market/Value Metric": st.column_config.NumberColumn(
                    "Weight %", help="Position weight as percentage of total equity", format="%.2f%%"
                ),
                "Quality Metric": st.column_config.NumberColumn(
                    "ROI %", help="Return on investment percentage", format="%.2f%%"
                ),
            }
            st.dataframe(
                styled,
                use_container_width=True,
                column_config=column_config,
                hide_index=True,
            )

        # Check if all portfolio positions have zero current prices (API issues)
        if not port_table.empty and all(port_table.get("Current Price", [1]) == 0):
            show_api_status_warning()
        
        # Manual pricing section for when APIs fail
        show_manual_pricing_section()

        show_buy_form()
        if not port_table.empty:
            show_sell_form()

        st.subheader("Daily Summary")
        if st.button("Generate Daily Summary", type="primary"):
            if not summary_df.empty:
                # Build new structured data payload for enhanced summary renderer
                holdings_payload = []
                positions_only = summary_df[summary_df["Ticker"] != "TOTAL"].copy()
                for _, row in positions_only.iterrows():
                    holdings_payload.append(
                        {
                            "ticker": row.get("Ticker"),
                            "exchange": row.get("Exchange", "N/A"),
                            "sector": row.get("Sector", "N/A"),
                            "shares": row.get("Shares"),
                            "costPerShare": row.get("Cost Basis"),
                            "currentPrice": row.get("Current Price"),
                            # Map any existing stop fields; default None
                            "stopType": "None",  # legacy data doesn't track stops yet
                            "stopPrice": None,
                            "trailingStopPct": None,
                            "marketCap": row.get("Market Cap"),
                            "adv20d": row.get("ADV20"),
                            "spread": row.get("Spread"),
                            "catalystDate": row.get("Catalyst"),
                        }
                    )
                payload = {
                    "asOfDate": datetime.now().strftime("%Y-%m-%d"),
                    "cashBalance": float(summary_df.get("Cash Balance").dropna().iloc[-1]) if "Cash Balance" in summary_df else 0.0,
                    "holdings": holdings_payload,
                    "notes": {"materialNewsToday": "N/A", "catalystNotes": []},
                }
                st.session_state.daily_summary = render_daily_portfolio_summary(payload)
            else:
                st.info("No summary available.")
        if st.session_state.get("daily_summary"):
            st.code(st.session_state.daily_summary, language="markdown")
            st.button(
                "Dismiss Summary",
                key="dismiss_summary",
                on_click=lambda: st.session_state.update(daily_summary=""),
            )

        if st.session_state.get("error_log"):
            st.subheader("Error Log")
            for line in st.session_state.error_log:
                st.text(line)


def format_currency(value: float) -> str:
    """Format a number as currency."""
    is_negative = value < 0
    abs_value = abs(value)
    formatted = f"${abs_value:,.2f}"
    return f"-{formatted}" if is_negative else formatted


def format_percentage(value: float) -> str:
    """Format a number as percentage."""
    return f"{value * 100:.2f}%"


def show_portfolio_summary() -> None:
    """Display portfolio summary metrics."""
    initialize_services()
    metrics = st.session_state.portfolio_service.get_metrics()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Value", f"${metrics.total_value:,.2f}")
    with col2:
        st.metric("Total Gain/Loss", f"${metrics.total_gain:,.2f}")
    with col3:
        st.metric("Total Return", f"{metrics.total_return:.1%}")


def show_holdings_table() -> None:
    """Display holdings table."""
    initialize_services()
    df = st.session_state.portfolio_service.to_dataframe()

    if df.empty:
        st.info("No holdings to display")
        return

    st.dataframe(df)
