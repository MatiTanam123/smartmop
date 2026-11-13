from __future__ import annotations

import ipaddress
from flask import Blueprint

from database.connection import get_db_connection
from routes.helpers import json_body, error_response, success_response
from services.auth import require_device_key

device_bp = Blueprint("devices", __name__)


def valid_ip_or_none(value):
    if value in (None, ""):
        return None
    try:
        return str(ipaddress.ip_address(str(value)))
    except ValueError:
        raise ValueError("ip_address bukan alamat IP yang valid.")


@device_bp.get("/devices")
def get_devices():
    with get_db_connection() as conn:
        rows = conn.execute("""SELECT device_id, device_code, device_type, device_name,
                                      ip_address, firmware_version, last_seen_at, is_enabled
                               FROM devices ORDER BY device_id""").fetchall()
    return success_response(rows)


@device_bp.get("/devices/status")
def get_device_status():
    with get_db_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM v_device_connection_status ORDER BY device_id"
        ).fetchall()
    return success_response(rows)


@device_bp.post("/device/heartbeat")
@require_device_key
def heartbeat():
    data, error = json_body()
    if error:
        return error
    code = str(data.get("device_code") or "").strip()
    if not code:
        return error_response("device_code wajib diisi.")
    try:
        ip_address = valid_ip_or_none(data.get("ip_address"))
    except ValueError as exc:
        return error_response(str(exc))

    with get_db_connection() as conn:
        device = conn.execute(
            "SELECT device_id FROM devices WHERE device_code = %s AND is_enabled = TRUE",
            (code,),
        ).fetchone()
        if not device:
            return error_response("Perangkat tidak ditemukan atau dinonaktifkan.", 404)

        conn.execute(
            """UPDATE devices
               SET last_seen_at = CURRENT_TIMESTAMP,
                   ip_address = COALESCE(%s::inet, ip_address),
                   firmware_version = COALESCE(%s, firmware_version)
               WHERE device_id = %s""",
            (ip_address, data.get("firmware_version"), device["device_id"]),
        )
        result = conn.execute(
            """INSERT INTO device_heartbeats (device_id, ip_address, wifi_rssi)
               VALUES (%s, %s::inet, %s)
               RETURNING heartbeat_id, received_at""",
            (device["device_id"], ip_address, data.get("wifi_rssi")),
        ).fetchone()
    return success_response(result, "Heartbeat diterima.", 201)


@device_bp.post("/device/telemetry")
@require_device_key
def telemetry():
    data, error = json_body()
    if error:
        return error
    code = str(data.get("device_code") or "").strip()
    if not code:
        return error_response("device_code wajib diisi.")

    allowed = (
        "battery_voltage", "battery_percent", "soap_level_percent",
        "soap_available", "wifi_rssi",
    )
    if not any(key in data for key in allowed):
        return error_response("Minimal satu nilai telemetry harus dikirim.")
    if "soap_available" in data and data["soap_available"] is not None and not isinstance(data["soap_available"], bool):
        return error_response("soap_available harus boolean true/false.")

    with get_db_connection() as conn:
        device = conn.execute(
            "SELECT device_id FROM devices WHERE device_code = %s AND is_enabled = TRUE",
            (code,),
        ).fetchone()
        if not device:
            return error_response("Perangkat tidak ditemukan atau dinonaktifkan.", 404)

        result = conn.execute(
            """INSERT INTO device_telemetry
               (device_id, battery_voltage, battery_percent,
                soap_level_percent, soap_available, wifi_rssi)
               VALUES (%s, %s, %s, %s, %s, %s)
               RETURNING telemetry_id, measured_at""",
            (
                device["device_id"], data.get("battery_voltage"),
                data.get("battery_percent"), data.get("soap_level_percent"),
                data.get("soap_available"), data.get("wifi_rssi"),
            ),
        ).fetchone()
    return success_response(result, "Telemetry tersimpan.", 201)
