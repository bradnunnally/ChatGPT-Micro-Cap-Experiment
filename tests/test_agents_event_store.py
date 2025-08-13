import pytest
from agents.noop_agent import NoopAgent
from data.db import get_connection, init_db
import pandas as pd


def clear_events():
    with get_connection() as conn:
        conn.execute("DELETE FROM events")


def get_last_event():
    with get_connection() as conn:
        df = pd.read_sql_query("SELECT * FROM events ORDER BY id DESC LIMIT 1", conn)
    return df.iloc[0] if not df.empty else None


def test_noop_agent_heartbeat():
    init_db()
    clear_events()
    agent = NoopAgent()
    agent.heartbeat()
    event = get_last_event()
    assert event is not None
    assert event["agent"] == "NoopAgent"
    assert event["event_type"] == "heartbeat"
    assert "noop heartbeat" in event["payload"]
