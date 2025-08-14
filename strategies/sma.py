from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Any
import pandas as pd
from .base import StrategyResult, compute_basic_metrics, Strategy


@dataclass
class SMACrossStrategy:
    fast: int = 5
    slow: int = 20
    slippage_bps: float = 0.0  # per side applied on position change
    commission_bps: float = 0.0  # additional per trade cost
    name: str = field(init=False, default="sma_cross")

    @property
    def params(self) -> Dict[str, Any]:
        return {
            "fast": self.fast,
            "slow": self.slow,
            "slippage_bps": self.slippage_bps,
            "commission_bps": self.commission_bps,
        }

    def run(self, prices: pd.Series) -> StrategyResult:
        df = pd.DataFrame({"price": prices})
        df[f"fast_{self.fast}"] = df["price"].rolling(self.fast).mean()
        df[f"slow_{self.slow}"] = df["price"].rolling(self.slow).mean()
        df["signal"] = 0
        df.loc[df[f"fast_{self.fast}"] > df[f"slow_{self.slow}"], "signal"] = 1
        df.loc[df[f"fast_{self.fast}"] < df[f"slow_{self.slow}"], "signal"] = -1
        df["position"] = df["signal"].shift().fillna(0).clip(-1, 1)
        returns = df["price"].pct_change().fillna(0)
        gross_ret = returns * df["position"]
        # Transaction costs: apply on absolute position change (switching costs)
        delta_pos = df["position"].diff().abs().fillna(df["position"].abs())
        cost_rate = (self.slippage_bps + self.commission_bps) / 10000.0
        cost_ret = delta_pos * cost_rate
        strat_ret = gross_ret - cost_ret
        equity = (1 + strat_ret).cumprod()
        metrics = compute_basic_metrics(equity, strat_ret)
        metrics["transaction_cost_bps_total"] = float(cost_ret.sum() * 10000.0)
        metrics["gross_total_return_pct"] = float(((1 + gross_ret).cumprod().iloc[-1] - 1) * 100) if len(gross_ret) else 0.0
        # Gross Sharpe (before costs) for comparison
        gross_sharpe = (gross_ret.mean() / gross_ret.std() * (252 ** 0.5)) if gross_ret.std() > 0 else 0.0
        metrics["gross_sharpe_like"] = float(gross_sharpe)
        # Keep existing sharpe_like as NET (already in compute_basic_metrics)
        trades = df[df["signal"] != 0]
        if not trades.empty:
            trades = trades.copy()
            trades["gross_ret"] = gross_ret.loc[trades.index]
            trades["net_ret"] = strat_ret.loc[trades.index]
            trades["transaction_cost_bps"] = (cost_ret.loc[trades.index] * 10000.0).astype(float)
        return StrategyResult(
            equity_curve=equity,
            returns=strat_ret,
            trades=trades,
            metrics=metrics,
            params=self.params,
            strategy_name=self.name,
        )
