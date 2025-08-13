import pandas as pd
from typing import Any, Dict, List, Optional


def fmt_money(n: Optional[float]) -> str:
    if n is None or pd.isna(n):
        return "N/A"
    return f"{n:,.2f}"


def fmt_money_with_dollar(n: Optional[float]) -> str:
    if n is None or pd.isna(n):
        return "N/A"
    return f"${n:,.2f}"


def fmt_pct(n: Optional[float]) -> str:
    if n is None or pd.isna(n):
        return "N/A"
    return f"{n:.2f}%"


def safe(value: Any, fallback: str = "N/A") -> str:
    if value is None:
        return fallback
    if isinstance(value, float) and pd.isna(value):
        return fallback
    return str(value)


def render_daily_portfolio_summary(data: Dict[str, Any]) -> str:
    """Render the Daily Portfolio Summary markdown per new spec.

    Input shape: see user specification in docs / request.
    """
    try:
        as_of = data.get("asOfDate") or "N/A"
        cash = float(data.get("cashBalance") or 0.0)
        holdings: List[Dict[str, Any]] = data.get("holdings") or []

        # Normalize & compute per-holding derived fields
        derived_rows = []
        invested_value = 0.0
        total_unrealized = 0.0
        total_cost_basis = 0.0
        winners = 0
        losers = 0
        below_stop = 0
        any_over_300m = False
        liquidity_checks_possible = False
        liquidity_all_ok = True

        for h in holdings:
            shares = float(h.get("shares") or 0.0)
            cost = float(h.get("costPerShare") or 0.0)
            price = float(h.get("currentPrice") or 0.0)
            value = shares * price
            pnl = (price - cost) * shares
            pct_change = ((price - cost) / cost * 100) if cost > 0 else None
            total_cost_basis += shares * cost
            invested_value += value
            total_unrealized += pnl
            if pnl > 0:
                winners += 1
            elif pnl < 0:
                losers += 1

            stop_type = h.get("stopType") or "None"
            stop_price = h.get("stopPrice")
            trailing_pct = h.get("trailingStopPct")
            if stop_type == "Fixed" and stop_price is not None and price <= float(stop_price):
                below_stop += 1

            if stop_type == "None":
                stop_rendered = "None"
            elif stop_type == "Fixed":
                stop_rendered = f"${float(stop_price):,.2f}" if stop_price is not None else "N/A"
            elif stop_type == "Trailing":
                stop_rendered = f"Trailing {float(trailing_pct):.0f}%" if trailing_pct is not None else "Trailing N/A"
            else:
                stop_rendered = safe(stop_type)

            market_cap = h.get("marketCap")
            if market_cap is not None:
                mc_val = float(market_cap)
                if mc_val >= 300_000_000:
                    any_over_300m = True
            else:
                mc_val = None

            adv20d = h.get("adv20d")
            spread = h.get("spread")
            if adv20d is not None:
                liquidity_checks_possible = True
                try:
                    if float(adv20d) > 0 and shares > 0.1 * float(adv20d):
                        liquidity_all_ok = False
                except Exception:
                    pass

            if spread is None:
                spread_rendered = "N/A"
            else:
                try:
                    spread_rendered = f"{float(spread):.2f}"
                except Exception:
                    spread_rendered = safe(spread)

            catalyst_date = h.get("catalystDate") or "N/A"

            derived_rows.append(
                {
                    "ticker": h.get("ticker") or "N/A",
                    "exchange": h.get("exchange") or "N/A",
                    "sector": h.get("sector") or "N/A",
                    "shares": shares if shares else 0.0,
                    "costPerShare": cost if cost else 0.0,
                    "currentPrice": price if price else 0.0,
                    "stopRendered": stop_rendered,
                    "value": value,
                    "pnl": pnl,
                    "%Change": pct_change,
                    "marketCap": mc_val,
                    "adv20d": adv20d,
                    "spreadRendered": spread_rendered,
                    "catalystRendered": catalyst_date,
                }
            )

        total_equity = cash + invested_value
        cash_pct_equity = (cash / total_equity * 100) if total_equity > 0 else 0.0
        avg_pct_simple = (
            sum(row["%Change"] for row in derived_rows if row["%Change"] is not None) / max(
                1, sum(1 for row in derived_rows if row["%Change"] is not None)
            )
            if derived_rows
            else 0.0
        )
        portfolio_roi = (
            (invested_value - total_cost_basis) / total_cost_basis * 100 if total_cost_basis > 0 else 0.0
        )

        # Concentration
        largest_concentration = (
            max((r["value"] for r in derived_rows), default=0.0) / invested_value * 100
            if invested_value > 0
            else 0.0
        )

        all_microcaps = not any_over_300m and all(
            (r["marketCap"] is None) or (r["marketCap"] < 300_000_000) for r in derived_rows
        )
        micro_cap_compliance = "Yes" if (derived_rows and all_microcaps) else ("No" if derived_rows else "N/A")
        any_over_300m_yn = "Yes" if any_over_300m else "No"
        liquidity_ok = (
            "N/A" if not liquidity_checks_possible else ("Yes" if liquidity_all_ok else "No")
        )

        # Sort holdings by value desc
        derived_rows.sort(key=lambda r: r["value"], reverse=True)
        top_holdings = derived_rows[:2]

        # Build markdown
        lines: List[str] = []
        lines.append(f"Daily Portfolio Summary for {as_of}")
        lines.append("")
        lines.append(f"Total Equity: ${fmt_money(total_equity)}")
        lines.append(f"- Invested Current Value (ex-cash): ${fmt_money(invested_value)}")
        lines.append(
            f"- Cash Balance: ${fmt_money(cash)} ({cash_pct_equity:.2f}% of equity)"
        )
        lines.append(f"Positions: {len(derived_rows)}")
        lines.append(f"Unrealized PnL: ${fmt_money(total_unrealized)}")
        lines.append(f"Average % Change (simple): {fmt_pct(avg_pct_simple)}")
        lines.append(f"Portfolio ROI vs cost: {fmt_pct(portfolio_roi)}")
        lines.append(f"Winners vs Losers: {winners} / {losers}")
        lines.append(f"Positions Below Stop Loss: {below_stop}")
        lines.append(
            f"Largest Position Concentration: {largest_concentration:.2f}% of invested capital"
        )
        lines.append(f"Micro-cap Compliance: {micro_cap_compliance}")
        lines.append("")
        lines.append("Top Holdings:")
        for r in top_holdings:
            concentration_pct = (
                f"{(r['value'] / invested_value * 100):.2f}%" if invested_value > 0 else "0.00%"
            )
            lines.append(
                f"  - {r['ticker']}: ${fmt_money(r['value'])} ({concentration_pct} of invested)"
            )
        lines.append("")
        lines.append(
            "Reevaluate your portfolio. Research the current market and decide if you would like to add or drop any stocks or adjust. You have complete control. Only trade U.S.-listed micro-caps (< $300M)."
        )
        lines.append("")
        lines.append("Current Portfolio")
        header_cols = [
            "Ticker","Exchange","Sector","Shares","Cost/Share","Current","Stop","Value","PnL","% Change","Mkt Cap","20d ADV","Spread","Catalyst"
        ]
        lines.append(" | ".join(header_cols))
        lines.append("--- | --- | --- | ---:| ---:| ---:| --- | ---:| ---:| ---:| ---:| ---:| ---:| ---")
        for r in derived_rows:
            mc_display = f"${fmt_money(r['marketCap'])}" if r["marketCap"] is not None else "N/A"
            adv_display = (
                f"{int(r['adv20d']):,}" if isinstance(r["adv20d"], (int, float)) and not pd.isna(r["adv20d"]) else "N/A"
            )
            pct_change_display = f"{r['%Change']:.2f}%" if r["%Change"] is not None else "N/A"
            row_cells = [
                safe(r["ticker"]),
                safe(r["exchange"]),
                safe(r["sector"]),
                f"{r['shares']:.0f}",
                f"${fmt_money(r['costPerShare'])}",
                f"${fmt_money(r['currentPrice'])}",
                safe(r["stopRendered"]),
                f"${fmt_money(r['value'])}",
                f"${fmt_money(r['pnl'])}",
                pct_change_display,
                mc_display,
                adv_display,
                safe(r["spreadRendered"]),
                safe(r["catalystRendered"]),
            ]
            lines.append(" | ".join(row_cells))
        lines.append("")
        lines.append("Compliance checks")
        lines.append(f"- Any holding ≥ $300M market cap: {any_over_300m_yn}")
        lines.append(
            f"- Liquidity sanity (intended trade size < 10% of 20d ADV): {liquidity_ok}"
        )

        return "\n".join(lines)
    except Exception as e:  # pragma: no cover - defensive
        return f"Error rendering daily portfolio summary: {e}"  # keep simple


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
