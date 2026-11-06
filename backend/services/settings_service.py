"""Translate the existing SmartMop frontend setting keys to PostgreSQL columns."""
from __future__ import annotations

DEFAULTS = {
    "namaRobot": "SmartMop-01", "modeAwal": "Otomatis", "kecepatan": "Pelan",
    "waktuPemotretan": "3", "confidence": "0.65", "pengulangan": "2",
    "volumeSabun": "Sedang", "ukuranModel": "640", "bbox": True,
    "simpanGambar": True, "batasBaterai": "20", "batasSabun": "15",
    "stopBaterai": True, "notifWeb": True, "notifSuara": True,
    "notifBrowser": False, "notifSelesai": True, "notifError": True,
    "ssid": "", "serverIP": "", "apiPort": "5000", "apiPath": "/api",
    "cameraIP": "", "controllerIP": "",
}

MODE_TO_DB = {"otomatis": "automatic", "manual": "manual", "automatic": "automatic"}
SPEED_TO_DB = {"pelan": "slow", "lambat": "slow", "slow": "slow", "sedang": "medium", "medium": "medium", "cepat": "fast", "fast": "fast"}
SOAP_TO_DB = {"rendah": "low", "low": "low", "sedang": "medium", "medium": "medium", "tinggi": "high", "high": "high"}


def _as_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _as_int(value, default, minimum, maximum, field):
    try:
        n = int(value)
    except (TypeError, ValueError):
        n = default
    if not minimum <= n <= maximum:
        raise ValueError(f"{field} harus antara {minimum} dan {maximum}.")
    return n


def _optional_ip(value):
    value = str(value or "").strip()
    if value.lower() == "localhost":
        return None
    return value or None


def get_settings(conn) -> dict:
    r = conn.execute("SELECT * FROM robot_settings WHERE setting_id = 1").fetchone() or {}
    n = conn.execute("SELECT * FROM notification_settings WHERE notification_setting_id = 1").fetchone() or {}
    a = conn.execute("SELECT * FROM app_settings WHERE setting_id = 1").fetchone() or {}
    result = DEFAULTS.copy()
    if r:
        result.update({
            "namaRobot": r["robot_name"],
            "modeAwal": "Otomatis" if r["operation_mode"] == "automatic" else "Manual",
            "kecepatan": {"slow": "Pelan", "medium": "Sedang", "fast": "Cepat"}.get(r["movement_speed"], "Pelan"),
            "waktuPemotretan": str(r["camera_interval_seconds"]),
            "confidence": str(float(r["confidence_threshold"])),
            "pengulangan": str(r["cleaning_repeats"]),
            "volumeSabun": {"low": "Rendah", "medium": "Sedang", "high": "Tinggi"}.get(r["soap_volume_preset"], "Sedang"),
        })
    if a:
        result.update({
            "ukuranModel": str(a["image_size"]), "bbox": a["show_bbox"],
            "simpanGambar": a["save_detection_images"],
            "batasBaterai": str(float(a["low_battery_threshold"])),
            "batasSabun": str(float(a["low_soap_threshold"])),
            "stopBaterai": a["stop_on_low_battery"],
            "ssid": a["wifi_ssid"] or "", "serverIP": a["server_host"] or "",
            "apiPort": str(a["api_port"]), "apiPath": a["api_prefix"],
            "cameraIP": str(a["camera_ip"] or ""),
            "controllerIP": str(a["controller_ip"] or ""),
        })
    if n:
        result.update({
            "notifWeb": n["website_notification"],
            "notifSuara": n["sound_notification"],
            "notifBrowser": n["browser_notification"],
            "notifSelesai": n["cleaning_completed"],
            "notifError": n["system_error"],
        })
    return result


