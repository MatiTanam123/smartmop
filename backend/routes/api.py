"""HTTP API used by the SmartMop web UI and ESP32 devices."""
from __future__ import annotations

from datetime import datetime
from functools import wraps
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from flask import Blueprint, current_app, jsonify, request, send_from_directory
from werkzeug.utils import secure_filename

from ..database.connection import get_db
from ..services.common import log_activity, device_id_by_code
from ..services.device_service import heartbeat, save_telemetry
from ..services.detection_service import record_detections, is_spill_class
from ..services.robot_service import (
    acknowledge_command, camera_quality, emergency_stop, move_robot,
    poll_commands, set_actuator, set_mode, start_cleaning,
)
from ..services.settings_service import get_settings, save_settings
from ..ml.preprocess import ALLOWED_EXTENSIONS

api = Blueprint("api", __name__, url_prefix="/api")


def device_auth_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        expected = current_app.config.get("DEVICE_API_KEY", "")
        if expected and request.headers.get("X-Device-Key", "") != expected:
            return jsonify({"ok": False, "error": "Unauthorized device request."}), 401
        return fn(*args, **kwargs)
    return wrapper


def _local_time(dt):
    if dt is None:
        return "--:--:--"
    zone = ZoneInfo(current_app.config.get("TIMEZONE", "Asia/Pontianak"))
    return dt.astimezone(zone).strftime("%H:%M:%S")


def _local_date(dt):
    zone = ZoneInfo(current_app.config.get("TIMEZONE", "Asia/Pontianak"))
    return dt.astimezone(zone).strftime("%Y-%m-%d") if dt else ""


def _num(value):
    return float(value) if value is not None else None


def _device_summary(conn) -> dict:
    seconds = int(current_app.config["DEVICE_ONLINE_SECONDS"])
    row = conn.execute(
        """SELECT device_id, last_seen_at, ip_address
           FROM devices WHERE device_code = 'ESP32_MAIN_01' AND is_enabled = TRUE"""
    ).fetchone()
    last_seen = row["last_seen_at"] if row else None
    online = bool(last_seen and (datetime.now(last_seen.tzinfo) - last_seen).total_seconds() <= seconds)
    telemetry = None
    if row:
        telemetry = conn.execute(
            """SELECT battery_percent, soap_level_percent, battery_voltage, measured_at
               FROM device_telemetry WHERE device_id = %s
               ORDER BY measured_at DESC LIMIT 1""",
            (row["device_id"],),
        ).fetchone()
    settings = conn.execute(
        "SELECT operation_mode FROM robot_settings WHERE setting_id = 1"
    ).fetchone()
    return {
        "robot_online": online,
        "status": "Online" if online else "Offline",
        "mode": (settings["operation_mode"] if settings else "automatic"),
        "battery": _num(telemetry["battery_percent"]) if telemetry else None,
        "soap": _num(telemetry["soap_level_percent"]) if telemetry else None,
        "battery_voltage": _num(telemetry["battery_voltage"]) if telemetry else None,
        "last_seen_at": last_seen.isoformat() if last_seen else None,
        "ip_address": str(row["ip_address"]) if row and row["ip_address"] else None,
    }


def _display_label(class_name: str) -> tuple[str, bool]:
    spill = is_spill_class(class_name)
    if spill:
        return ("Tumpahan Sirup" if "sirup" in class_name.lower() or "syrup" in class_name.lower() else class_name.replace("_", " ").title(), True)
    return ("Tidak Ada Tumpahan" if any(x in class_name.lower() for x in ("clean", "no spill", "tidak ada", "bersih")) else class_name.replace("_", " ").title(), False)


@api.get("/health")
def health():
    try:
        with get_db() as conn:
            conn.execute("SELECT 1")
        detector = current_app.extensions.get("spill_detector")
        return jsonify({
            "ok": True,
            "service": "smartmop-backend",
            "database": "connected",
            "ml_available": bool(detector and detector.available),
        })
    except Exception as exc:
        current_app.logger.exception("Health check database failed")
        return jsonify({"ok": False, "database": "disconnected", "error": str(exc)}), 503


