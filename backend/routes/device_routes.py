from flask import Blueprint, jsonify
from database.connection import get_db_connection
from routes.helpers import json_body, error_response, success_response

device_bp = Blueprint("devices", __name__)

@device_bp.get("/devices")
def get_devices():
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT device_id, device_code, device_type, device_name,
                   ip_address, firmware_version, last_seen_at, is_enabled
            FROM devices ORDER BY device_id
        """)
        return success_response(cur.fetchall())

@device_bp.get("/devices/status")
def get_device_status():
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM v_device_connection_status ORDER BY device_id")
        return success_response(cur.fetchall())

@device_bp.post("/device/heartbeat")
def heartbeat():
    data, error = json_body()
    if error:
        return error
    code = data.get("device_code")
    if not code:
        return error_response("device_code wajib diisi")

    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT device_id FROM devices WHERE device_code = %s AND is_enabled = TRUE", (code,))
        device = cur.fetchone()
        if not device:
            return error_response("Perangkat tidak ditemukan atau dinonaktifkan", 404)

        device_id = device["device_id"]
        cur.execute("""
            UPDATE devices
            SET last_seen_at = CURRENT_TIMESTAMP,
                ip_address = COALESCE(%s::inet, ip_address),
                firmware_version = COALESCE(%s, firmware_version)
            WHERE device_id = %s
        """, (data.get("ip_address"), data.get("firmware_version"), device_id))

        cur.execute("""
            INSERT INTO device_heartbeats (device_id, ip_address, wifi_rssi)
            VALUES (%s, %s::inet, %s)
            RETURNING heartbeat_id, received_at
        """, (device_id, data.get("ip_address"), data.get("wifi_rssi")))
        result = cur.fetchone()
        return success_response(result, "Heartbeat diterima", 201)

@device_bp.post("/device/telemetry")
def telemetry():
    data, error = json_body()
    if error:
        return error
    code = data.get("device_code")
    if not code:
        return error_response("device_code wajib diisi")

    allowed = ("battery_voltage", "battery_percent", "soap_level_percent", "wifi_rssi")
    if not any(key in data for key in allowed):
        return error_response("Minimal satu data telemetry harus dikirim")

    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT device_id FROM devices WHERE device_code = %s AND is_enabled = TRUE", (code,))
        device = cur.fetchone()
        if not device:
            return error_response("Perangkat tidak ditemukan", 404)

        cur.execute("""
            INSERT INTO device_telemetry
                (device_id, battery_voltage, battery_percent, soap_level_percent, wifi_rssi)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING telemetry_id, measured_at
        """, (
            device["device_id"], data.get("battery_voltage"),
            data.get("battery_percent"), data.get("soap_level_percent"),
            data.get("wifi_rssi")
        ))
        return success_response(cur.fetchone(), "Telemetry tersimpan", 201)
