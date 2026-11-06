"""Shared database helpers."""
from __future__ import annotations
from datetime import datetime
from typing import Any
from psycopg.types.json import Jsonb


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


def device_id_by_code(conn, device_code: str) -> int | None:
    row = conn.execute(
        "SELECT device_id FROM devices WHERE device_code = %s AND is_enabled = TRUE",
        (device_code,),
    ).fetchone()
    return int(row["device_id"]) if row else None


def create_command(
    conn,
    command_type: str,
    payload: dict[str, Any] | None = None,
    *,
    device_code: str = "ESP32_MAIN_01",
    session_id: int | None = None,
) -> int:
    device_id = device_id_by_code(conn, device_code)
    if device_id is None:
        raise LookupError(f"Perangkat {device_code} tidak ditemukan atau nonaktif.")
    row = conn.execute(
        """INSERT INTO robot_commands
           (device_id, session_id, command_type, command_payload)
           VALUES (%s, %s, %s, %s)
           RETURNING command_id""",
        (device_id, session_id, command_type, Jsonb(payload or {})),
    ).fetchone()
    return int(row["command_id"])


def to_iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None
