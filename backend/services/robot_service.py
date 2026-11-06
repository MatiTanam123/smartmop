"""Robot command queue and cleaning-session operations."""
from __future__ import annotations
from psycopg.types.json import Jsonb
from .common import create_command, device_id_by_code, log_activity

ACTIVE_STATUSES = ("pending", "approaching", "mopping", "verifying")


def current_mode(conn) -> str:
    row = conn.execute("SELECT operation_mode FROM robot_settings WHERE setting_id = 1").fetchone()
    return row["operation_mode"] if row else "automatic"


def set_mode(conn, mode: str) -> dict:
    normalized = str(mode).strip().lower()
    mapping = {"otomatis": "automatic", "automatic": "automatic", "manual": "manual"}
    if normalized not in mapping:
        raise ValueError("Mode harus Otomatis atau Manual.")
    mode_db = mapping[normalized]
    conn.execute(
        """INSERT INTO robot_settings (setting_id, operation_mode)
           VALUES (1, %s)
           ON CONFLICT (setting_id) DO UPDATE SET
             operation_mode = EXCLUDED.operation_mode,
             updated_at = CURRENT_TIMESTAMP""",
        (mode_db,),
    )
    command_id = create_command(conn, "set_mode", {"mode": mode_db})
    log_activity(conn, "mode_changed", f"Mode robot diubah menjadi {'Otomatis' if mode_db == 'automatic' else 'Manual'}.")
    return {"mode": mode_db, "command_id": command_id}


def move_robot(conn, direction: str) -> dict:
    allowed = {"maju", "mundur", "kiri", "kanan", "berhenti"}
    direction = str(direction).strip().lower()
    if direction not in allowed:
        raise ValueError("Arah gerak tidak valid.")
    if current_mode(conn) != "manual":
        raise PermissionError("Gerakan manual hanya dapat digunakan dalam mode Manual.")
    command_id = create_command(conn, "move", {"direction": direction})
    log_activity(conn, "robot_move", f"Perintah gerak manual: {direction}.")
    return {"command_id": command_id, "direction": direction, "command_status": "queued"}


def start_cleaning(conn, action: str) -> dict:
    action = str(action).strip().lower()
    controller_id = device_id_by_code(conn, "ESP32_MAIN_01")
    if action == "start":
        active = conn.execute(
            """SELECT session_id FROM cleaning_sessions
               WHERE session_status IN ('pending','approaching','mopping','verifying')
               ORDER BY created_at DESC LIMIT 1"""
        ).fetchone()
        if active:
            return {"session_id": int(active["session_id"]), "message": "Sesi pembersihan sudah berjalan."}
        settings = conn.execute(
            """SELECT mop_duration_seconds, cleaning_repeats, soap_volume_preset,
                      movement_speed, camera_interval_seconds
               FROM robot_settings WHERE setting_id = 1"""
        ).fetchone() or {
            "mop_duration_seconds": 10, "cleaning_repeats": 2,
            "soap_volume_preset": "medium", "movement_speed": "slow",
            "camera_interval_seconds": 3,
        }
        mode = current_mode(conn)
        # Use the latest accepted spill as the parent detection when available.
        detection = conn.execute(
            """SELECT detection_id FROM detections
               WHERE decision_status = 'accepted'
                 AND detected_at >= CURRENT_TIMESTAMP - INTERVAL '30 minutes'
                 AND (lower(class_name) LIKE '%spill%' OR lower(class_name) LIKE '%syrup%'
                      OR lower(class_name) LIKE '%sirup%' OR lower(class_name) LIKE '%tumpahan%')
                 AND lower(class_name) NOT LIKE '%no_spill%'
                 AND lower(class_name) NOT LIKE '%no spill%'
                 AND lower(class_name) NOT LIKE '%clean%'
                 AND lower(class_name) NOT LIKE '%tidak ada%'
               ORDER BY detected_at DESC LIMIT 1"""
        ).fetchone()
        row = conn.execute(
            """INSERT INTO cleaning_sessions
               (detection_id, controller_device_id, operation_mode, session_status,
                started_at, mop_duration_seconds, cleaning_attempts)
               VALUES (%s, %s, %s, 'pending', CURRENT_TIMESTAMP, %s, 0)
               RETURNING session_id""",
            (detection["detection_id"] if detection else None, controller_id, mode,
             settings["mop_duration_seconds"]),
        ).fetchone()
        session_id = int(row["session_id"])
        command_id = create_command(
            conn, "clean_start",
            {
                "action": "start",
                "duration_seconds": int(settings["mop_duration_seconds"]),
                "cleaning_repeats": int(settings["cleaning_repeats"]),
                "soap_volume_preset": settings["soap_volume_preset"],
                "movement_speed": settings["movement_speed"],
            },
            session_id=session_id,
        )
        log_activity(conn, "cleaning_started", "Perintah mulai mengepel dikirim ke robot.", session_id=session_id)
        return {"session_id": session_id, "command_id": command_id, "session_status": "pending"}

    if action == "stop":
        active = conn.execute(
            """SELECT session_id FROM cleaning_sessions
               WHERE session_status IN ('pending','approaching','mopping','verifying')
               ORDER BY created_at DESC LIMIT 1"""
        ).fetchone()
        session_id = int(active["session_id"]) if active else None
        if session_id:
            conn.execute(
                """UPDATE cleaning_sessions SET session_status = 'cancelled',
                   completed_at = CURRENT_TIMESTAMP, notes = COALESCE(notes, '') || ' Dihentikan dari dashboard.'
                   WHERE session_id = %s""", (session_id,)
            )
        command_id = create_command(conn, "clean_stop", {"action": "stop"}, session_id=session_id)
        log_activity(conn, "cleaning_stopped", "Proses pengepelan dihentikan dari dashboard.", severity="warning", session_id=session_id)
        return {"session_id": session_id, "command_id": command_id, "session_status": "cancelled"}

    raise ValueError("action harus start atau stop.")


