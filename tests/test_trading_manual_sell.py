import pandas as pd
import streamlit as st
from unittest.mock import patch
from services.trading import manual_sell


@patch("data.portfolio.save_portfolio_snapshot")
def test_manual_sell_basic(mock_save):
    st.session_state.portfolio = pd.DataFrame({
        'ticker': ['XYZ'],
        'shares': [10],
        'stop_loss': [5.0],
        'buy_price': [10.0],
        'cost_basis': [100.0],
    })
    st.session_state.cash = 0.0
    result = manual_sell('XYZ', 4, 12.0)
    assert result is True
    assert st.session_state.cash == 48.0
    assert st.session_state.portfolio.iloc[0]['shares'] == 6


@patch("data.portfolio.save_portfolio_snapshot")
def test_manual_sell_all_shares(mock_save):
    st.session_state.portfolio = pd.DataFrame({
        'ticker': ['ABC'],
        'shares': [5],
        'stop_loss': [1.0],
        'buy_price': [2.0],
        'cost_basis': [10.0],
    })
    st.session_state.cash = 10.0
    result = manual_sell('ABC', 5, 3.0)
    assert result is True
    assert st.session_state.cash == 25.0
    assert st.session_state.portfolio.empty
