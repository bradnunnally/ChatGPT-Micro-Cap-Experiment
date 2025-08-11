from data.db import get_connection
import pandas as pd

with get_connection() as conn:
    df = pd.read_sql_query('SELECT * FROM events ORDER BY id DESC LIMIT 1', conn)
    print(df.to_dict())
