from __future__ import annotations

from psycopg.types.json import Jsonb
from flask import Blueprint, request

from database.connection import get_db_connection
from routes.helpers import json_body, error_response, success_response
from services.auth import require_admin_key, require_device_key

command_bp = Blueprint("commands", __name__)


@command_bp.get("/commands/pending")
@require_device_key
def pending_commands():
    code = str(request.args.get("device_code", "ESP32_MAIN_01")).strip()
    with get_db_connection() as conn:
        device = conn.execute(
            """SELECT device_id FROM devices
               WHERE device_code = %s AND device_type = 'esp32_controller'
                 AND is_enabled = TRUE""",
            (code,),
        ).fetchone()
        if not device:
            return error_response("Controller tidak ditemukan atau dinonaktifkan.", 404)

        # Atomic claim prevents two simultaneous polls from receiving the same command.
        rows = conn.execute(
            """WITH picked AS (
                   SELECT command_id
                   FROM robot_commands
                   WHERE device_id = %s AND command_status = 'queued'
                   ORDER BY created_at ASC
                   LIMIT 20
                   FOR UPDATE SKIP LOCKED
               )
               UPDATE robot_commands AS command
               SET command_status = 'sent', sent_at = CURRENT_TIMESTAMP
               FROM picked
               WHERE command.command_id = picked.command_id
               RETURNING command.command_id, command.session_id,
                         command.command_type, command.command_payload,
                         command.created_at""",
            (device["device_id"],),
        ).fetchall()
    return success_response(rows, "Antrean perintah berhasil diambil.")


@command_bp.post("/commands/<int:command_id>/ack")
@require_device_key
def acknowledge_command(command_id: int):
    data, error = json_body()
    if error:
        return error
    status = str(data.get("command_status", "acknowledged"))
    if status not in {"acknowledged", "failed"}:
        return error_response("command_status harus acknowledged atau failed.")

    response_payload = data.get("response_payload") or {}
    if not isinstance(response_payload, dict):
        return error_response("response_payload harus berupa JSON object.")
    device_code = str(response_payload.get("device_code") or data.get("device_code") or "").strip()
    if not device_code:
        return error_response("response_payload.device_code wajib diisi untuk ACK.")

    with get_db_connection() as conn:
        row = conn.execute(
            """UPDATE robot_commands AS command
               SET command_status = %s,
                   response_payload = %s,
                   acknowledged_at = CURRENT_TIMESTAMP
               FROM devices
               WHERE command.command_id = %s
                 AND command.device_id = devices.device_id
                 AND devices.device_code = %s
                 AND devices.device_type = 'esp32_controller'
               RETURNING command.command_id, command.command_status,
                         command.acknowledged_at""",
            (status, Jsonb(response_payload), command_id, device_code),
        ).fetchone()
        if not row:
            return error_response("Perintah tidak ditemukan atau bukan milik controller ini.", 404)
    return success_response(row, "Acknowledgement diterima.")


@command_bp.post("/commands")
@require_admin_key
def create_command():
    data, error = json_body()
    if error:
        return error
    command_type = str(data.get("command_type") or "").strip()
    if not command_type:
        return error_response("command_type wajib diisi.")
    if len(command_type) > 50:
        return error_response("command_type maksimal 50 karakter.")

    payload = data.get("command_payload") or {}
    if not isinstance(payload, dict):
        return error_response("command_payload harus berupa JSON object.")

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

        row = conn.execute(
            """INSERT INTO robot_commands
               (device_id, session_id, command_type, command_payload)
               VALUES (%s, %s, %s, %s)
               RETURNING command_id, command_type, command_status, created_at""",
            (device["device_id"], data.get("session_id"), command_type, Jsonb(payload)),
        ).fetchone()
    return success_response(row, "Perintah dibuat dan masuk antrean.", 201)
