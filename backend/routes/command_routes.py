from flask import Blueprint
from database.connection import get_db_connection
from routes.helpers import json_body, error_response, success_response

command_bp = Blueprint("commands", __name__)

@command_bp.get("/commands/pending")
def pending_commands():
    code = __import__("flask").request.args.get("device_code", "ESP32_MAIN_01")
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT device_id FROM devices WHERE device_code = %s", (code,))
        device = cur.fetchone()
        if not device:
            return error_response("Perangkat tidak ditemukan", 404)
        cur.execute("""
            SELECT command_id, session_id, command_type, command_payload, created_at
            FROM robot_commands
            WHERE device_id = %s AND command_status = 'queued'
            ORDER BY created_at ASC LIMIT 20
        """, (device["device_id"],))
        commands = cur.fetchall()
        if commands:
            ids = [item["command_id"] for item in commands]
            cur.execute("""
                UPDATE robot_commands
                SET command_status = 'sent', sent_at = CURRENT_TIMESTAMP
                WHERE command_id = ANY(%s)
            """, (ids,))
        return success_response(commands)

@command_bp.post("/commands/<int:command_id>/ack")
def acknowledge_command(command_id):
    data, error = json_body()
    if error:
        return error
    status = data.get("command_status", "acknowledged")
    if status not in ("acknowledged", "failed"):
        return error_response("command_status harus acknowledged atau failed")

    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute("""
            UPDATE robot_commands
            SET command_status = %s,
                response_payload = %s,
                acknowledged_at = CURRENT_TIMESTAMP
            WHERE command_id = %s
            RETURNING command_id, command_status, acknowledged_at
        """, (status, __import__("json").dumps(data.get("response_payload", {})), command_id))
        result = cur.fetchone()
        if not result:
            return error_response("Perintah tidak ditemukan", 404)
        return success_response(result, "Acknowledgement diterima")

@command_bp.post("/commands")
def create_command():
    data, error = json_body()
    if error:
        return error
    if not data.get("command_type"):
        return error_response("command_type wajib diisi")
    with get_db_connection() as conn, conn.cursor() as cur:
        code = data.get("device_code", "ESP32_MAIN_01")
        cur.execute("SELECT device_id FROM devices WHERE device_code = %s", (code,))
        device = cur.fetchone()
        if not device:
            return error_response("Perangkat tidak ditemukan", 404)
        cur.execute("""
            INSERT INTO robot_commands (device_id, session_id, command_type, command_payload)
            VALUES (%s, %s, %s, %s::jsonb)
            RETURNING command_id, command_type, command_status, created_at
        """, (device["device_id"], data.get("session_id"), data["command_type"],
              __import__("json").dumps(data.get("command_payload", {}))))
        return success_response(cur.fetchone(), "Perintah dibuat", 201)
