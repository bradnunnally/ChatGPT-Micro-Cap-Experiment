from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Protocol
import pandas as pd


@dataclass
class StrategyResult:
    equity_curve: pd.Series
    returns: pd.Series  # per-period strategy returns (aligned with equity_curve)
    trades: pd.DataFrame
    metrics: Dict[str, Any]
    params: Dict[str, Any]
    strategy_name: str


class Strategy(Protocol):
    name: str
    params: Dict[str, Any]

    def run(self, prices: pd.Series) -> StrategyResult: ...


def compute_basic_metrics(equity: pd.Series, strat_returns: pd.Series) -> Dict[str, float]:
    if equity.empty:
        return {"total_return_pct": 0.0, "max_drawdown_pct": 0.0, "sharpe_like": 0.0}
    total_return = (equity.iloc[-1] - 1) * 100
    mdd = ((equity / equity.cummax() - 1).min()) * 100
    sr = (strat_returns.mean() / strat_returns.std() * (252 ** 0.5)) if strat_returns.std() > 0 else 0.0
    return {
        "total_return_pct": float(total_return),
        "max_drawdown_pct": float(mdd),
        "sharpe_like": float(sr),
    }


def train_test_split_series(series: pd.Series, split: float = 0.7) -> tuple[pd.Series, pd.Series]:
    if series.empty:
        return series, series
    idx = int(len(series) * split)
    if idx <= 0 or idx >= len(series):
        return series, series.iloc[0:0]
    return series.iloc[:idx], series.iloc[idx:]


def evaluate_train_test(result: StrategyResult, split: float = 0.7) -> Dict[str, Dict[str, float]]:
    """Compute metrics for train and test segments of the strategy returns.

    Returns dict: {"train": metrics, "test": metrics}
    """
    train_ret, test_ret = train_test_split_series(result.returns, split)
    out: Dict[str, Dict[str, float]] = {}
    def _equity(rets: pd.Series) -> pd.Series:
        return (1 + rets).cumprod()
    if not train_ret.empty:
        out["train"] = compute_basic_metrics(_equity(train_ret), train_ret)
    else:
        out["train"] = {"total_return_pct": 0.0, "max_drawdown_pct": 0.0, "sharpe_like": 0.0}
    if not test_ret.empty:
        out["test"] = compute_basic_metrics(_equity(test_ret), test_ret)
    else:
        out["test"] = {"total_return_pct": 0.0, "max_drawdown_pct": 0.0, "sharpe_like": 0.0}
    return out
