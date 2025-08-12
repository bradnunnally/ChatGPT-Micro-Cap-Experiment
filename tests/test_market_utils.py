import math
import pandas as pd
import services.market as market


def test_market_helpers_basic():
    assert market.is_valid_price(10.5) is True
    assert market.is_valid_price(-1) is False
    assert market.calculate_percentage_change(100, 110) == 10.0
    assert market.calculate_percentage_change(0, 110) == 0.0
    assert market.validate_price_data(5.0) is True
    assert market.validate_price_data(-3) is False


def test_validate_ticker_format():
    assert market.validate_ticker_format('AAPL') is True
    assert market.validate_ticker_format('aapl') is False
    assert market.validate_ticker_format('1234') is False
    assert market.validate_ticker_format('') is False
    assert market.validate_ticker_format('BRK.B') is True


def test_sanitize_market_data_impute_branch():
    # Construct DataFrame where one valid row and one row with missing price but valid volume triggers imputation branch
    df = pd.DataFrame({
        'ticker': ['AAA', 'BBB'],
        'price': [10.0, None],
        'volume': [1000, 2000],
    })
    cleaned = market.sanitize_market_data(df)
    assert len(cleaned) == 2
    assert set(cleaned['ticker']) == {'AAA', 'BBB'}
    # Ensure the imputed price of 1.0 exists for BBB
    bbb_row = cleaned[cleaned['ticker'] == 'BBB'].iloc[0]
    assert math.isclose(float(bbb_row['price']), 1.0, rel_tol=1e-6)
