from flask import Blueprint

from database.connection import get_db_connection
from routes.helpers import json_body, error_response, success_response
from services.auth import require_admin_key, require_device_key

cleaning_bp = Blueprint("cleaning", __name__)


@cleaning_bp.post("/cleaning/start")
@require_admin_key
def start_cleaning():
    data, error = json_body()
    if error:
        return error
    mode = data.get("operation_mode", "manual")
    if mode not in ("automatic", "manual"):
        return error_response("operation_mode harus automatic atau manual.")

    device_code = str(data.get("device_code", "ESP32_MAIN_01")).strip()
    with get_db_connection() as conn:
        device = conn.execute(
            """SELECT device_id FROM devices
               WHERE device_code = %s AND device_type = 'esp32_controller'
                 AND is_enabled = TRUE""",
            (device_code,),
        ).fetchone()
        if not device:
            return error_response("Controller tidak ditemukan atau dinonaktifkan.", 404)

        session = conn.execute(
            """INSERT INTO cleaning_sessions
               (detection_id, controller_device_id, operation_mode,
                session_status, started_at, notes)
               VALUES (%s, %s, %s, 'approaching', CURRENT_TIMESTAMP, %s)
               RETURNING session_id, session_status, started_at""",
            (data.get("detection_id"), device["device_id"], mode, data.get("notes")),
        ).fetchone()
        conn.execute(
            """INSERT INTO activity_logs (event_type, severity, message, session_id)
               VALUES ('cleaning_started', 'info', 'Sesi pembersihan dibuat dari dashboard.', %s)""",
            (session["session_id"],),
        )
    return success_response(session, "Sesi pembersihan dibuat.", 201)


@cleaning_bp.put("/cleaning/<int:session_id>/status")
@require_device_key
def update_cleaning_status(session_id: int):
    data, error = json_body()
    if error:
        return error

    allowed_status = {
        "pending", "approaching", "mopping", "verifying",
        "completed", "failed", "cancelled",
    }
    status = data.get("session_status")
    if status not in allowed_status:
        return error_response("session_status tidak valid.")

    verification_result = data.get("verification_result")
    if verification_result not in (None, "clean", "still_dirty", "uncertain"):
        return error_response("verification_result tidak valid.")
    verification_confidence = data.get("verification_confidence")
    if verification_confidence is not None:
        try:
            verification_confidence = float(verification_confidence)
        except (ValueError, TypeError):
            return error_response("verification_confidence harus berupa angka 0..1.")
        if not 0 <= verification_confidence <= 1:
            return error_response("verification_confidence harus berada pada rentang 0..1.")

    with get_db_connection() as conn:
        row = conn.execute(
            """UPDATE cleaning_sessions
               SET session_status = %s,
                   completed_at = CASE
                       WHEN %s IN ('completed', 'failed', 'cancelled')
                       THEN CURRENT_TIMESTAMP ELSE completed_at END,
                   mop_duration_seconds = COALESCE(%s, mop_duration_seconds),
                   cleaning_attempts = COALESCE(%s, cleaning_attempts),
                   soap_pump_duration_ms = COALESCE(%s, soap_pump_duration_ms),
                   verification_result = COALESCE(%s, verification_result),
                   verification_confidence = COALESCE(%s, verification_confidence),
                   notes = COALESCE(%s, notes)
               WHERE session_id = %s
               RETURNING session_id, session_status, started_at, completed_at""",
            (
                status, status, data.get("mop_duration_seconds"),
                data.get("cleaning_attempts"), data.get("soap_pump_duration_ms"),
                verification_result, verification_confidence,
                data.get("notes"), session_id,
            ),
        ).fetchone()
        if not row:
            return error_response("Sesi pembersihan tidak ditemukan.", 404)
    return success_response(row, "Status sesi diperbarui.")


@cleaning_bp.get("/cleaning/history")
def cleaning_history():
    with get_db_connection() as conn:
        rows = conn.execute(
            """SELECT session_id, detection_id, controller_device_id,
                      operation_mode, session_status, started_at, completed_at,
                      mop_duration_seconds, cleaning_attempts,
                      verification_result, verification_confidence, notes, created_at
               FROM cleaning_sessions
               ORDER BY created_at DESC LIMIT 100"""
        ).fetchall()
    return success_response(rows)
