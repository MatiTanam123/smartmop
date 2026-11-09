from flask import Blueprint, jsonify
from database.connection import get_db_connection
from routes.helpers import json_body, error_response, success_response

detection_bp = Blueprint("detections", __name__)

@detection_bp.post("/camera/frame")
def create_camera_frame():
    data, error = json_body()
    if error:
        return error
    code = data.get("device_code", "ESP32_CAM_01")
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT device_id FROM devices WHERE device_code = %s AND is_enabled = TRUE", (code,))
        device = cur.fetchone()
        if not device:
            return error_response("Perangkat kamera tidak ditemukan", 404)

        cur.execute("""
            INSERT INTO camera_frames
                (camera_device_id, image_path, has_spill, highest_spill_confidence,
                 model_name, model_version, inference_ms, processed)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING frame_id, captured_at
        """, (
            device["device_id"], data.get("image_path"),
            data.get("has_spill", False), data.get("highest_spill_confidence"),
            data.get("model_name"), data.get("model_version"),
            data.get("inference_ms"), data.get("processed", True)
        ))
        frame = cur.fetchone()
        return success_response(frame, "Frame kamera tersimpan", 201)

@detection_bp.post("/detections")
def create_detection():
    data, error = json_body()
    if error:
        return error
    if not data.get("class_name") or data.get("confidence") is None:
        return error_response("class_name dan confidence wajib diisi")

    with get_db_connection() as conn, conn.cursor() as cur:
        camera_code = data.get("device_code", "ESP32_CAM_01")
        cur.execute("SELECT device_id FROM devices WHERE device_code = %s", (camera_code,))
        device = cur.fetchone()
        if not device:
            return error_response("Perangkat kamera tidak ditemukan", 404)

        cur.execute("""
            INSERT INTO detections
                (camera_device_id, frame_id, class_name, confidence,
                 bbox_x, bbox_y, bbox_width, bbox_height, image_path,
                 model_name, model_version, inference_ms, decision_status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING detection_id, detected_at
        """, (
            device["device_id"], data.get("frame_id"), data["class_name"],
            data["confidence"], data.get("bbox_x"), data.get("bbox_y"),
            data.get("bbox_width"), data.get("bbox_height"),
            data.get("image_path"), data.get("model_name"),
            data.get("model_version"), data.get("inference_ms"),
            data.get("decision_status", "accepted")
        ))
        detection = cur.fetchone()
        cur.execute("""
            INSERT INTO activity_logs (event_type, severity, message, detection_id)
            VALUES ('detection', 'info', %s, %s)
        """, (f"Deteksi {data['class_name']} diterima", detection["detection_id"]))
        return success_response(detection, "Hasil deteksi tersimpan", 201)

@detection_bp.get("/detections")
def list_detections():
    limit = min(max(int(__import__("flask").request.args.get("limit", 50)), 1), 200)
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT detection_id, camera_device_id, frame_id, detected_at,
                   class_name, confidence, bbox_x, bbox_y, bbox_width,
                   bbox_height, image_path, model_name, model_version,
                   inference_ms, decision_status
            FROM detections ORDER BY detected_at DESC LIMIT %s
        """, (limit,))
        return success_response(cur.fetchall())
