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
try:  # Turnover budget is optional; degrade gracefully if module missing
    from services.turnover_budget import record_trade_notional, evaluate_turnover  # type: ignore
except Exception:  # pragma: no cover
    def record_trade_notional(*_a, **_k):  # type: ignore
        return None
    def evaluate_turnover(*_a, **_k):  # type: ignore
        return {"will_block": False}

def _coerce_portfolio(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure the portfolio frame has required columns with default values."""
    base_cols_defaults = {
        "ticker": "",
        "shares": 0.0,
        "buy_price": 0.0,
        "cost_basis": 0.0,
        "stop_loss": 0.0,
    }
    for c, d in base_cols_defaults.items():
        if c not in df.columns:
            df[c] = d
    # Normalize ticker casing
    if not df.empty:
        df["ticker"] = df["ticker"].astype(str).str.upper()
    return df.reset_index(drop=True)


def _equity_snapshot(pf: pd.DataFrame, cash: float) -> float:
    return float(cash + float((pf["shares"] * pf["buy_price"]).sum()))


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
    enforce_turnover_budget: bool = True,
) -> Tuple[pd.DataFrame, float, pd.DataFrame]:
    """Execute a batch of orders against a portfolio.

    Features:
      - Optional proportional scaling of BUY side to available cash
      - Optional partial fills for insufficient cash / shares
      - Slippage (bps) applied symmetrically (buy up, sell down)
      - Turnover budget pre-block for BUY; post-trade ledger recording BUY & SELL
    """
    pf = _coerce_portfolio(portfolio_df.copy())
    rep_rows: List[Dict] = []
    price_map = price_map or {}
    slip = float(slippage_bps) / 10000.0 if slippage_bps else 0.0

    # Pre-pass for proportional scaling of BUY orders
    total_buy_cost = 0.0
    prepared: List[dict] = []
    for od in orders:
        o = dict(od)
        t = str(o.get("ticker", "")).upper()
        side = str(o.get("side", "")).upper()
        shares = float(o.get("shares", 0) or 0)
        est_price = float(o.get("est_price", 0) or 0)
        live_price = float(price_map.get(t, est_price) or est_price)
        if shares <= 0 or live_price <= 0:
            rep_rows.append({"ticker": t, "side": side, "shares": shares, "status": "skipped", "reason": "invalid_price_or_shares"})
            continue
        exec_price = live_price * (1 + slip if side == "BUY" else 1 - slip)
        o.update({"ticker": t, "side": side, "shares": shares, "exec_price": exec_price, "live_price": live_price})
        prepared.append(o)
        if side == "BUY":
            total_buy_cost += exec_price * shares

    scale_factor = 1.0
    if proportional_scale and total_buy_cost > cash and total_buy_cost > 0:
        scale_factor = cash / total_buy_cost

    # Execution loop
    for o in prepared:
        t = o["ticker"]
        side = o["side"]
        req_shares = o["shares"]
        exec_price = o["exec_price"]
        live_price = o["live_price"]

        shares = req_shares
        if side == "BUY" and scale_factor < 1.0:
            shares = req_shares * scale_factor
            if shares < 1e-8:
                rep_rows.append({"ticker": t, "side": side, "shares": 0, "status": "skipped", "reason": "scaled_to_zero"})
                continue

        if side == "BUY":
            cost = exec_price * shares
            # Cash check & partial
            if cost > cash + 1e-9:
                if enable_partial and exec_price > 0:
                    shares_partial = max(0.0, cash / exec_price)
                    if shares_partial < 1e-8:
                        rep_rows.append({"ticker": t, "side": side, "shares": 0, "status": "rejected", "reason": "insufficient_cash"})
                        continue
                    shares = shares_partial
                    cost = exec_price * shares
                    fill_type = "partial_filled"
                else:
                    rep_rows.append({"ticker": t, "side": side, "shares": shares, "status": "rejected", "reason": "insufficient_cash"})
                    continue
            else:
                fill_type = "filled"

            # Turnover pre-block
            if commit and enforce_turnover_budget:
                try:
                    equity_snap = _equity_snapshot(pf, cash)
                    eval_res = evaluate_turnover(cost, equity_snap)
                    if eval_res.get("will_block"):
                        rep_rows.append({"ticker": t, "side": side, "shares": shares, "status": "blocked_turnover", "reason": "turnover_budget_exceeded"})
                        continue
                except Exception:  # pragma: no cover
                    pass

            if commit:
                pf = apply_buy(pf, t, shares, exec_price)
                cash -= cost

            slip_cost = (exec_price - live_price) * shares
            rep_rows.append({
                "ticker": t,
                "side": side,
                "shares": shares,
                "exec_price": exec_price,
                "status": fill_type,
                "notional": cost,
                "slippage_cost": slip_cost,
            })

            if commit and log_trades:
                try:  # pragma: no cover - log failures ignored
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

            if commit and enforce_turnover_budget:
                try:
                    equity_snap = _equity_snapshot(pf, cash)
                    record_trade_notional(t, side, cost, equity_snap)
                except Exception:  # pragma: no cover
                    pass

        elif side == "SELL":
            mask = pf["ticker"] == t
            if not mask.any():
                rep_rows.append({"ticker": t, "side": side, "shares": shares, "status": "rejected", "reason": "no_position"})
                continue
            cur_shares = float(pf.loc[mask, "shares"].iloc[0])
            exec_shares = shares
            fill_type = "filled"
            if shares > cur_shares + 1e-9:
                if enable_partial and cur_shares > 0:
                    exec_shares = cur_shares
                    fill_type = "partial_filled"
                else:
                    rep_rows.append({"ticker": t, "side": side, "shares": shares, "status": "rejected", "reason": "insufficient_shares"})
                    continue

            proceeds = exec_price * exec_shares
            if commit:
                pf, _pnl = apply_sell(pf, t, exec_shares, exec_price)
                cash += proceeds

            slip_cost = (live_price - exec_price) * exec_shares if exec_shares > 0 else 0.0
            rep_rows.append({
                "ticker": t,
                "side": side,
                "shares": exec_shares,
                "exec_price": exec_price,
                "status": fill_type,
                "notional": proceeds,
                "slippage_cost": slip_cost,
            })

            if commit and log_trades:
                try:  # pragma: no cover
                    append_trade_log({
                        "Date": TODAY,
                        "Ticker": t,
                        "Shares Bought": "",
                        "Buy Price": "",
                        "Cost Basis": proceeds,  # using proceeds for symmetry; can refine
                        "PnL": 0.0,
                        "Reason": "REBALANCE SELL",
                        "Shares Sold": exec_shares,
                        "Sell Price": exec_price,
                    })
                except Exception:  # pragma: no cover
                    pass

            if commit and enforce_turnover_budget:
                try:
                    equity_snap = _equity_snapshot(pf, cash)
                    record_trade_notional(t, side, proceeds, equity_snap)
                except Exception:  # pragma: no cover
                    pass

        else:
            rep_rows.append({"ticker": t, "side": side, "shares": shares, "status": "skipped", "reason": "unknown_side"})

    report_df = pd.DataFrame(rep_rows)
    updated_pf = pf.reset_index(drop=True) if commit else portfolio_df.reset_index(drop=True)
    return updated_pf, float(cash), report_df
