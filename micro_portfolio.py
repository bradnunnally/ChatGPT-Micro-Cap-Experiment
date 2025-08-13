from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


PORTFOLIO_FILE = Path("data/portfolio.json")


def load_portfolio() -> dict:
    if not PORTFOLIO_FILE.exists():
        return {"cash_balance": 0.0, "positions": []}
    try:
        return json.loads(PORTFOLIO_FILE.read_text())
    except Exception:
        return {"cash_balance": 0.0, "positions": []}


def save_portfolio(p: dict) -> None:
    PORTFOLIO_FILE.parent.mkdir(parents=True, exist_ok=True)
    PORTFOLIO_FILE.write_text(json.dumps(p, indent=2))


def add_position(ticker: str, shares: float, buy_price: float, stop_loss: Optional[float] = None) -> None:
    p = load_portfolio()
    pos = next((x for x in p["positions"] if x["ticker"].upper() == ticker.upper()), None)
    if pos:
        # merge: simple add shares at weighted price
        total_shares = float(pos["shares"]) + float(shares)
        if total_shares > 0:
            pos["buy_price"] = (float(pos["buy_price"]) * float(pos["shares"]) + float(buy_price) * float(shares)) / total_shares
        pos["shares"] = total_shares
        pos["stop_loss"] = stop_loss
    else:
        p["positions"].append({
            "ticker": ticker.upper(),
            "shares": float(shares),
            "buy_price": float(buy_price),
            "stop_loss": float(stop_loss) if stop_loss is not None else None,
        })
    save_portfolio(p)


def remove_position(ticker: str) -> None:
    p = load_portfolio()
    p["positions"] = [x for x in p["positions"] if x["ticker"].upper() != ticker.upper()]
    save_portfolio(p)


def update_stop_loss(ticker: str, stop_loss: Optional[float]) -> None:
    p = load_portfolio()
    for x in p["positions"]:
        if x["ticker"].upper() == ticker.upper():
            x["stop_loss"] = float(stop_loss) if stop_loss is not None else None
            break
    save_portfolio(p)


__all__ = [
    "PORTFOLIO_FILE",
    "load_portfolio",
    "save_portfolio",
    "add_position",
    "remove_position",
    "update_stop_loss",
]
