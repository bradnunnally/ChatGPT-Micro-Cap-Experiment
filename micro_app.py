from __future__ import annotations

import argparse
from datetime import date, timedelta

import pandas as pd

from micro_config import get_provider, print_mode, resolve_env
from micro_portfolio import load_portfolio, save_portfolio, add_position, remove_position, update_stop_loss, PORTFOLIO_FILE


def _seed_dev_defaults(env: str) -> None:
    if env == "dev_stage" and not PORTFOLIO_FILE.exists():
        save_portfolio(
            {
                "cash_balance": 100.0,
                "positions": [
                    {"ticker": "AAA", "shares": 10, "buy_price": 5.0, "stop_loss": None},
                    {"ticker": "BBB", "shares": 20, "buy_price": 2.5, "stop_loss": None},
                ],
            }
        )


def _adv_20(provider, ticker: str) -> tuple[float | None, float | None]:
    end = date.today()
    start = end - timedelta(days=60)
    df = provider.get_daily_candles(ticker, start, end)
    if df.empty:
        return (None, None)
    last20 = df.tail(20)
    adv = float(last20["volume"].mean()) if not last20["volume"].empty else None
    dv = None
    if adv is not None and "close" in last20.columns:
        dv = float((last20["close"] * last20["volume"]).mean())
    return adv, dv


def _catalyst(provider, ticker: str) -> str:
    end = date.today()
    start = end - timedelta(days=14)
    news = provider.get_company_news(ticker, start, end) or []
    headline = news[0]["headline"] if news else None
    cal = provider.get_earnings_calendar(ticker, end, end + timedelta(days=120)) or []
    next_earn = None
    for item in cal:
        dt = item.get("date") or item.get("earningsDate")
        if dt:
            next_earn = dt
            break
    parts = []
    if headline:
        parts.append(headline)
    if next_earn:
        parts.append(f"Earnings: {next_earn}")
    return " | ".join(parts) if parts else ""


def cmd_show(env: str) -> None:
    provider = get_provider(env)
    print_mode(provider)
    _seed_dev_defaults(env)
    p = load_portfolio()
    positions = p.get("positions", [])
    cash = float(p.get("cash_balance", 0.0))
    rows = []
    for pos in positions:
        t = pos["ticker"].upper()
        shares = float(pos["shares"])
        buy = float(pos["buy_price"])
        stop = pos.get("stop_loss")
        q = provider.get_quote(t)
        price = q.get("price") or 0.0
        current_value = shares * float(price)
        pnl = (float(price) - buy) * shares
        pct = ((float(price) - buy) / buy * 100.0) if buy else 0.0
        prof = provider.get_company_profile(t)
        adv, dv = _adv_20(provider, t)
        bid, ask = provider.get_bid_ask(t)
        spread = (ask - bid) if (bid is not None and ask is not None) else None
        catalyst = _catalyst(provider, t)
        rows.append(
            {
                "Ticker": t,
                "Shares Owned": shares,
                "Buy Price": buy,
                "Stop Loss": stop,
                "Current Price": price,
                "Current Value": current_value,
                "PnL": pnl,
                "Action": "Hold",
                "Pct Change": pct,
                "Exchange": prof.get("exchange"),
                "Sector": prof.get("sector"),
                "Mkt Cap": prof.get("marketCap"),
                "20d ADV": adv,
                "Spread": spread if spread is not None else "N/A",
                "Catalyst": catalyst,
            }
        )

    df = pd.DataFrame(rows)
    invested_val = float(df["Current Value"].sum()) if not df.empty else 0.0
    total_equity = cash + invested_val
    unrealized = float(df["PnL"].sum()) if not df.empty else 0.0
    avg_pct = float(df["Pct Change"].mean()) if not df.empty else 0.0
    cost_basis = float((df["Buy Price"] * df["Shares Owned"]).sum()) if not df.empty else 0.0
    roi = ((invested_val - cost_basis) / cost_basis * 100.0) if cost_basis else 0.0
    winners = int((df["PnL"] > 0).sum()) if not df.empty else 0
    losers = int((df["PnL"] <= 0).sum()) if not df.empty else 0
    below_stop = int(((df["Current Price"] < df["Stop Loss"]) & df["Stop Loss"].notna()).sum()) if not df.empty else 0
    largest_pos = float((df["Current Value"] / total_equity * 100.0).max()) if total_equity and not df.empty else 0.0
    micro_cap_noncompliant = int((df["Mkt Cap"].fillna(float("inf")) >= 300_000_000).sum()) if not df.empty else 0

    print("\nPortfolio Table:\n")
    if not df.empty:
        print(df.to_string(index=False))
    else:
        print("(no positions)")

    print("\nDaily Portfolio Summary:")
    print(f"  Total Equity: {total_equity:.2f}  | Invested: {invested_val:.2f}  | Cash: {cash:.2f} ({(cash/total_equity*100.0 if total_equity else 0.0):.1f}%)")
    print(f"  Positions: {len(positions)}  | Unrealized PnL: {unrealized:.2f}  | Avg % Chg: {avg_pct:.2f}%  | ROI: {roi:.2f}%")
    print(f"  Winners: {winners}  | Losers: {losers}  | Below Stop: {below_stop}  | Largest Position: {largest_pos:.2f}%")
    print(f"  Micro-cap non-compliant (>= $300M): {micro_cap_noncompliant}")

    # Watchlist section (ticker, price, change%)
    print("\nWatchlist:")
    wrows = []
    for pos in positions:
        t = pos["ticker"].upper()
        q = provider.get_quote(t)
        wrows.append({
            "Ticker": t,
            "Price": q.get("price"),
            "Change %": q.get("percent"),
        })
    wdf = pd.DataFrame(wrows)
    if not wdf.empty:
        print(wdf.to_string(index=False))
    else:
        print("(empty)")


def main():
    parser = argparse.ArgumentParser(description="Micro trading CLI app")
    parser.add_argument("command", choices=["add", "remove", "show"], help="Command to run")
    parser.add_argument("ticker", nargs="?", help="Ticker symbol")
    parser.add_argument("shares", nargs="?", type=float, help="Shares to add")
    parser.add_argument("buy_price", nargs="?", type=float, help="Buy price")
    parser.add_argument("--stop", dest="stop", type=float, default=None, help="Optional stop loss")
    parser.add_argument("--env", dest="env", choices=["dev_stage", "production"], default=None)
    args = parser.parse_args()

    env = resolve_env(args.env)
    if args.command == "add":
        if not args.ticker or args.shares is None or args.buy_price is None:
            raise SystemExit("Usage: micro_app.py add TICKER SHARES BUYPRICE [--stop STOP]")
        add_position(args.ticker, args.shares, args.buy_price, args.stop)
        cmd_show(env)
    elif args.command == "remove":
        if not args.ticker:
            raise SystemExit("Usage: micro_app.py remove TICKER")
        remove_position(args.ticker)
        cmd_show(env)
    else:
        cmd_show(env)


if __name__ == "__main__":
    main()
