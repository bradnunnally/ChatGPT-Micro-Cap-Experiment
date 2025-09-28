"""
Configuration for portfolio summary functionality.

This module centralizes all configuration values that were previously
scattered as magic numbers throughout the codebase.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class SummaryConfig:
    """Configuration for portfolio summary generation and analysis."""
    
    # Historical data parameters
    default_history_months: int = 6
    min_observations_for_metrics: int = 10
    trading_days_per_year: int = 252
    
    # Caching configuration
    price_cache_ttl_minutes: int = 5
    
    # Market data configuration
    benchmark_symbol: str = "^GSPC"
    
    # Display configuration
    currency_precision: int = 2
    percentage_precision: int = 2
    
    # Risk analysis parameters
    risk_free_rate: float = 0.02  # 2% annual risk-free rate
    confidence_level: float = 0.95  # 95% confidence for VaR calculations
    
    # Portfolio analysis thresholds
    min_position_size_for_display: float = 0.01  # Minimum 1% to show in allocations
    max_holdings_display: int = 20  # Maximum holdings to display in tables
    
    # Data validation
    max_price_change_threshold: float = 0.5  # 50% single-day change threshold for outlier detection
    min_trading_volume: int = 1000  # Minimum daily volume for liquidity checks


# Global default configuration instance
DEFAULT_CONFIG = SummaryConfig()


def get_config() -> SummaryConfig:
    """
    Get the current configuration instance.
    
    Returns:
        Current SummaryConfig instance
    """
    return DEFAULT_CONFIG


def set_config(config: SummaryConfig) -> None:
    """
    Set a new configuration instance (primarily for testing).
    
    Args:
        config: New configuration to use
    """
    global DEFAULT_CONFIG
    DEFAULT_CONFIG = config


def create_test_config(**overrides) -> SummaryConfig:
    """
    Create a configuration instance with specific overrides for testing.
    
    Args:
        **overrides: Configuration values to override
        
    Returns:
        New SummaryConfig instance with overrides applied
        
    Example:
        test_config = create_test_config(
            price_cache_ttl_minutes=1, 
            min_observations_for_metrics=5
        )
    """
    config_defaults = {
        'default_history_months': 6,
        'min_observations_for_metrics': 10,
        'trading_days_per_year': 252,
        'price_cache_ttl_minutes': 5,
        'benchmark_symbol': '^GSPC',
        'currency_precision': 2,
        'percentage_precision': 2,
        'risk_free_rate': 0.02,
        'confidence_level': 0.95,
        'min_position_size_for_display': 0.01,
        'max_holdings_display': 20,
        'max_price_change_threshold': 0.5,
        'min_trading_volume': 1000,
    }
    
    # Apply overrides
    config_defaults.update(overrides)
    
    return SummaryConfig(**config_defaults)