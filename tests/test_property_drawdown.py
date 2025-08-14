import pandas as pd
from hypothesis import given, strategies as st
from services.risk import compute_drawdown, max_drawdown

# Property-based tests for drawdown metrics
# Properties:
# 1. Drawdown values are always <= 0
# 2. First drawdown value is 0
# 3. Max drawdown (most negative) >= min(series) relative decline logic is consistent
# 4. Monotonic increasing equity has max_drawdown == 0
# 5. If equity dips then recovers, max_drawdown captures worst interim drop

@given(st.lists(st.floats(min_value=0.01, max_value=1e6, allow_nan=False, allow_infinity=False), min_size=1, max_size=200))
def test_drawdown_non_positive(values):
    s = pd.Series(values)
    dd = compute_drawdown(s)
    assert (dd <= 0).all()
    assert dd.iloc[0] == 0

@given(st.lists(st.floats(min_value=1.0, max_value=1e6, allow_nan=False, allow_infinity=False), min_size=2, max_size=200))
def test_monotonic_increasing_has_zero_max_drawdown(values):
    # Make strictly increasing
    inc = [values[0] + i * 1 for i in range(len(values))]
    s = pd.Series(inc)
    assert max_drawdown(s) == 0.0

@given(st.lists(st.floats(min_value=10.0, max_value=1e6, allow_nan=False, allow_infinity=False), min_size=3, max_size=200))
def test_drawdown_bounds(values):
    s = pd.Series(values)
    dd = compute_drawdown(s)
    # Drawdown never less than -100%
    assert dd.min() >= -100.0


def test_known_pattern():
    # Equity: 100 -> 80 (-20%) -> 60 (-40%) -> 90 (-10% from peak) -> 120 (new peak)
    s = pd.Series([100, 80, 60, 90, 120])
    assert max_drawdown(s) == -40.0
