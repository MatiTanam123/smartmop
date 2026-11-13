"""Common database-side activity logger."""
from __future__ import annotations


def log_activity(
    conn,
    event_type: str,
    message: str,
    severity: str = "info",
    detection_id: int | None = None,
    session_id: int | None = None,
) -> None:
    conn.execute(
        """INSERT INTO activity_logs
           (event_type, severity, message, detection_id, session_id)
           VALUES (%s, %s, %s, %s, %s)""",
        (event_type, severity, message, detection_id, session_id),
    )
