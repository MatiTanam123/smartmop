"""Device heartbeat and telemetry persistence."""
from __future__ import annotations
from typing import Any
from .common import device_id_by_code, log_activity


def heartbeat(conn, payload: dict[str, Any], remote_addr: str | None = None) -> dict[str, Any]:
    code = str(payload.get("device_code", "")).strip()
    if not code:
        raise ValueError("device_code wajib diisi.")
    row = conn.execute(
        "SELECT device_id, device_type FROM devices WHERE device_code = %s AND is_enabled = TRUE",
        (code,),
    ).fetchone()
    if not row:
        raise LookupError(f"Device code {code} tidak terdaftar.")

    ip = payload.get("ip_address") or remote_addr
    rssi = payload.get("wifi_rssi")
    if rssi is not None:
        rssi = int(rssi)
        if not -127 <= rssi <= 0:
            raise ValueError("wifi_rssi harus berada pada rentang -127 sampai 0 dBm.")

    conn.execute(
        """UPDATE devices
           SET last_seen_at = CURRENT_TIMESTAMP,
               ip_address = COALESCE(%s::inet, ip_address),
               firmware_version = COALESCE(%s, firmware_version)
           WHERE device_id = %s""",
        (ip, payload.get("firmware_version"), row["device_id"]),
    )
    hb = conn.execute(
        """INSERT INTO device_heartbeats (device_id, ip_address, wifi_rssi)
           VALUES (%s, %s::inet, %s)
           RETURNING heartbeat_id, received_at""",
        (row["device_id"], ip, rssi),
    ).fetchone()
    return {
        "device_code": code,
        "device_type": row["device_type"],
        "heartbeat_id": int(hb["heartbeat_id"]),
        "received_at": hb["received_at"].isoformat(),
    }


def save_telemetry(conn, payload: dict[str, Any]) -> dict[str, Any]:
    code = str(payload.get("device_code", "")).strip()
    device_id = device_id_by_code(conn, code)
    if not device_id:
        raise LookupError(f"Device code {code or '(kosong)'} tidak ditemukan.")

    def maybe_float(key: str):
        value = payload.get(key)
        return None if value is None or value == "" else float(value)

    battery_voltage = maybe_float("battery_voltage")
    battery_percent = maybe_float("battery_percent")
    soap_level = maybe_float("soap_level_percent")
    rssi = payload.get("wifi_rssi")
    if rssi is not None:
        rssi = int(rssi)
        if not -127 <= rssi <= 0:
            raise ValueError("wifi_rssi harus berada pada rentang -127 sampai 0 dBm.")

    row = conn.execute(
        """INSERT INTO device_telemetry
           (device_id, battery_voltage, battery_percent, soap_level_percent, wifi_rssi)
           VALUES (%s, %s, %s, %s, %s)
           RETURNING telemetry_id, measured_at""",
        (device_id, battery_voltage, battery_percent, soap_level, rssi),
    ).fetchone()
    conn.execute(
        "UPDATE devices SET last_seen_at = CURRENT_TIMESTAMP WHERE device_id = %s",
        (device_id,),
    )
    return {"telemetry_id": int(row["telemetry_id"]), "measured_at": row["measured_at"].isoformat()}