def save_settings(conn, payload: dict) -> dict:
    # Keep values for fields not currently shown in the form (for example
    # speed, interval, and repeat count) instead of resetting them on each save.
    s = DEFAULTS.copy()
    s.update(get_settings(conn))
    s.update(payload or {})
    mode_key = str(s["modeAwal"]).strip().lower()
    speed_key = str(s["kecepatan"]).strip().lower()
    soap_key = str(s["volumeSabun"]).strip().lower()
    if mode_key not in MODE_TO_DB:
        raise ValueError("Mode robot harus Otomatis atau Manual.")
    if speed_key not in SPEED_TO_DB:
        raise ValueError("Kecepatan robot tidak valid.")
    if soap_key not in SOAP_TO_DB:
        raise ValueError("Volume sabun tidak valid.")

    camera_interval = _as_int(s["waktuPemotretan"], 3, 1, 60, "Interval kamera")
    confidence = float(s["confidence"])
    if not 0 <= confidence <= 1:
        raise ValueError("Confidence harus berada pada rentang 0 sampai 1.")
    repeats = _as_int(s["pengulangan"], 2, 1, 5, "Pengulangan pengepelan")
    image_size = _as_int(s["ukuranModel"], 640, 320, 1280, "Ukuran gambar")
    if image_size not in {320, 416, 640, 960, 1280}:
        raise ValueError("Ukuran gambar harus 320, 416, 640, 960, atau 1280.")
    low_battery = float(s["batasBaterai"])
    low_soap = float(s["batasSabun"])
    if not 0 <= low_battery <= 100 or not 0 <= low_soap <= 100:
        raise ValueError("Batas baterai dan sabun harus 0 sampai 100 persen.")
    port = _as_int(s["apiPort"], 5000, 1, 65535, "Port API")
    api_prefix = str(s["apiPath"] or "/api").strip()
    if not api_prefix.startswith("/") or " " in api_prefix:
        raise ValueError("Endpoint API harus diawali / dan tidak boleh mengandung spasi.")

    conn.execute(
        """INSERT INTO robot_settings
           (setting_id, robot_name, operation_mode, camera_interval_seconds,
            confidence_threshold, movement_speed, cleaning_repeats, soap_volume_preset,
            updated_at)
           VALUES (1, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
           ON CONFLICT (setting_id) DO UPDATE SET
             robot_name = EXCLUDED.robot_name,
             operation_mode = EXCLUDED.operation_mode,
             camera_interval_seconds = EXCLUDED.camera_interval_seconds,
             confidence_threshold = EXCLUDED.confidence_threshold,
             movement_speed = EXCLUDED.movement_speed,
             cleaning_repeats = EXCLUDED.cleaning_repeats,
             soap_volume_preset = EXCLUDED.soap_volume_preset,
             updated_at = CURRENT_TIMESTAMP""",
        (str(s["namaRobot"])[:80], MODE_TO_DB[mode_key], camera_interval,
         confidence, SPEED_TO_DB[speed_key], repeats, SOAP_TO_DB[soap_key]),
    )
    conn.execute(
        """INSERT INTO app_settings
           (setting_id, image_size, show_bbox, save_detection_images,
            low_battery_threshold, low_soap_threshold, stop_on_low_battery,
            wifi_ssid, server_host, api_port, api_prefix, camera_ip, controller_ip, updated_at)
           VALUES (1, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::inet, %s::inet, CURRENT_TIMESTAMP)
           ON CONFLICT (setting_id) DO UPDATE SET
             image_size = EXCLUDED.image_size,
             show_bbox = EXCLUDED.show_bbox,
             save_detection_images = EXCLUDED.save_detection_images,
             low_battery_threshold = EXCLUDED.low_battery_threshold,
             low_soap_threshold = EXCLUDED.low_soap_threshold,
             stop_on_low_battery = EXCLUDED.stop_on_low_battery,
             wifi_ssid = EXCLUDED.wifi_ssid,
             server_host = EXCLUDED.server_host,
             api_port = EXCLUDED.api_port,
             api_prefix = EXCLUDED.api_prefix,
             camera_ip = EXCLUDED.camera_ip,
             controller_ip = EXCLUDED.controller_ip,
             updated_at = CURRENT_TIMESTAMP""",
        (image_size, _as_bool(s["bbox"], True), _as_bool(s["simpanGambar"], True),
         low_battery, low_soap, _as_bool(s["stopBaterai"], True),
         str(s["ssid"] or "")[:100] or None, str(s["serverIP"] or "").strip() or None,
         port, api_prefix, _optional_ip(s["cameraIP"]), _optional_ip(s["controllerIP"])),
    )
    conn.execute(
        """INSERT INTO notification_settings
           (notification_setting_id, website_notification, sound_notification,
            browser_notification, spill_detected, cleaning_completed, system_error,
            updated_at)
           VALUES (1, %s, %s, %s, TRUE, %s, %s, CURRENT_TIMESTAMP)
           ON CONFLICT (notification_setting_id) DO UPDATE SET
             website_notification = EXCLUDED.website_notification,
             sound_notification = EXCLUDED.sound_notification,
             browser_notification = EXCLUDED.browser_notification,
             cleaning_completed = EXCLUDED.cleaning_completed,
             system_error = EXCLUDED.system_error,
             updated_at = CURRENT_TIMESTAMP""",
        (_as_bool(s["notifWeb"], True), _as_bool(s["notifSuara"], True),
         _as_bool(s["notifBrowser"], False), _as_bool(s["notifSelesai"], True),
         _as_bool(s["notifError"], True)),
    )
    return get_settings(conn)
