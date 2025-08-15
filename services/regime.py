"""Simple regime detection utilities.

Scope: Provide a basic market regime label using available benchmark and factor
return series (already accessible in app). If required data unavailable, return
"unknown" and keep feature inert.

Current heuristic (expandable):
  1. Use benchmark (e.g., SPY) daily returns last N days (default 60).
  2. Compute realized volatility (std) and average return.
  3. Classify:
       - bull: avg_ret > +0.05% and vol < 1.5 * long_run_vol
       - bear: avg_ret < -0.05% and cumulative drawdown > 5%
       - high_vol: volatility > 2 * long_run_vol
       - sideways: |avg_ret| <= 0.05%
     Precedence order: high_vol -> bear -> bull -> sideways.
  4. Provide dictionary with regime label + metrics for UI / strategy context.

Fallback: If < MIN_OBS observations, label = "unknown".
"""
from __future__ import annotations
import pandas as pd
from services.benchmark import get_benchmark_series, BENCHMARK_SYMBOL_DEFAULT
from services.market import get_daily_price_series

MIN_OBS = 20


def _returns_from_prices(prices: pd.Series) -> pd.Series:
    return prices.pct_change(fill_method=None).dropna()


def detect_regime(lookback: int = 60, benchmark: str = BENCHMARK_SYMBOL_DEFAULT) -> dict:
    try:
        bench = get_benchmark_series(benchmark)
        if bench is None or bench.empty:
            # attempt fallback from daily price series table
            df = get_daily_price_series(benchmark, limit=lookback+5)
            if df.empty or 'close' not in df.columns:
                return {"label": "unknown"}
            s = df.set_index('date')['close'].astype(float)
        else:
            s = bench.tail(lookback+5).astype(float)
        rets = _returns_from_prices(s).tail(lookback)
        if rets.shape[0] < MIN_OBS:
            return {"label": "unknown"}
        avg_ret = rets.mean() * 100  # percent
        vol = rets.std() * 100       # percent
        cum = (1 + rets).prod() - 1
        peak = s.expanding().max()
        dd = (s/peak - 1).min() * 100  # percent drawdown (negative)
        long_run_vol = rets.rolling(min(lookback, 120)).std().mean() * 100 if rets.shape[0] >= 30 else vol
        label = "sideways"
        if vol > 2 * long_run_vol:
            label = "high_vol"
        elif avg_ret < -0.05 and dd < -5:
            label = "bear"
        elif avg_ret > 0.05 and vol < 1.5 * long_run_vol:
            label = "bull"
        else:
            label = "sideways"
        return {
            "label": label,
            "avg_ret_pct": float(avg_ret),
            "vol_pct": float(vol),
            "drawdown_pct": float(dd),
            "lookback": lookback,
            "obs": int(rets.shape[0]),
        }
    except Exception:
        return {"label": "unknown"}

__all__ = ["detect_regime"]
