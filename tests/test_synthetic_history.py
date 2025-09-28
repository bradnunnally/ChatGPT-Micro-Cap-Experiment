"""Tests for synthetic portfolio history generation and hybrid risk calculations."""

import pandas as pd
import pytest

from ui.summary import (
    get_portfolio_history_for_analytics,
    _build_portfolio_history_from_market,
    _compute_risk_metrics_with_source_info,
    _history_has_valid_equity,
)


@pytest.fixture(autouse=True)
def stub_market_service(monkeypatch):
    """Mock the market service to return predictable data."""
    
    def _stub_fetch_history(symbol, months=3):
        # Generate predictable price history based on symbol
        dates = pd.date_range(end="2025-09-27", periods=60, freq="D")  # 60 days of data
        
        if symbol == "AAPL":
            # Simulate Apple stock with some volatility
            base_price = 150.0
            prices = [base_price + (i * 0.5) + ((i % 7) * 2.0) for i in range(60)]
        elif symbol == "MSFT":
            # Simulate Microsoft stock
            base_price = 300.0 
            prices = [base_price + (i * 0.3) + ((i % 5) * 1.5) for i in range(60)]
        else:
            # Default generic stock
            base_price = 50.0
            prices = [base_price + (i * 0.1) for i in range(60)]
            
        return pd.DataFrame({
            "date": dates,
            "close": prices,
            "volume": [1_000_000 + (i * 10_000) for i in range(60)]
        })
    
    monkeypatch.setattr("ui.summary.MARKET_SERVICE.fetch_history", _stub_fetch_history)


def test_history_has_valid_equity():
    """Test the helper function for checking valid equity data."""
    
    # Empty DataFrame should return False
    assert not _history_has_valid_equity(pd.DataFrame())
    
    # DataFrame without TOTAL rows should return False
    df_no_total = pd.DataFrame({
        "ticker": ["AAPL", "MSFT"],
        "total_equity": [1000, 2000],
        "date": ["2025-01-01", "2025-01-02"]
    })
    assert not _history_has_valid_equity(df_no_total)
    
    # DataFrame with TOTAL but no valid equity should return False
    df_invalid_equity = pd.DataFrame({
        "ticker": ["TOTAL", "TOTAL"], 
        "total_equity": [None, pd.NA],
        "date": ["2025-01-01", "2025-01-02"]
    })
    assert not _history_has_valid_equity(df_invalid_equity)
    
    # DataFrame with only one TOTAL row should return False (needs at least 2)
    df_single_total = pd.DataFrame({
        "ticker": ["AAPL", "TOTAL", "MSFT"],
        "total_equity": [1000, 5000, 2000],
        "date": ["2025-01-01", "2025-01-02", "2025-01-03"]
    })
    assert not _history_has_valid_equity(df_single_total)
    
    # DataFrame with 2+ valid TOTAL equity rows should return True
    df_valid = pd.DataFrame({
        "ticker": ["AAPL", "TOTAL", "MSFT", "TOTAL"],
        "total_equity": [1000, 5000, 2000, 5100],
        "date": ["2025-01-01", "2025-01-02", "2025-01-03", "2025-01-04"]
    })
    assert _history_has_valid_equity(df_valid)


def test_build_portfolio_history_from_market():
    """Test synthetic portfolio history generation from market data."""
    
    # Test with empty holdings
    empty_df = pd.DataFrame()
    result = _build_portfolio_history_from_market(empty_df, 1000.0)
    assert result.empty
    
    # Test with valid holdings
    holdings_df = pd.DataFrame([
        {"ticker": "AAPL", "shares": 10},
        {"ticker": "MSFT", "shares": 5},
    ])
    
    result = _build_portfolio_history_from_market(holdings_df, 1000.0, months=2)
    
    # Should have generated history
    assert not result.empty
    assert "date" in result.columns
    assert "ticker" in result.columns
    assert "total_equity" in result.columns
    
    # All rows should be TOTAL ticker
    assert all(result["ticker"] == "TOTAL")
    
    # Should have reasonable equity values (positions + cash)
    assert all(result["total_equity"] > 1000.0)  # At least the cash balance
    
    # Check that equity includes both positions and cash
    # AAPL: 10 shares * ~150-180 = 1500-1800
    # MSFT: 5 shares * ~300-320 = 1500-1600  
    # Cash: 1000
    # Total should be around 4000-4400
    min_expected = 3500  # Conservative lower bound
    max_expected = 5000  # Conservative upper bound
    assert all(result["total_equity"] >= min_expected)
    assert all(result["total_equity"] <= max_expected)


