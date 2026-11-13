from flask import Blueprint

from database.connection import get_db_connection
from routes.helpers import json_body, error_response, success_response
from services.auth import require_admin_key

settings_bp = Blueprint("settings", __name__)

SETTINGS_CONFIG = {
    "robot_settings": ("setting_id", {
        "robot_name", "operation_mode", "camera_interval_seconds",
        "confidence_threshold", "confirmation_frames", "movement_speed",
        "mop_duration_seconds", "cleaning_repeats", "soap_volume_preset",
        "dashboard_refresh_seconds",
    }),
    "notification_settings": ("notification_setting_id", {
        "website_notification", "sound_notification", "browser_notification",
        "spill_detected", "cleaning_completed", "system_error",
        "low_battery", "low_soap",
    }),
    "app_settings": ("setting_id", {
        "image_size", "show_bbox", "save_detection_images",
        "low_battery_threshold", "low_soap_threshold", "stop_on_low_battery",
        "wifi_ssid", "server_host", "api_port", "api_prefix",
        "camera_ip", "controller_ip",
    }),
}


def read_settings(table: str):
    key, _allowed = SETTINGS_CONFIG[table]
    with get_db_connection() as conn:
        row = conn.execute(
            f"SELECT * FROM {table} WHERE {key} = 1"
        ).fetchone()
    return success_response(row)


def update_settings(table: str):
    data, error = json_body()
    if error:
        return error
    key, allowed = SETTINGS_CONFIG[table]
    updates = {name: value for name, value in data.items() if name in allowed}
    if not updates:
        return error_response("Tidak ada field pengaturan yang valid.")

    # Identifiers are taken only from the fixed allowlist above.
    assignments = ", ".join(f"{column} = %s" for column in updates)
    values = list(updates.values()) + [1]
    with get_db_connection() as conn:
        row = conn.execute(
            f"UPDATE {table} SET {assignments}, updated_at = CURRENT_TIMESTAMP "
            f"WHERE {key} = %s RETURNING *",
            values,
        ).fetchone()
        if not row:
            return error_response("Baris pengaturan default tidak ditemukan. Jalankan schema.sql.", 404)
    return success_response(row, "Pengaturan diperbarui.")


@settings_bp.get("/settings")
def get_robot_settings():
    return read_settings("robot_settings")


@settings_bp.put("/settings")
@require_admin_key
def put_robot_settings():
    return update_settings("robot_settings")


@settings_bp.get("/notifications/settings")
def get_notification_settings():
    return read_settings("notification_settings")


@settings_bp.put("/notifications/settings")
@require_admin_key
def put_notification_settings():
    return update_settings("notification_settings")


@settings_bp.get("/app-settings")
def get_app_settings():
    return read_settings("app_settings")


@settings_bp.put("/app-settings")
@require_admin_key
def put_app_settings():
    return update_settings("app_settings")
