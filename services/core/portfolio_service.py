from dataclasses import dataclass
from typing import Dict, Optional

import pandas as pd


@dataclass
class PortfolioMetrics:
    total_value: float
    total_gain: float
    total_return: float
    holdings_count: int


@dataclass
class Position:
    ticker: str
    shares: int
    price: float
    cost_basis: float
    stop_loss: Optional[float] = None


class PortfolioService:
    def __init__(self):
        self._positions: Dict[str, Position] = {}

    def add_position(self, position: Position) -> None:
        self._positions[position.ticker] = position

    def remove_position(self, ticker: str) -> None:
        self._positions.pop(ticker, None)

    def get_metrics(self) -> PortfolioMetrics:
        if not self._positions:
            return PortfolioMetrics(0, 0, 0, 0)

        total_value = sum(p.shares * p.price for p in self._positions.values())
        total_cost = sum(p.cost_basis for p in self._positions.values())
        total_gain = total_value - total_cost
        total_return = (total_gain / total_cost) if total_cost > 0 else 0

        return PortfolioMetrics(
            total_value=total_value,
            total_gain=total_gain,
            total_return=total_return,
            holdings_count=len(self._positions),
        )

    def to_dataframe(self) -> pd.DataFrame:
        if not self._positions:
            return pd.DataFrame(columns=["ticker", "shares", "price", "cost_basis", "stop_loss"])

        return pd.DataFrame(
            [
                {
                    "ticker": ticker,
                    "shares": pos.shares,
                    "price": pos.price,
                    "cost_basis": pos.cost_basis,
                    "stop_loss": pos.stop_loss,
                }
                for ticker, pos in self._positions.items()
            ]
        )


# ----------------------
# Pure portfolio functions
# ----------------------


def calculate_position_value(shares: float, current_price: float) -> float:
    return float(shares) * float(current_price)


def calculate_pnl(buy_price: float, current_price: float, shares: float) -> float:
    return (float(current_price) - float(buy_price)) * float(shares)


def apply_buy(
    portfolio_df: pd.DataFrame,
    ticker: str,
    shares: float,
    price: float,
    stop_loss: Optional[float] = None,
) -> pd.DataFrame:
    """Return a new DataFrame with a buy applied; no side effects.

    Expected columns when present: ticker, shares, stop_loss, buy_price, cost_basis
    Missing columns will be created with sensible defaults.
    """
    df = portfolio_df.copy()
    # Ensure core columns
    for col, default in [
        ("ticker", ""),
        ("shares", 0.0),
        ("stop_loss", 0.0 if stop_loss is None else float(stop_loss)),
        ("buy_price", 0.0),
        ("cost_basis", 0.0),
    ]:
        if col not in df.columns:
            df[col] = default

    t = str(ticker).strip().upper()
    add_cost = float(price) * float(shares)
    mask = df["ticker"].str.upper() == t
    if not mask.any():
        df = pd.concat(
            [
                df,
                pd.DataFrame(
                    [
                        {
                            "ticker": t,
                            "shares": float(shares),
                            "stop_loss": float(stop_loss) if stop_loss is not None else 0.0,
                            "buy_price": float(price),
                            "cost_basis": add_cost,
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )
    else:
        idx = df[mask].index[0]
        current_shares = float(df.at[idx, "shares"]) if pd.notna(df.at[idx, "shares"]) else 0.0
        current_cost = (
            float(df.at[idx, "cost_basis"]) if pd.notna(df.at[idx, "cost_basis"]) else 0.0
        )
        new_shares = current_shares + float(shares)
        new_cost = current_cost + add_cost
        df.at[idx, "shares"] = new_shares
        df.at[idx, "cost_basis"] = new_cost
        # Weighted average buy price
        df.at[idx, "buy_price"] = (new_cost / new_shares) if new_shares > 0 else float(price)
        if stop_loss is not None:
            df.at[idx, "stop_loss"] = float(stop_loss)

    return df


def apply_sell(
    portfolio_df: pd.DataFrame,
    ticker: str,
    shares: float,
    price: float,
) -> tuple[pd.DataFrame, float]:
    """Return (updated_df, pnl) for a sell; no side effects.

    Uses constant average cost method: reduces cost_basis by buy_price * shares_sold.
    Removes the row if shares go to zero.
    """
    df = portfolio_df.copy()
    for col in ["ticker", "shares", "buy_price", "cost_basis"]:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    t = str(ticker).strip().upper()
    mask = df["ticker"].str.upper() == t
    if not mask.any():
        raise ValueError("Ticker not in portfolio")

    idx = df[mask].index[0]
    total_shares = float(df.at[idx, "shares"]) if pd.notna(df.at[idx, "shares"]) else 0.0
    if float(shares) > total_shares:
        raise ValueError("Insufficient shares")

    buy_price = float(df.at[idx, "buy_price"]) if pd.notna(df.at[idx, "buy_price"]) else 0.0
    proceeds = float(price) * float(shares)
    cost_out = buy_price * float(shares)
    pnl = proceeds - cost_out

    remaining = total_shares - float(shares)
    if remaining <= 0:
        df = df[~mask]
    else:
        df.at[idx, "shares"] = remaining
        new_cost_basis = max(0.0, float(df.at[idx, "cost_basis"]) - cost_out)
        df.at[idx, "cost_basis"] = new_cost_basis
        # buy_price remains the same average cost

    return df.reset_index(drop=True), pnl


def compute_snapshot(
    portfolio_df: pd.DataFrame,
    prices: dict[str, float],
    cash: float,
    date: str,
) -> pd.DataFrame:
    """Return a snapshot DataFrame with per-position and TOTAL rows.

    No I/O. Expects portfolio_df with columns: ticker, shares, buy_price, stop_loss.
    """
    df = portfolio_df.copy()
    # Ensure columns
    for c in ["ticker", "shares", "buy_price", "stop_loss"]:
        if c not in df.columns:
            df[c] = 0.0 if c != "ticker" else ""

    rows: list[dict] = []
    total_value = 0.0
    total_pnl = 0.0

    for _, r in df.iterrows():
        t = str(r["ticker"]).strip().upper()
        sh = float(r["shares"]) if pd.notna(r["shares"]) else 0.0
        stop = float(r["stop_loss"]) if pd.notna(r["stop_loss"]) else 0.0
        buy = float(r["buy_price"]) if pd.notna(r["buy_price"]) else 0.0
        cur = float(prices.get(t, 0.0) or 0.0)
        value = round(cur * sh, 2)
        pnl = round((cur - buy) * sh, 2)
        total_value += value
        total_pnl += pnl

        rows.append(
            {
                "Date": date,
                "Ticker": t,
                "Shares": sh,
                "Cost Basis": buy,
                "Stop Loss": stop,
                "Current Price": cur,
                "Total Value": value,
                "PnL": pnl,
                "Action": "HOLD",
                "Cash Balance": "",
                "Total Equity": "",
            }
        )

    rows.append(
        {
            "Date": date,
            "Ticker": "TOTAL",
            "Shares": "",
            "Cost Basis": "",
            "Stop Loss": "",
            "Current Price": "",
            "Total Value": round(total_value, 2),
            "PnL": round(total_pnl, 2),
            "Action": "",
            "Cash Balance": round(float(cash), 2),
            "Total Equity": round(total_value + float(cash), 2),
        }
    )

    out = pd.DataFrame(rows)
    return out