def test_get_portfolio_history_for_analytics_with_existing_data():
    """Test hybrid approach when good existing data is available."""
    
    # Create mock existing history with sufficient data
    existing_history = pd.DataFrame({
        "date": pd.date_range("2025-08-01", periods=20, freq="D"),
        "ticker": ["TOTAL"] * 20,
        "total_equity": [5000 + (i * 10) for i in range(20)]
    })
    
    holdings_df = pd.DataFrame([{"ticker": "AAPL", "shares": 10}])
    
    result_history, is_synthetic = get_portfolio_history_for_analytics(
        holdings_df, existing_history, 1000.0
    )
    
    # Should use existing data
    assert not is_synthetic
    assert len(result_history) == 20
    assert all(result_history["ticker"] == "TOTAL")


def test_get_portfolio_history_for_analytics_fallback_to_synthetic():
    """Test hybrid approach when falling back to synthetic data."""
    
    # Create insufficient existing history (too few data points)
    insufficient_history = pd.DataFrame({
        "date": pd.date_range("2025-09-25", periods=5, freq="D"),
        "ticker": ["TOTAL"] * 5,
        "total_equity": [5000, 5100, 5050, 5200, 5150]
    })
    
    holdings_df = pd.DataFrame([
        {"ticker": "AAPL", "shares": 10},
        {"ticker": "MSFT", "shares": 5}
    ])
    
    result_history, is_synthetic = get_portfolio_history_for_analytics(
        holdings_df, insufficient_history, 1000.0
    )
    
    # Should fall back to synthetic
    assert is_synthetic
    assert not result_history.empty
    assert len(result_history) > 10  # Should have generated substantial history


def test_compute_risk_metrics_with_synthetic_flag():
    """Test risk metrics calculation with synthetic data flagging."""
    
    # Create synthetic portfolio history
    dates = pd.date_range("2025-08-01", periods=30, freq="D")
    # Simulate portfolio with some volatility and trend
    equity_values = [5000 + (i * 20) + ((i % 7) * 50) for i in range(30)]
    
    history = pd.DataFrame({
        "date": dates,
        "ticker": ["TOTAL"] * 30,
        "total_equity": equity_values
    })
    
    # Test with synthetic flag
    metrics_synthetic = _compute_risk_metrics_with_source_info(
        history, is_synthetic=True, benchmark_symbol="^GSPC"
    )
    
    # Should have calculated metrics
    assert metrics_synthetic["max_drawdown"] is not None
    assert metrics_synthetic["sharpe_annual"] is not None
    assert metrics_synthetic["beta"] is not None
    assert metrics_synthetic["is_synthetic"] is True
    
    # Note should indicate synthetic data
    assert "synthetic history" in metrics_synthetic["note"]
    
    # Test with real data flag  
    metrics_real = _compute_risk_metrics_with_source_info(
        history, is_synthetic=False, benchmark_symbol="^GSPC"
    )
    
    assert metrics_real["is_synthetic"] is False
    assert "synthetic history" not in metrics_real["note"]


def test_comprehensive_synthetic_workflow():
    """Test the complete workflow from holdings to risk metrics."""
    
    # Create a realistic portfolio
    holdings_df = pd.DataFrame([
        {"ticker": "AAPL", "shares": 20},
        {"ticker": "MSFT", "shares": 10},
    ])
    
    # No existing history (new portfolio)
    no_history = pd.DataFrame()
    cash_balance = 2000.0
    
    # Get history using hybrid approach
    history, is_synthetic = get_portfolio_history_for_analytics(
        holdings_df, no_history, cash_balance
    )
    
    # Should have generated synthetic history
    assert is_synthetic
    assert not history.empty
    assert len(history) > 20  # Reasonable amount of synthetic data
    
    # Calculate risk metrics
    risk_metrics = _compute_risk_metrics_with_source_info(
        history, is_synthetic=is_synthetic, benchmark_symbol="^GSPC"
    )
    
    # Should have meaningful metrics
    assert risk_metrics["max_drawdown"] is not None
    assert risk_metrics["sharpe_annual"] is not None
    assert risk_metrics["sortino_annual"] is not None
    assert risk_metrics["beta"] is not None
    assert risk_metrics["alpha_annual"] is not None
    assert risk_metrics["r_squared"] is not None
    assert risk_metrics["obs"] > 0
    
    # Should be flagged as synthetic
    assert risk_metrics["is_synthetic"] is True
    assert "synthetic history" in risk_metrics["note"]
    
    print(f"Generated {len(history)} synthetic data points")
    print(f"Risk metrics: Sharpe={risk_metrics['sharpe_annual']:.3f}, Beta={risk_metrics['beta']:.3f}")
    print(f"Note: {risk_metrics['note']}")