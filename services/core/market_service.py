from typing import Optional

import yfinance as yf

from services.logging import get_logger
logger = get_logger(__name__)


class MarketService:
    def get_current_price(self, ticker: str) -> Optional[float]:
        try:
            data = yf.download(
                ticker,
                period="1d",
                progress=False,
                auto_adjust=True
            )
            
            if data.empty:
                return None
                
            return float(data["Close"].iloc[0])
            
        except Exception as e:
            logger.error(f"Error getting price for {ticker}: {e}")
            return None
    
    def validate_ticker(self, ticker: str) -> bool:
        return self.get_current_price(ticker) is not None