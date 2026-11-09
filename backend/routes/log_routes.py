from flask import Blueprint, request
from database.connection import get_db_connection
from routes.helpers import json_body, error_response, success_response

log_bp = Blueprint("logs", __name__)

@log_bp.get("/logs")
def get_logs():
    limit = min(max(request.args.get("limit", default=50, type=int), 1), 200)
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT log_id, event_type, severity, message,
                   detection_id, session_id, created_at
            FROM activity_logs ORDER BY created_at DESC LIMIT %s
        """, (limit,))
        return success_response(cur.fetchall())

@log_bp.post("/logs")
def create_log():
    data, error = json_body()
    if error:
        return error
    if not data.get("event_type") or not data.get("message"):
        return error_response("event_type dan message wajib diisi")
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute("""
            INSERT INTO activity_logs (event_type, severity, message, detection_id, session_id)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING log_id, created_at
        """, (
            data["event_type"], data.get("severity", "info"), data["message"],
            data.get("detection_id"), data.get("session_id")
        ))
        return success_response(cur.fetchone(), "Log tersimpan", 201)
