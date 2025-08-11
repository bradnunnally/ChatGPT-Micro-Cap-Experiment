from dataclasses import dataclass

import pandas as pd


@dataclass
class PortfolioMetrics:
    total_value: float
    total_gain: float
    total_return: float
    holdings_count: int


class PortfolioManager:
    def __init__(self):
        self._portfolio = pd.DataFrame()

    def add_position(self, ticker: str, shares: int, price: float) -> None:
        """Add a new position to portfolio."""
        new_position = pd.DataFrame(
            {
                "ticker": [ticker],
                "shares": [shares],
                "price": [price],
                "cost_basis": [shares * price],
            }
        )
        self._portfolio = pd.concat([self._portfolio, new_position], ignore_index=True)

    def get_portfolio_metrics(self) -> PortfolioMetrics:
        """Calculate portfolio metrics without UI dependencies."""
        if self._portfolio.empty:
            return PortfolioMetrics(0, 0, 0, 0)

        total_value = (self._portfolio["shares"] * self._portfolio["price"]).sum()
        cost_basis = self._portfolio["cost_basis"].sum()
        total_gain = total_value - cost_basis
        total_return = (total_gain / cost_basis) if cost_basis > 0 else 0

        return PortfolioMetrics(
            total_value=total_value,
            total_gain=total_gain,
            total_return=total_return,
            holdings_count=len(self._portfolio),
        )
