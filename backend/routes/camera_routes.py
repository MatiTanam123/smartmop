"""Camera upload, latest-frame, and frame-image endpoints.

ESP32-CAM -> POST /api/camera/upload (multipart field: image)
Website   -> GET  /api/camera/latest-frame?device_code=ESP32_CAM_01
Image     -> GET  /api/camera/frames/<frame_id>/image
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

from flask import Blueprint, abort, current_app, jsonify, redirect, request, send_file, url_for

from database.connection import get_db_connection
from routes.helpers import error_response, success_response
from services.ai_service import InvalidImageError, ModelUnavailableError, predict_image
from services.auth import require_device_key
from services.detection_service import record_detections

camera_bp = Blueprint("camera", __name__, url_prefix="/api/camera")


def _serialize(value):
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _parse_capture_time(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("captured_at harus berupa timestamp ISO-8601.") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _build_image_url(image_path: str | None, frame_id: int) -> str | None:
    if not image_path:
        return None
    parsed = urlparse(str(image_path))
    if parsed.scheme in {"http", "https"}:
        return str(image_path)
    return url_for("camera.get_frame_image", frame_id=frame_id, _external=True)


@camera_bp.post("/upload")
@require_device_key
def upload_camera_frame():
    """Validate upload, run YOLO on server, then store frame + detections."""
    upload = request.files.get("image")
    if upload is None:
        return error_response("File wajib dikirim pada field multipart 'image'.", 400)

    device_code = str(
        request.form.get("device_code") or current_app.config["CAMERA_DEVICE_CODE"]
    ).strip()
    if not device_code:
        return error_response("device_code wajib diisi.", 400)

    try:
        captured_at = _parse_capture_time(request.form.get("captured_at"))
    except ValueError as exc:
        return error_response(str(exc), 400)

    max_bytes = current_app.config["MAX_IMAGE_UPLOAD_BYTES"]
    image_bytes = upload.stream.read(max_bytes + 1)
    if not image_bytes:
        return error_response("File gambar kosong.", 400)
    if len(image_bytes) > max_bytes:
        return error_response("Ukuran gambar melebihi batas upload.", 413)

    stored_file: Path | None = None
    committed = False
    try:
        inference = predict_image(image_bytes)
        extension = {
            "jpeg": ".jpg",
            "png": ".png",
            "webp": ".webp",
        }[inference["image_format"]]

        now = datetime.now(timezone.utc)
        relative_path = (
            Path("captures")
            / now.strftime("%Y")
            / now.strftime("%m")
            / now.strftime("%d")
            / f"{uuid.uuid4().hex}{extension}"
        )
        media_root: Path = Path(current_app.config["MEDIA_ROOT"])
        stored_file = (media_root / relative_path).resolve()
        stored_file.parent.mkdir(parents=True, exist_ok=True)

        # Atomic file write: final file appears only after bytes are fully written.
        temp_file = stored_file.with_name(stored_file.name + ".tmp")
        temp_file.write_bytes(image_bytes)
        temp_file.replace(stored_file)

        with get_db_connection() as conn:
            saved = record_detections(
                conn,
                inference["detections"],
                camera_device_code=device_code,
                image_path=relative_path.as_posix(),
                model_name=inference["model_name"],
                model_version=inference["model_version"],
                inference_ms=inference["inference_ms"],
                captured_at=captured_at,
                device_ip=request.remote_addr,
            )
        committed = True

        saved["image_url"] = url_for(
            "camera.get_frame_image",
            frame_id=saved["frame_id"],
            _external=True,
        )
        saved["image_width"] = inference["image_width"]
        saved["image_height"] = inference["image_height"]
        return success_response(saved, "Frame berhasil diproses YOLO dan disimpan.", 201)

    except InvalidImageError as exc:
        return error_response(str(exc), 415)
    except ModelUnavailableError as exc:
        current_app.logger.error("YOLO model unavailable: %s", exc)
        return error_response(str(exc), 503)
    except LookupError as exc:
        return error_response(str(exc), 404)
    except ValueError as exc:
        return error_response(str(exc), 400)
    except Exception:
        current_app.logger.exception("SMARTMOP camera upload failed.")
        return error_response("Gagal memproses frame kamera. Periksa log backend.", 500)
    finally:
        if stored_file is not None and not committed:
            try:
                stored_file.unlink(missing_ok=True)
            except OSError:
                current_app.logger.warning("Gagal membersihkan file frame yang tidak tersimpan: %s", stored_file)


@camera_bp.get("/latest-frame")
def latest_frame():
    device_code = request.args.get(
        "device_code", current_app.config["CAMERA_DEVICE_CODE"]
    ).strip()
    if not device_code:
        return error_response("device_code wajib diisi.", 400)

    try:
        with get_db_connection() as conn:
            frame = conn.execute(
                """SELECT cf.frame_id, cf.camera_device_id, cf.captured_at,
                          cf.image_path, cf.has_spill, cf.highest_spill_confidence,
                          cf.model_name, cf.model_version, cf.inference_ms,
                          cf.processed, d.device_code
                   FROM camera_frames cf
                   JOIN devices d ON d.device_id = cf.camera_device_id
                   WHERE d.device_code = %s
                     AND d.device_type = 'esp32_cam'
                     AND d.is_enabled = TRUE
                     AND cf.processed = TRUE
                   ORDER BY cf.captured_at DESC, cf.frame_id DESC
                   LIMIT 1""",
                (device_code,),
            ).fetchone()

            if frame is None:
                return jsonify({
                    "success": True,
                    "message": "Belum ada frame kamera yang diproses.",
                    "data": None,
                }), 200

            detections = conn.execute(
                """SELECT detection_id, frame_id, class_name, confidence,
                          bbox_x, bbox_y, bbox_width, bbox_height, decision_status,
                          detected_at
                   FROM detections
                   WHERE frame_id = %s AND decision_status = 'accepted'
                   ORDER BY confidence DESC, detection_id ASC""",
                (frame["frame_id"],),
            ).fetchall()
            settings = conn.execute(
                "SELECT show_bbox FROM app_settings WHERE setting_id = 1"
            ).fetchone()

        data = dict(frame)
        data["image_url"] = _build_image_url(data.get("image_path"), int(data["frame_id"]))
        data["detections"] = detections
        data["show_bbox"] = bool(settings["show_bbox"]) if settings else True
        return success_response(_serialize(data), "Frame kamera terbaru berhasil diambil.")

    except Exception:
        current_app.logger.exception("Gagal mengambil frame kamera terbaru.")
        return error_response("Gagal mengambil frame kamera dari database.", 503)


@camera_bp.get("/frames/<int:frame_id>/image")
def get_frame_image(frame_id: int):
    try:
        with get_db_connection() as conn:
            row = conn.execute(
                "SELECT image_path FROM camera_frames WHERE frame_id = %s",
                (frame_id,),
            ).fetchone()

        if not row or not row.get("image_path"):
            abort(404)

        image_path = str(row["image_path"])
        parsed = urlparse(image_path)
        if parsed.scheme in {"http", "https"}:
            return redirect(image_path, code=302)

        media_root = Path(current_app.config["MEDIA_ROOT"]).resolve()
        candidate = (media_root / image_path).resolve()
        try:
            candidate.relative_to(media_root)
        except ValueError:
            abort(403)

        if not candidate.is_file():
            abort(404)
        return send_file(candidate, conditional=True, max_age=0)

    except Exception as exc:
        if getattr(exc, "code", None) in {403, 404}:
            raise
        current_app.logger.exception("Gagal menyajikan gambar frame %s.", frame_id)
        abort(404)
