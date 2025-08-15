"""Rebalance execution helpers.

Converts proposed rebalance orders (already sized) into portfolio mutations
using pure portfolio functions (no direct Streamlit dependency). This keeps
logic testable and allows UI layer to persist changes afterward.

Order schema expected (list[dict]): each dict contains:
  ticker (str), side (BUY|SELL), shares (int/float), est_price (float),
  value_delta (float), target_weight (float), current_weight (float)

Main function:
  execute_orders(portfolio_df, cash, orders, price_map=None, slippage_bps=0)

Returns:
  updated_portfolio_df, updated_cash, execution_report_df

Failures are reported per order with status field; processing continues
sequentially (no transactional rollback).
"""
from __future__ import annotations
from typing import Iterable, List, Tuple, Dict
import pandas as pd

from services.core.portfolio_service import apply_buy, apply_sell
from services.trading import append_trade_log  # reuse existing trade log persistence
from config import TODAY


def _coerce_portfolio(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["ticker","shares","buy_price","cost_basis","stop_loss"])
    cols = set(df.columns)
    needed = {"ticker","shares","buy_price","cost_basis","stop_loss"}
    for c in needed - cols:
        if c == "ticker":
            df[c] = ""
        else:
            df[c] = 0.0
    df["ticker"] = df["ticker"].astype(str).str.upper()
    return df


def execute_orders(
    portfolio_df: pd.DataFrame,
    cash: float,
    orders: Iterable[dict],
    price_map: dict[str, float] | None = None,
    slippage_bps: float = 0.0,
    commit: bool = True,
    proportional_scale: bool = True,
    enable_partial: bool = True,
    log_trades: bool = True,
) -> Tuple[pd.DataFrame, float, pd.DataFrame]:
    """Execute orders sequentially with optional proportional scaling & dry-run.

    Enhancements:
      - proportional_scale: if aggregate BUY notional exceeds cash, scale all BUY share sizes.
      - enable_partial: allow partial fill of individual SELL if insufficient shares (instead of reject).
      - commit=False performs dry run (returns hypothetical results, no trade log writes).
      - log_trades: append trade log rows for filled orders when commit.
    """
    pf = _coerce_portfolio(portfolio_df.copy())
    rep_rows: List[Dict] = []
    price_map = price_map or {}
    slip = float(slippage_bps) / 10000.0 if slippage_bps else 0.0
    # Pre-scan buys for proportional scaling
    buy_rows: List[dict] = []
    total_buy_cost = 0.0
    prepared_orders: List[dict] = []
    for order in orders:
        o = dict(order)
        t = str(o.get("ticker", "")).upper()
        side = str(o.get("side", "")).upper()
        shares = float(o.get("shares", 0))
        est_price = float(o.get("est_price", 0))
        live_price = float(price_map.get(t, est_price) or est_price)
        if live_price <= 0 or shares <= 0:
            rep_rows.append({"ticker": t, "side": side, "shares": shares, "status": "skipped", "reason": "invalid_price_or_shares"})
            continue
        exec_price = live_price * (1 + slip if side == "BUY" else 1 - slip)
        o.update({"ticker": t, "side": side, "shares": shares, "exec_price": exec_price, "live_price": live_price})
        prepared_orders.append(o)
        if side == "BUY":
            total_buy_cost += exec_price * shares
            buy_rows.append(o)
    scale_factor = 1.0
    if proportional_scale and total_buy_cost > cash and total_buy_cost > 0:
        scale_factor = cash / total_buy_cost
    # Execute
    for o in prepared_orders:
        t = o["ticker"]; side = o["side"]; shares_req = o["shares"]
        exec_price = o["exec_price"]
        shares = shares_req
        if side == "BUY" and scale_factor < 1.0:
            shares = shares_req * scale_factor
            if shares < 1e-8:
                rep_rows.append({"ticker": t, "side": side, "shares": 0, "status": "skipped", "reason": "scaled_to_zero"})
                continue
        if side == "BUY":
            cost = exec_price * shares
            if cost > cash + 1e-9:
                # final guard (if not scaled or rounding issues) -> optional partial
                if enable_partial and exec_price > 0:
                    shares_partial = max(0.0, cash / exec_price)
                    if shares_partial < 1e-8:
                        rep_rows.append({"ticker": t, "side": side, "shares": 0, "status": "rejected", "reason": "insufficient_cash"})
                        continue
                    cost = exec_price * shares_partial
                    fill_type = "partial_filled"
                    shares = shares_partial
                else:
                    rep_rows.append({"ticker": t, "side": side, "shares": shares, "status": "rejected", "reason": "insufficient_cash"})
                    continue
            else:
                fill_type = "filled"
            if commit:
                pf = apply_buy(pf, t, shares, exec_price)
                cash -= cost
            slip_cost = (exec_price - live_price) * shares if side == "BUY" else (live_price - exec_price) * shares
            rep_rows.append({"ticker": t, "side": side, "shares": shares, "exec_price": exec_price, "status": fill_type, "notional": cost, "slippage_cost": slip_cost})
            if commit and log_trades:
                try:
                    append_trade_log({
                        "Date": TODAY,
                        "Ticker": t,
                        "Shares Bought": shares,
                        "Buy Price": exec_price,
                        "Cost Basis": cost,
                        "PnL": 0.0,
                        "Reason": "REBALANCE BUY",
                        "Shares Sold": "",
                        "Sell Price": "",
                    })
                except Exception:  # pragma: no cover
                    pass
        elif side == "SELL":
            pos_mask = pf["ticker"] == t
            if not pos_mask.any():
                rep_rows.append({"ticker": t, "side": side, "shares": shares, "status": "rejected", "reason": "no_position"})
                continue
            current_shares = float(pf.loc[pos_mask, "shares"].iloc[0])
            exec_shares = shares
            fill_type = "filled"
            if shares > current_shares + 1e-9:
                if enable_partial and current_shares > 0:
                    exec_shares = current_shares
                    fill_type = "partial_filled"
                else:
                    rep_rows.append({"ticker": t, "side": side, "shares": shares, "status": "rejected", "reason": "insufficient_shares"})
                    continue
            if commit:
                pf, _pnl = apply_sell(pf, t, exec_shares, exec_price)
                proceeds = exec_price * exec_shares
                cash += proceeds
            else:
                proceeds = exec_price * exec_shares
            slip_cost = (live_price - exec_price) * exec_shares if side == "SELL" else 0.0
            rep_rows.append({"ticker": t, "side": side, "shares": exec_shares, "exec_price": exec_price, "status": fill_type, "notional": proceeds, "slippage_cost": slip_cost})
            if commit and log_trades:
                try:
                    append_trade_log({
                        "Date": TODAY,
                        "Ticker": t,
                        "Shares Bought": "",
                        "Buy Price": "",
                        "Cost Basis": exec_price * exec_shares,  # cost basis reference
                        "PnL": 0.0,
                        "Reason": "REBALANCE SELL",
                        "Shares Sold": exec_shares,
                        "Sell Price": exec_price,
                    })
                except Exception:  # pragma: no cover
                    pass
        else:
            rep_rows.append({"ticker": t, "side": side, "shares": shares, "status": "skipped", "reason": "unknown_side"})
    report_df = pd.DataFrame(rep_rows)
    return (pf.reset_index(drop=True) if commit else portfolio_df.reset_index(drop=True)), float(cash if commit else cash), report_df

__all__ = ["execute_orders"]
