from flask import Blueprint, request

from database.connection import get_db_connection
from routes.helpers import json_body, error_response, success_response
from services.auth import require_admin_key

log_bp = Blueprint("logs", __name__)


@log_bp.get("/logs")
def get_logs():
    limit = request.args.get("limit", default=50, type=int) or 50
    limit = max(1, min(limit, 200))
    with get_db_connection() as conn:
        rows = conn.execute(
            """SELECT log_id, event_type, severity, message,
                      detection_id, session_id, created_at
               FROM activity_logs ORDER BY created_at DESC LIMIT %s""",
            (limit,),
        ).fetchall()
    return success_response(rows)


@log_bp.post("/logs")
@require_admin_key
def create_log():
    data, error = json_body()
    if error:
        return error
    if not data.get("event_type") or not data.get("message"):
        return error_response("event_type dan message wajib diisi.")
    severity = data.get("severity", "info")
    if severity not in {"info", "warning", "error"}:
        return error_response("severity harus info, warning, atau error.")

    with get_db_connection() as conn:
        row = conn.execute(
            """INSERT INTO activity_logs
               (event_type, severity, message, detection_id, session_id)
               VALUES (%s, %s, %s, %s, %s)
               RETURNING log_id, created_at""",
            (
                data["event_type"], severity, data["message"],
                data.get("detection_id"), data.get("session_id"),
            ),
        ).fetchone()
    return success_response(row, "Log tersimpan.", 201)
