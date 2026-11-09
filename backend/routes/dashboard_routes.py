from flask import Blueprint
from database.connection import get_db_connection
from routes.helpers import success_response

dashboard_bp = Blueprint("dashboard", __name__)

@dashboard_bp.get("/dashboard")
def dashboard():
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS total_devices FROM devices WHERE is_enabled = TRUE")
        devices = cur.fetchone()
        cur.execute("SELECT COUNT(*) AS online_devices FROM v_device_connection_status WHERE connection_status = 'online'")
        online = cur.fetchone()
        cur.execute("SELECT COUNT(*) AS total_detections FROM detections WHERE detected_at >= CURRENT_DATE")
        detections = cur.fetchone()
        cur.execute("SELECT COUNT(*) AS active_sessions FROM cleaning_sessions WHERE session_status IN ('pending','approaching','mopping','verifying')")
        active = cur.fetchone()
        cur.execute("SELECT COUNT(*) AS completed_sessions_today FROM cleaning_sessions WHERE session_status = 'completed' AND completed_at >= CURRENT_DATE")
        completed = cur.fetchone()
        cur.execute("SELECT * FROM v_device_connection_status ORDER BY device_id")
        device_status = cur.fetchall()
        cur.execute("SELECT telemetry_id, device_id, battery_voltage, battery_percent, soap_level_percent, wifi_rssi, measured_at FROM device_telemetry ORDER BY measured_at DESC LIMIT 1")
        latest_telemetry = cur.fetchone()
        return success_response({
            "total_devices": devices["total_devices"],
            "online_devices": online["online_devices"],
            "detections_today": detections["total_detections"],
            "active_cleaning_sessions": active["active_sessions"],
            "completed_sessions_today": completed["completed_sessions_today"],
            "devices": device_status,
            "latest_telemetry": latest_telemetry
        })
