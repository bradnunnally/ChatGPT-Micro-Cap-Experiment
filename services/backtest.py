from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Callable
import pandas as pd

@dataclass
class BacktestResult:
    equity_curve: pd.Series
    trades: pd.DataFrame
    metrics: dict


def simple_moving_average_strategy(prices: pd.Series, fast: int = 5, slow: int = 20):
    df = pd.DataFrame({"price": prices})
    df[f"fast_{fast}"] = df["price"].rolling(fast).mean()
    df[f"slow_{slow}"] = df["price"].rolling(slow).mean()
    df["signal"] = 0
    df.loc[df[f"fast_{fast}"] > df[f"slow_{slow}"] , "signal"] = 1
    df.loc[df[f"fast_{fast}"] < df[f"slow_{slow}"] , "signal"] = -1
    df["position"] = df["signal"].shift().fillna(0).clip(-1,1)
    returns = df["price"].pct_change().fillna(0)
    strat_ret = returns * df["position"]
    equity = (1 + strat_ret).cumprod()
    return BacktestResult(equity_curve=equity, trades=df[df["signal"] != 0], metrics={
        "total_return_pct": (equity.iloc[-1] - 1) * 100 if len(equity) else 0.0,
        "max_drawdown_pct": ((equity / equity.cummax() - 1).min()) * 100 if len(equity) else 0.0,
        "sharpe_like": (strat_ret.mean() / strat_ret.std() * (252 ** 0.5)) if strat_ret.std() > 0 else 0.0
    })


def run_backtest(prices: pd.Series, strategy: Callable[[pd.Series], BacktestResult] = simple_moving_average_strategy) -> BacktestResult:
    return strategy(prices)
