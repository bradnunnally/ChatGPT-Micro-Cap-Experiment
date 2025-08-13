import json
from datetime import datetime, UTC

from data.db import get_connection, init_db


class NoopAgent:
    name = "NoopAgent"
    description = "Agent that logs a heartbeat event."

    def heartbeat(self):
        init_db()
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO events (timestamp, agent, event_type, payload)
                VALUES (?, ?, ?, ?)
                """,
                (
                    datetime.now(UTC).isoformat(),
                    self.name,
                    "heartbeat",
                    json.dumps({"msg": "noop heartbeat"}),
                ),
            )
