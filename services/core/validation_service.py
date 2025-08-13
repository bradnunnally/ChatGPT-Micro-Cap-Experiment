from typing import Optional, Tuple


class ValidationService:
    @staticmethod
    def validate_ticker(ticker: str) -> Tuple[bool, Optional[str]]:
        """Validate ticker symbol format."""
        if not ticker:
            return False, "Ticker symbol cannot be empty"

        if len(ticker) > 5:
            return False, "Ticker symbol too long"

        if not ticker.isalpha():
            return False, "Ticker symbol must contain only letters"

        return True, None

    @staticmethod
    def validate_shares(shares: int) -> Tuple[bool, Optional[str]]:
        """Validate share quantity."""
        if shares <= 0:
            return False, "Share quantity must be positive"

        if shares > 1000000:
            return False, "Share quantity too large"

        return True, None

    @staticmethod
    def validate_price(price: float) -> Tuple[bool, Optional[str]]:
        """Validate stock price."""
        if price <= 0:
            return False, "Price must be positive"

        if price > 10000:
            return False, "Price seems unrealistic"

        return True, None
