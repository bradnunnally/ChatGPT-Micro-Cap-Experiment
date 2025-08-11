from dataclasses import dataclass
from typing import Optional

from services.core.market_service import MarketService
from services.core.portfolio_service import PortfolioService, Position


@dataclass
class TradeResult:
    success: bool
    message: str
    position: Optional[Position] = None


class TradingService:
    def __init__(self, portfolio_service: PortfolioService, market_service: MarketService):
        self.portfolio = portfolio_service
        self.market = market_service
        self.cash_balance = 10000.0  # Default starting cash

    def buy_stock(self, ticker: str, shares: int, price: Optional[float] = None) -> TradeResult:
        """Execute a buy order."""
        if price is None:
            price = self.market.get_current_price(ticker)
            if price is None:
                return TradeResult(False, f"Could not get price for {ticker}")

        total_cost = shares * price

        if total_cost > self.cash_balance:
            return TradeResult(False, "Insufficient funds")

        position = Position(ticker=ticker, shares=shares, price=price, cost_basis=total_cost)

        self.portfolio.add_position(position)
        self.cash_balance -= total_cost

        return TradeResult(True, f"Bought {shares} shares of {ticker}", position)

    def sell_stock(self, ticker: str, shares: int, price: Optional[float] = None) -> TradeResult:
        """Execute a sell order."""
        if price is None:
            price = self.market.get_current_price(ticker)
            if price is None:
                return TradeResult(False, f"Could not get price for {ticker}")

        # Check if position exists
        df = self.portfolio.to_dataframe()
        if df.empty or ticker not in df["ticker"].values:
            return TradeResult(False, f"No position found for {ticker}")

        current_shares = df[df["ticker"] == ticker]["shares"].iloc[0]
        if shares > current_shares:
            return TradeResult(False, f"Cannot sell {shares} shares, only have {current_shares}")

        # Execute sale
        proceeds = shares * price
        self.cash_balance += proceeds

        # Remove or update position
        if shares == current_shares:
            self.portfolio.remove_position(ticker)
        else:
            # Update position (simplified for now)
            pass

        return TradeResult(True, f"Sold {shares} shares of {ticker}")

    def get_cash_balance(self) -> float:
        return self.cash_balance

    def add_cash(self, amount: float) -> None:
        self.cash_balance += amount
