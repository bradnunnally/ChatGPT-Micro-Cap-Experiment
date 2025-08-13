from typing import Optional

from services.core.market_data_service import MarketDataService
from services.core.validation import validate_ticker


class MarketService:
    """Facade used in tests; delegates to MarketDataService with caching and resilience."""

    def __init__(self) -> None:
        self._svc = MarketDataService()

    def get_current_price(self, ticker: str) -> Optional[float]:
        try:
            return self._svc.get_price(ticker)
        except Exception:
            # Keep contract: return None on failure
            return None

    def validate_ticker(self, ticker: str) -> bool:
        try:
            validate_ticker(ticker)
            price = self.get_current_price(ticker)
            return price is not None
        except Exception:
            return False
