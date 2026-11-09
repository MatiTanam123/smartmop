from flask import Blueprint
from database.connection import get_db_connection
from routes.helpers import json_body, error_response, success_response

settings_bp = Blueprint("settings", __name__)

SETTINGS_COLUMNS = {
    "robot_settings": {
        "robot_name", "operation_mode", "camera_interval_seconds",
        "confidence_threshold", "confirmation_frames", "movement_speed",
        "mop_duration_seconds", "cleaning_repeats", "soap_volume_preset",
        "dashboard_refresh_seconds"
    },
    "notification_settings": {
        "website_notification", "sound_notification", "browser_notification",
        "spill_detected", "cleaning_completed", "system_error",
        "low_battery", "low_soap"
    },
    "app_settings": {
        "image_size", "show_bbox", "save_detection_images",
        "low_battery_threshold", "low_soap_threshold", "stop_on_low_battery",
        "wifi_ssid", "server_host", "api_port", "api_prefix",
        "camera_ip", "controller_ip"
    }
}

def read_settings(table):
    with get_db_connection() as conn, conn.cursor() as cur:
        key = "notification_setting_id" if table == "notification_settings" else "setting_id"
        cur.execute(f"SELECT * FROM {table} WHERE {key} = 1")
        return success_response(cur.fetchone())

def update_settings(table):
    data, error = json_body()
    if error:
        return error
    allowed = SETTINGS_COLUMNS[table]
    updates = {k: v for k, v in data.items() if k in allowed}
    if not updates:
        return error_response("Tidak ada field pengaturan yang valid")

    # Nama kolom berasal dari allowlist tetap di atas; nilai tetap memakai parameter SQL.
    assignments = ", ".join([f"{column} = %s" for column in updates])
    key = "notification_setting_id" if table == "notification_settings" else "setting_id"
    values = list(updates.values())
    values.append(1)
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            f"UPDATE {table} SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE {key} = %s RETURNING *",
            values
        )
        result = cur.fetchone()
        if not result:
            return error_response("Baris pengaturan default belum ada. Jalankan INSERT awal dari schema.sql.", 404)
        return success_response(result, "Pengaturan diperbarui")

@settings_bp.get("/settings")
def get_robot_settings():
    return read_settings("robot_settings")

@settings_bp.put("/settings")
def put_robot_settings():
    return update_settings("robot_settings")

@settings_bp.get("/notifications/settings")
def get_notification_settings():
    return read_settings("notification_settings")

@settings_bp.put("/notifications/settings")
def put_notification_settings():
    return update_settings("notification_settings")

@settings_bp.get("/app-settings")
def get_app_settings():
    return read_settings("app_settings")

@settings_bp.put("/app-settings")
def put_app_settings():
    return update_settings("app_settings")
