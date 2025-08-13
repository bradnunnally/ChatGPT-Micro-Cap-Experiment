import pytest

# Entire legacy fallback test module skipped after yfinance removal.
pytestmark = pytest.mark.skip(reason="Legacy yfinance fallback paths removed; tests deprecated.")
