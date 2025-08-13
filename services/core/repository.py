"""Repository protocol for portfolio persistence.

Decouples core logic from storage so we can swap implementations and
version the schema safely.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import pandas as pd


@dataclass(frozen=True)
class LoadResult:
    portfolio: pd.DataFrame
    cash: float
    is_first_time: bool


class PortfolioRepository(Protocol):
    def load(self) -> LoadResult:  # pragma: no cover - exercised via existing tests
        """Load current portfolio and cash balance."""

    def load_cash(self) -> float:  # pragma: no cover
        """Return the current cash balance."""

    def save_snapshot(
        self, portfolio_df: pd.DataFrame, cash: float
    ) -> pd.DataFrame:  # pragma: no cover
        """Persist holdings, cash, and a daily snapshot; returns snapshot DataFrame."""

    def append_trade_log(self, log: dict) -> None:  # pragma: no cover
        """Append an entry to the trade log."""
