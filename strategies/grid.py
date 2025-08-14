from __future__ import annotations

from itertools import product
from typing import Iterable, List, Dict, Any
import pandas as pd

from .sma import SMACrossStrategy
from .base import StrategyResult, evaluate_train_test


def run_sma_grid(prices: pd.Series, fast_values: Iterable[int], slow_values: Iterable[int], slippage_bps: float = 0.0, commission_bps: float = 0.0) -> List[StrategyResult]:
    results: List[StrategyResult] = []
    for f, s in product(fast_values, slow_values):
        if f >= s:  # enforce fast < slow for meaningful crossover
            continue
    strat = SMACrossStrategy(fast=f, slow=s, slippage_bps=slippage_bps, commission_bps=commission_bps)
    res = strat.run(prices)
    results.append(res)
    return results


def summarize_results(results: List[StrategyResult]) -> pd.DataFrame:
    rows = []
    for r in results:
        tt = evaluate_train_test(r, split=0.7)
        row = {
            "strategy": r.strategy_name,
            **r.params,
            **{f"train_{k}": v for k, v in tt["train"].items()},
            **{f"test_{k}": v for k, v in tt["test"].items()},
            **r.metrics,
        }
        rows.append(row)
    if not rows:
        return pd.DataFrame(columns=["strategy", "fast", "slow", "total_return_pct", "max_drawdown_pct", "sharpe_like"])
    df = pd.DataFrame(rows)
    # Prefer test Sharpe for ranking if available; fallback to overall
    rank_cols = [c for c in ["test_sharpe_like", "sharpe_like", "test_total_return_pct", "total_return_pct"] if c in df.columns]
    df["rank"] = df.sort_values(rank_cols, ascending=[False] * len(rank_cols)).reset_index(drop=True).index + 1
    return df.sort_values("rank")