@api.get("/dashboard")
def dashboard():
    with get_db() as conn:
        robot = _device_summary(conn)
        detections = conn.execute(
            """SELECT d.detection_id, d.class_name, d.confidence, d.detected_at,
                      cs.session_status, cs.verification_result
               FROM detections d
               LEFT JOIN LATERAL (
                   SELECT session_status, verification_result
                   FROM cleaning_sessions cs
                   WHERE cs.detection_id = d.detection_id
                   ORDER BY cs.created_at DESC LIMIT 1
               ) cs ON TRUE
               ORDER BY d.detected_at DESC LIMIT 5"""
        ).fetchall()
        logs = conn.execute(
            """SELECT severity, message, created_at
               FROM activity_logs ORDER BY created_at DESC LIMIT 8"""
        ).fetchall()
    mode_label = "Otomatis" if robot["mode"] == "automatic" else "Manual"
    det_rows = []
    for d in detections:
        label, spill = _display_label(d["class_name"])
        status = "-"
        if d["session_status"] == "completed":
            status = "Dibersihkan"
        elif d["session_status"] == "failed":
            status = "Gagal"
        elif d["session_status"] in {"pending", "approaching", "mopping", "verifying"}:
            status = "Menunggu Pembersihan" if d["session_status"] == "pending" else "Sedang Dibersihkan"
        elif spill:
            status = "Menunggu Pembersihan"
        else:
            status = "Lantai Bersih"
        det_rows.append({
            "id": int(d["detection_id"]), "label": label,
            "confidence": round(float(d["confidence"]) * 100),
            "time": _local_time(d["detected_at"]), "spill": spill, "status": status,
        })
    log_rows = []
    for item in logs:
        severity = item["severity"]
        log_rows.append({
            "time": _local_time(item["created_at"]),
            "text": item["message"],
            "type": "danger" if severity == "error" else "warning" if severity == "warning" else "info",
        })
    return jsonify({
        "robot": {
            "status": robot["status"], "mode": mode_label,
            "soap": robot["soap"], "battery": robot["battery"],
        },
        "detections": det_rows,
        "log": log_rows,
    })


@api.get("/robot/status")
def robot_status():
    with get_db() as conn:
        data = _device_summary(conn)
    return jsonify(data)


@api.get("/history")
def history():
    date_from = request.args.get("from")
    date_to = request.args.get("to")
    requested_status = request.args.get("status")
    try:
        limit = max(1, min(int(request.args.get("limit", 200)), 1000))
    except ValueError:
        limit = 200
    with get_db() as conn:
        rows = conn.execute(
            """SELECT d.detection_id, d.class_name, d.confidence, d.detected_at,
                      cs.session_status, cs.verification_result
               FROM detections d
               LEFT JOIN LATERAL (
                   SELECT session_status, verification_result
                   FROM cleaning_sessions cs
                   WHERE cs.detection_id = d.detection_id
                   ORDER BY cs.created_at DESC LIMIT 1
               ) cs ON TRUE
               WHERE (%s::date IS NULL OR d.detected_at::date >= %s::date)
                 AND (%s::date IS NULL OR d.detected_at::date <= %s::date)
               ORDER BY d.detected_at DESC LIMIT %s""",
            (date_from, date_from, date_to, date_to, limit),
        ).fetchall()
    result = []
    for row in rows:
        label, spill = _display_label(row["class_name"])
        s = row["session_status"]
        status = "Dibersihkan" if s == "completed" else "Gagal" if s == "failed" else "Menunggu" if s in {"pending", "approaching", "mopping", "verifying"} else "-"
        item = {
            "id": int(row["detection_id"]), "date": _local_date(row["detected_at"]),
            "time": _local_time(row["detected_at"]), "label": label,
            "spill": spill, "confidence": round(float(row["confidence"]) * 100), "status": status,
        }
        if not requested_status or item["status"] == requested_status:
            result.append(item)
    return jsonify(result)


@api.get("/settings")
def read_settings():
    with get_db() as conn:
        settings = get_settings(conn)
    return jsonify(settings)


@api.post("/settings")
def write_settings():
    payload = request.get_json(silent=True) or {}
    try:
        with get_db() as conn:
            settings = save_settings(conn, payload)
            log_activity(conn, "settings_updated", "Pengaturan SmartMop diperbarui melalui dashboard.")
        return jsonify({"ok": True, "settings": settings})
    except (ValueError, TypeError) as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@api.post("/robot/mode")
def robot_mode():
    payload = request.get_json(silent=True) or {}
    try:
        with get_db() as conn:
            result = set_mode(conn, payload.get("mode", ""))
        return jsonify({"ok": True, **result})
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except LookupError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 409


