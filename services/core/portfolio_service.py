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
            holdings_count=len(self._positions)
        )
    
    def to_dataframe(self) -> pd.DataFrame:
        if not self._positions:
            return pd.DataFrame(columns=['ticker', 'shares', 'price', 'cost_basis', 'stop_loss'])
            
        return pd.DataFrame([
            {
                'ticker': ticker,
                'shares': pos.shares,
                'price': pos.price,
                'cost_basis': pos.cost_basis,
                'stop_loss': pos.stop_loss
            }
            for ticker, pos in self._positions.items()
        ])