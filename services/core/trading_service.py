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
        if shares <= 0:
            return TradeResult(False, "Share count must be positive")

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
        if shares <= 0:
            return TradeResult(False, "Share count must be positive")

        if price is None:
            price = self.market.get_current_price(ticker)
            if price is None:
                return TradeResult(False, f"Could not get price for {ticker}")

        # Check if position exists
        df = self.portfolio.to_dataframe()
        if df.empty or ticker not in df["ticker"].values:
            return TradeResult(False, f"No position found for {ticker}")

        position_row = df[df["ticker"] == ticker].iloc[0]
        current_shares = int(position_row["shares"])

        row_price_value = position_row.get("price", price)
        if row_price_value is None or row_price_value != row_price_value:
            row_price = float(price)
        else:
            row_price = float(row_price_value)

        cost_basis_default = current_shares * row_price
        row_cost_basis_value = position_row.get("cost_basis", cost_basis_default)
        if row_cost_basis_value is None or row_cost_basis_value != row_cost_basis_value:
            row_cost_basis = float(cost_basis_default)
        else:
            row_cost_basis = float(row_cost_basis_value)

        if shares > current_shares:
            return TradeResult(False, f"Cannot sell {shares} shares, only have {current_shares}")

        # Execute sale
        proceeds = shares * price
        self.cash_balance += proceeds

        # Remove or update position
        if shares == current_shares:
            self.portfolio.remove_position(ticker)
        else:
            avg_cost_per_share = row_cost_basis / current_shares if current_shares else 0
            remaining_shares = current_shares - shares
            remaining_cost_basis = max(0.0, float(avg_cost_per_share * remaining_shares))

            stop_loss = None
            if "stop_loss" in df.columns:
                stop_loss_value = position_row.get("stop_loss")
                if (
                    stop_loss_value is not None
                    and stop_loss_value == stop_loss_value
                ):  # NaN check without numpy dependency
                    stop_loss = float(stop_loss_value)

            updated_position = Position(
                ticker=ticker,
                shares=int(remaining_shares),
                price=row_price,
                cost_basis=float(remaining_cost_basis),
                stop_loss=stop_loss,
            )

            self.portfolio.remove_position(ticker)
            self.portfolio.add_position(updated_position)

        return TradeResult(True, f"Sold {shares} shares of {ticker}")

    def get_cash_balance(self) -> float:
        return self.cash_balance

    def add_cash(self, amount: float) -> None:
        self.cash_balance += amount
