import sys

import pandas as pd

from data.db import get_connection


def show_events(limit=10):
    with get_connection() as conn:
        df = pd.read_sql_query(f"SELECT * FROM events ORDER BY id DESC LIMIT {limit}", conn)
    print(df)


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    show_events(n)
