from typing import List

import pandas as pd

# ---------------------------------------------------------------------------
# Portfolio schema and helpers
# ---------------------------------------------------------------------------

PORTFOLIO_COLUMNS: List[str] = [
    "ticker",
    "shares",
    "stop_loss",
    "buy_price",
    "cost_basis",
]


def ensure_schema(df: pd.DataFrame) -> pd.DataFrame:
    """Return ``df`` with all expected portfolio columns present."""

    for col in PORTFOLIO_COLUMNS:
        if col not in df.columns:
            df[col] = 0.0 if col != "ticker" else ""
    return df[PORTFOLIO_COLUMNS].copy()
