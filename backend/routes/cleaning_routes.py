from flask import Blueprint
from database.connection import get_db_connection
from routes.helpers import json_body, error_response, success_response

cleaning_bp = Blueprint("cleaning", __name__)

@cleaning_bp.post("/cleaning/start")
def start_cleaning():
    data, error = json_body()
    if error:
        return error
    mode = data.get("operation_mode", "manual")
    if mode not in ("automatic", "manual"):
        return error_response("operation_mode harus automatic atau manual")

    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT device_id FROM devices WHERE device_code = %s",
                    (data.get("device_code", "ESP32_MAIN_01"),))
        device = cur.fetchone()
        if not device:
            return error_response("Controller tidak ditemukan", 404)

        cur.execute("""
            INSERT INTO cleaning_sessions
                (detection_id, controller_device_id, operation_mode,
                 session_status, started_at, notes)
            VALUES (%s, %s, %s, 'approaching', CURRENT_TIMESTAMP, %s)
            RETURNING session_id, session_status, started_at
        """, (data.get("detection_id"), device["device_id"], mode, data.get("notes")))
        session = cur.fetchone()
        cur.execute("""
            INSERT INTO activity_logs (event_type, severity, message, session_id)
            VALUES ('cleaning_started', 'info', 'Sesi pembersihan dimulai', %s)
        """, (session["session_id"],))
        return success_response(session, "Sesi pembersihan dibuat", 201)

@cleaning_bp.put("/cleaning/<int:session_id>/status")
def update_cleaning_status(session_id):
    data, error = json_body()
    if error:
        return error
    allowed_status = ("pending", "approaching", "mopping", "verifying",
                      "completed", "failed", "cancelled")
    status = data.get("session_status")
    if status not in allowed_status:
        return error_response("session_status tidak valid")

    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute("""
            UPDATE cleaning_sessions
            SET session_status = %s,
                completed_at = CASE WHEN %s IN ('completed', 'failed', 'cancelled')
                                    THEN CURRENT_TIMESTAMP ELSE completed_at END,
                mop_duration_seconds = COALESCE(%s, mop_duration_seconds),
                cleaning_attempts = COALESCE(%s, cleaning_attempts),
                soap_pump_duration_ms = COALESCE(%s, soap_pump_duration_ms),
                verification_result = COALESCE(%s, verification_result),
                verification_confidence = COALESCE(%s, verification_confidence),
                notes = COALESCE(%s, notes)
            WHERE session_id = %s
            RETURNING session_id, session_status, started_at, completed_at
        """, (
            status, status, data.get("mop_duration_seconds"),
            data.get("cleaning_attempts"), data.get("soap_pump_duration_ms"),
            data.get("verification_result"), data.get("verification_confidence"),
            data.get("notes"), session_id
        ))
        result = cur.fetchone()
        if not result:
            return error_response("Sesi tidak ditemukan", 404)
        return success_response(result, "Status sesi diperbarui")

@cleaning_bp.get("/cleaning/history")
def cleaning_history():
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT session_id, detection_id, controller_device_id,
                   operation_mode, session_status, started_at, completed_at,
                   mop_duration_seconds, cleaning_attempts,
                   verification_result, verification_confidence, notes, created_at
            FROM cleaning_sessions ORDER BY created_at DESC LIMIT 100
        """)
        return success_response(cur.fetchall())
