"""
Sector Analysis Service
Provides sector grouping and analysis for portfolio positions.
"""

import pandas as pd
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import json
from pathlib import Path

from infra.logging import get_logger
from services.core.market_service import MarketService

logger = get_logger(__name__)


class SectorService:
    """Service for sector classification and analysis."""
    
    def __init__(self):
        self.market_service = MarketService()
        self.cache_file = Path("data/sector_cache.json")
        self.cache_ttl_hours = 24
        self._sector_cache = self._load_cache()
    
    def _load_cache(self) -> Dict[str, Any]:
        """Load sector cache from file."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load sector cache: {e}")
        return {}
    
    def _save_cache(self):
        """Save sector cache to file."""
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, 'w') as f:
                json.dump(self._sector_cache, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save sector cache: {e}")
    
    def get_sector_for_symbol(self, symbol: str) -> str:
        """Get sector for a given stock symbol."""
        # Check cache first
        cached_data = self._sector_cache.get(symbol)
        if cached_data:
            cache_time = datetime.fromisoformat(cached_data.get("timestamp", "2000-01-01"))
            if datetime.now() - cache_time < timedelta(hours=self.cache_ttl_hours):
                return cached_data.get("sector", "Unknown")
        
        # Fetch from API - use Finnhub client directly
        try:
            from micro_config import get_config
            config = get_config()
            finnhub_client = config.data_provider
            
            # Get company profile
            profile = finnhub_client.get_company_profile(symbol)
            sector = profile.get("finnhubIndustry", "Unknown")
            
            # Cache the result
            self._sector_cache[symbol] = {
                "sector": sector,
                "timestamp": datetime.now().isoformat()
            }
            self._save_cache()
            
            return sector
        except Exception as e:
            logger.warning(f"Failed to fetch sector for {symbol}: {e}")
            return "Unknown"
    
    def group_positions_by_sector(self, positions_df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
        """Group positions DataFrame by sector."""
        if positions_df.empty:
            return {}
        
        # Add sector column
        positions_df = positions_df.copy()
        positions_df['Sector'] = positions_df['Ticker'].apply(self.get_sector_for_symbol)
        
        # Group by sector
        grouped = {}
        for sector in positions_df['Sector'].unique():
            sector_df = positions_df[positions_df['Sector'] == sector].copy()
            grouped[sector] = sector_df
        
        return grouped
    
    def calculate_sector_allocation(self, positions_df: pd.DataFrame) -> pd.DataFrame:
        """Calculate portfolio allocation by sector."""
        if positions_df.empty:
            return pd.DataFrame()
        
        # Add sectors
        positions_df = positions_df.copy()
        positions_df['Sector'] = positions_df['Ticker'].apply(self.get_sector_for_symbol)
        
        # Calculate total value per sector
        if 'Market Value' in positions_df.columns:
            value_column = 'Market Value'
        elif 'Position Value' in positions_df.columns:
            value_column = 'Position Value'
        else:
            logger.warning("No value column found for sector allocation")
            return pd.DataFrame()
        
        sector_totals = positions_df.groupby('Sector')[value_column].sum().reset_index()
        total_value = sector_totals[value_column].sum()
        
        if total_value > 0:
            sector_totals['Allocation %'] = (sector_totals[value_column] / total_value * 100).round(2)
        else:
            sector_totals['Allocation %'] = 0
        
        sector_totals = sector_totals.rename(columns={value_column: 'Total Value'})
        sector_totals = sector_totals.sort_values('Total Value', ascending=False)
        
        return sector_totals
    
    def get_sector_summary(self, positions_df: pd.DataFrame) -> Dict[str, Any]:
        """Get comprehensive sector summary statistics."""
        if positions_df.empty:
            return {
                "sector_count": 0,
                "top_sector": "N/A",
                "top_sector_pct": 0,
                "sector_diversity_score": 0
            }
        
        allocation = self.calculate_sector_allocation(positions_df)
        
        if allocation.empty:
            return {
                "sector_count": 0,
                "top_sector": "N/A",
                "top_sector_pct": 0,
                "sector_diversity_score": 0
            }
        
        # Calculate diversity score (lower is better, 100 = all in one sector)
        diversity_score = 100 - (allocation['Allocation %'].std() * 10 if len(allocation) > 1 else 0)
        diversity_score = max(0, min(100, diversity_score))
        
        return {
            "sector_count": len(allocation),
            "top_sector": allocation.iloc[0]['Sector'] if len(allocation) > 0 else "N/A",
            "top_sector_pct": allocation.iloc[0]['Allocation %'] if len(allocation) > 0 else 0,
            "sector_diversity_score": round(diversity_score, 1),
            "sector_allocation": allocation.to_dict('records')
        }
    
    def get_sector_performance(self, positions_df: pd.DataFrame) -> pd.DataFrame:
        """Calculate performance metrics by sector."""
        if positions_df.empty or 'Gain/Loss %' not in positions_df.columns:
            return pd.DataFrame()
        
        positions_df = positions_df.copy()
        positions_df['Sector'] = positions_df['Ticker'].apply(self.get_sector_for_symbol)
        
        # Calculate sector performance
        sector_perf = positions_df.groupby('Sector').agg({
            'Gain/Loss %': 'mean',
            'Ticker': 'count'
        }).reset_index()
        
        sector_perf = sector_perf.rename(columns={
            'Gain/Loss %': 'Avg Return %',
            'Ticker': 'Position Count'
        })
        
        sector_perf = sector_perf.sort_values('Avg Return %', ascending=False)
        
        return sector_perf


# Global sector service instance
sector_service = SectorService()