@api.post("/robot/move")
def robot_move():
    payload = request.get_json(silent=True) or {}
    try:
        with get_db() as conn:
            result = move_robot(conn, payload.get("direction", ""))
        return jsonify({"ok": True, **result})
    except PermissionError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 409
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except LookupError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 409


@api.post("/robot/clean")
def robot_clean():
    payload = request.get_json(silent=True) or {}
    try:
        with get_db() as conn:
            result = start_cleaning(conn, payload.get("action", ""))
        return jsonify({"ok": True, **result})
    except (ValueError, LookupError) as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@api.post("/robot/pump")
def robot_pump():
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload.get("on"), bool):
        return jsonify({"ok": False, "error": "on harus boolean."}), 400
    try:
        with get_db() as conn:
            result = set_actuator(conn, "pump", payload["on"])
        return jsonify({"ok": True, **result})
    except LookupError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 409


@api.post("/robot/motor")
def robot_motor():
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload.get("on"), bool):
        return jsonify({"ok": False, "error": "on harus boolean."}), 400
    try:
        with get_db() as conn:
            result = set_actuator(conn, "mop_motor", payload["on"])
        return jsonify({"ok": True, **result})
    except LookupError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 409


@api.post("/robot/emergency-stop")
def robot_emergency_stop():
    try:
        with get_db() as conn:
            result = emergency_stop(conn)
        return jsonify({"ok": True, **result})
    except LookupError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 409


@api.post("/camera/quality")
def camera_quality_api():
    payload = request.get_json(silent=True) or {}
    try:
        with get_db() as conn:
            result = camera_quality(conn, payload.get("quality", ""))
        return jsonify({"ok": True, **result})
    except (ValueError, LookupError) as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@api.post("/device/heartbeat")
@device_auth_required
def device_heartbeat():
    payload = request.get_json(silent=True) or {}
    try:
        with get_db() as conn:
            result = heartbeat(conn, payload, request.remote_addr)
        return jsonify({"ok": True, **result})
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except LookupError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 404


@api.post("/device/telemetry")
@device_auth_required
def device_telemetry():
    payload = request.get_json(silent=True) or {}
    try:
        with get_db() as conn:
            result = save_telemetry(conn, payload)
        return jsonify({"ok": True, **result})
    except (ValueError, TypeError) as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except LookupError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 404


@api.get("/device/commands")
@device_auth_required
def device_commands():
    code = request.args.get("device_code", "ESP32_MAIN_01")
    try:
        with get_db() as conn:
            commands = poll_commands(conn, code, request.args.get("limit", 5))
        return jsonify({"ok": True, "commands": commands})
    except (ValueError, LookupError) as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@api.post("/device/commands/<int:command_id>/ack")
@device_auth_required
def device_command_ack(command_id: int):
    payload = request.get_json(silent=True) or {}
    try:
        with get_db() as conn:
            result = acknowledge_command(conn, command_id, payload)
        return jsonify({"ok": True, **result})
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except LookupError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 404


@api.post("/device/sessions/<int:session_id>/status")
@device_auth_required
def device_session_status(session_id: int):
    payload = request.get_json(silent=True) or {}
    status = str(payload.get("status", "")).lower()
    allowed = {"approaching", "mopping", "verifying", "completed", "failed", "cancelled"}
    if status not in allowed:
        return jsonify({"ok": False, "error": "Status sesi tidak valid."}), 400
    verification = payload.get("verification_result")
    if verification not in (None, "clean", "still_dirty", "uncertain"):
        return jsonify({"ok": False, "error": "verification_result tidak valid."}), 400
    confidence = payload.get("verification_confidence")
    try:
        with get_db() as conn:
            row = conn.execute(
                """UPDATE cleaning_sessions SET session_status = %s,
                   started_at = COALESCE(started_at, CASE WHEN %s IN ('approaching','mopping') THEN CURRENT_TIMESTAMP END),
                   completed_at = CASE WHEN %s IN ('completed','failed','cancelled') THEN CURRENT_TIMESTAMP ELSE completed_at END,
                   verification_result = COALESCE(%s, verification_result),
                   verification_confidence = COALESCE(%s, verification_confidence),
                   mop_duration_seconds = COALESCE(%s, mop_duration_seconds),
                   notes = COALESCE(%s, notes)
                   WHERE session_id = %s RETURNING session_id""",
                (status, status, status, verification, confidence,
                 payload.get("mop_duration_seconds"), payload.get("notes"), session_id),
            ).fetchone()
            if not row:
                return jsonify({"ok": False, "error": "Sesi tidak ditemukan."}), 404
            log_activity(conn, "cleaning_status", f"Status sesi #{session_id}: {status}.",
                         severity="error" if status == "failed" else "info", session_id=session_id)
        return jsonify({"ok": True, "session_id": session_id, "status": status})
    except Exception as exc:
        current_app.logger.exception("Failed updating cleaning session")
        return jsonify({"ok": False, "error": str(exc)}), 400