def set_actuator(conn, actuator: str, on: bool) -> dict:
    if actuator not in {"pump", "mop_motor"}:
        raise ValueError("Aktuator tidak dikenali.")
    command_id = create_command(conn, f"{actuator}_set", {"on": bool(on)})
    label = "Pompa sabun" if actuator == "pump" else "Motor pel"
    log_activity(conn, "actuator_changed", f"{label} {'dinyalakan' if on else 'dimatikan'}.")
    return {"command_id": command_id, "actuator": actuator, "on": bool(on)}


def emergency_stop(conn) -> dict:
    # Emergency stop is queued to the controller; for safety it must also be implemented
    # as a physical hardware cutoff on the robot, not only as a software command.
    active = conn.execute(
        """SELECT session_id FROM cleaning_sessions
           WHERE session_status IN ('pending','approaching','mopping','verifying')"""
    ).fetchall()
    for row in active:
        conn.execute(
            """UPDATE cleaning_sessions SET session_status = 'cancelled',
               completed_at = CURRENT_TIMESTAMP,
               notes = COALESCE(notes, '') || ' Emergency stop.'
               WHERE session_id = %s""", (row["session_id"],)
        )
    command_id = create_command(conn, "emergency_stop", {"stop_all": True})
    log_activity(conn, "emergency_stop", "Henti darurat diminta melalui dashboard.", severity="error")
    return {"command_id": command_id, "cancelled_sessions": len(active), "command_status": "queued"}


def camera_quality(conn, quality: str) -> dict:
    q = str(quality).strip().upper()
    if q not in {"HD", "SD"}:
        raise ValueError("Kualitas kamera harus HD atau SD.")
    command_id = create_command(
        conn, "camera_quality", {"quality": q}, device_code="ESP32_CAM_01"
    )
    log_activity(conn, "camera_quality", f"Permintaan kualitas kamera diubah menjadi {q}.")
    return {"command_id": command_id, "quality": q}


def poll_commands(conn, device_code: str, limit: int = 5) -> list[dict]:
    device_id = device_id_by_code(conn, device_code)
    if not device_id:
        raise LookupError(f"Perangkat {device_code} tidak terdaftar.")
    limit = max(1, min(int(limit), 20))
    rows = conn.execute(
        """SELECT command_id, session_id, command_type, command_payload, created_at
           FROM robot_commands
           WHERE device_id = %s AND command_status = 'queued'
           ORDER BY created_at ASC
           LIMIT %s FOR UPDATE SKIP LOCKED""",
        (device_id, limit),
    ).fetchall()
    ids = [r["command_id"] for r in rows]
    if ids:
        conn.execute(
            """UPDATE robot_commands SET command_status = 'sent', sent_at = CURRENT_TIMESTAMP
               WHERE command_id = ANY(%s)""", (ids,)
        )
    return [
        {
            "command_id": int(r["command_id"]),
            "session_id": int(r["session_id"]) if r["session_id"] is not None else None,
            "command_type": r["command_type"],
            "payload": r["command_payload"],
            "created_at": r["created_at"].isoformat(),
        }
        for r in rows
    ]


def acknowledge_command(conn, command_id: int, payload: dict) -> dict:
    status = str(payload.get("status", "acknowledged")).lower()
    if status not in {"acknowledged", "failed"}:
        raise ValueError("status harus acknowledged atau failed.")
    row = conn.execute(
        """UPDATE robot_commands
           SET command_status = %s,
               response_payload = %s,
               acknowledged_at = CURRENT_TIMESTAMP
           WHERE command_id = %s AND command_status IN ('queued','sent')
           RETURNING command_id, command_type, session_id""",
        (status, Jsonb(payload.get("response", {})), command_id),
    ).fetchone()
    if not row:
        raise LookupError("Perintah tidak ditemukan atau sudah diproses.")
    session_id = row["session_id"]
    if session_id:
        if row["command_type"] in {"clean_start", "approach_spill"} and status == "acknowledged":
            conn.execute(
                """UPDATE cleaning_sessions SET session_status =
                     CASE WHEN %s = 'approach_spill' THEN 'approaching' ELSE 'mopping' END,
                     started_at = COALESCE(started_at, CURRENT_TIMESTAMP)
                   WHERE session_id = %s AND session_status NOT IN ('completed','failed','cancelled')""",
                (row["command_type"], session_id),
            )
        elif row["command_type"] in {"clean_stop", "emergency_stop"}:
            conn.execute(
                """UPDATE cleaning_sessions SET session_status = 'cancelled',
                   completed_at = CURRENT_TIMESTAMP WHERE session_id = %s""", (session_id,)
            )
    return {"command_id": int(row["command_id"]), "command_status": status}