@api.post("/detections")
@device_auth_required
def external_detection():
    """Accept already-computed model output from a trusted ML process."""
    payload = request.get_json(silent=True) or {}
    items = payload.get("detections")
    if items is None:
        items = [payload]
    if not isinstance(items, list):
        return jsonify({"ok": False, "error": "detections harus berupa array."}), 400
    try:
        with get_db() as conn:
            result = record_detections(
                conn, items,
                camera_device_code=payload.get("device_code", "ESP32_CAM_01"),
                image_path=payload.get("image_path"),
                model_name=payload.get("model_name", "external-ml"),
                model_version=payload.get("model_version"),
                inference_ms=payload.get("inference_ms"),
            )
        return jsonify({"ok": True, **result})
    except (ValueError, TypeError) as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except LookupError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 404


@api.post("/camera/upload")
@device_auth_required
def camera_upload():
    upload = request.files.get("image") or request.files.get("file")
    if upload is None or not upload.filename:
        return jsonify({"ok": False, "error": "Kirim file gambar pada field 'image'."}), 400
    ext = Path(upload.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({"ok": False, "error": "Format gambar harus JPG, JPEG, PNG, atau WEBP."}), 400

    original = secure_filename(upload.filename)
    filename = f"{uuid4().hex}_{original or ('capture' + ext)}"
    capture_dir = Path(current_app.config["CAPTURE_DIR"])
    capture_dir.mkdir(parents=True, exist_ok=True)
    filepath = capture_dir / filename
    upload.save(filepath)

    device_code = request.form.get("device_code", "ESP32_CAM_01")
    try:
        with get_db() as conn:
            heartbeat(conn, {"device_code": device_code}, request.remote_addr)
            app_settings = conn.execute("SELECT * FROM app_settings WHERE setting_id = 1").fetchone() or {}
            robot_settings = conn.execute("SELECT * FROM robot_settings WHERE setting_id = 1").fetchone() or {}
            keep_image = bool(app_settings.get("save_detection_images", True))
            image_path = f"/api/captures/{filename}" if keep_image else None
            detector = current_app.extensions["spill_detector"]
            result = detector.predict(
                filepath,
                confidence=float(robot_settings.get("confidence_threshold", 0.65)),
                image_size=int(app_settings.get("image_size", current_app.config["ML_IMAGE_SIZE"])),
            )
            if not result["available"]:
                if not keep_image:
                    filepath.unlink(missing_ok=True)
                return jsonify({
                    "ok": True, "image_saved": keep_image,
                    "image_url": image_path,
                    "ml_available": False,
                    "message": "Gambar diterima, tetapi model belum tersedia. Letakkan bobot model pada backend/ml/models/best.pt.",
                    "model_error": result.get("error"),
                }), 202
            detections_result = record_detections(
                conn,
                result["detections"],
                camera_device_code=device_code,
                image_path=image_path,
                model_name=result.get("model_name", "YOLO"),
                model_version=result.get("model_version"),
                inference_ms=result.get("inference_ms"),
            )
            if not keep_image:
                filepath.unlink(missing_ok=True)
        return jsonify({
            "ok": True, "image_saved": keep_image, "image_url": image_path,
            "ml_available": True, "inference_ms": result["inference_ms"],
            **detections_result,
        })
    except Exception as exc:
        current_app.logger.exception("Camera upload/inference failed")
        if filepath.exists() and not locals().get("keep_image", True):
            filepath.unlink(missing_ok=True)
        return jsonify({"ok": False, "error": str(exc)}), 500


@api.get("/captures/<path:filename>")
def get_capture(filename: str):
    return send_from_directory(current_app.config["CAPTURE_DIR"], filename)
