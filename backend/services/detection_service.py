"""Persist ML detections and optionally dispatch an automatic cleaning command."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any

from .common import create_command, device_id_by_code, log_activity


def is_spill_class(class_name: str) -> bool:
    value = str(class_name or "").strip().lower().replace("_", " ").replace("-", " ")
    negative = ("no spill", "not spill", "without spill", "no syrup", "clean", "bersih", "tidak ada", "lantai normal")
    if any(term in value for term in negative):
        return False
    return any(term in value for term in ("spill", "syrup", "sirup", "tumpahan"))


def _normal_confidence(value: Any) -> float:
    conf = float(value)
    if 1 < conf <= 100:
        conf /= 100.0
    if not 0 <= conf <= 1:
        raise ValueError("confidence harus berada pada rentang 0..1 atau 0..100 persen.")
    return conf


def record_detections(
    conn,
    items: list[dict[str, Any]],
    *,
    camera_device_code: str = "ESP32_CAM_01",
    image_path: str | None = None,
    model_name: str = "YOLO",
    model_version: str | None = None,
    inference_ms: int | None = None,
) -> dict[str, Any]:
    camera_id = device_id_by_code(conn, camera_device_code)
    if camera_id is None:
        raise LookupError(f"Kamera {camera_device_code} tidak terdaftar di tabel devices.")
    settings = conn.execute(
        "SELECT operation_mode, confidence_threshold, confirmation_frames FROM robot_settings WHERE setting_id = 1"
    ).fetchone() or {"operation_mode": "automatic", "confidence_threshold": 0.65, "confirmation_frames": 3}
    threshold = float(settings["confidence_threshold"])
    frame_time = datetime.now(timezone.utc)

    # Normalize all detections first. One call represents one image/frame.
    prepared: list[dict[str, Any]] = []
    for item in items:
        class_name = str(item.get("class_name") or item.get("label") or "unknown")[:80]
        confidence = _normal_confidence(item.get("confidence", 0))
        spill = is_spill_class(class_name)
        prepared.append({
            "item": item,
            "class_name": class_name,
            "confidence": confidence,
            "spill": spill,
            "decision_status": "accepted" if confidence >= threshold else "rejected",
        })

    accepted_spill_confidences = [
        item["confidence"] for item in prepared
        if item["spill"] and item["decision_status"] == "accepted"
    ]
    frame_has_spill = bool(accepted_spill_confidences)
    frame_row = conn.execute(
        """INSERT INTO camera_frames
           (camera_device_id, captured_at, image_path, has_spill,
            highest_spill_confidence, model_name, model_version, inference_ms, processed)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, TRUE)
           RETURNING frame_id, captured_at""",
        (camera_id, frame_time, image_path, frame_has_spill,
         max(accepted_spill_confidences) if accepted_spill_confidences else None,
         model_name, model_version, inference_ms),
    ).fetchone()
    frame_id = int(frame_row["frame_id"])

    inserted: list[dict[str, Any]] = []
    for item_data in prepared:
        item = item_data["item"]
        class_name = item_data["class_name"]
        confidence = item_data["confidence"]
        spill = item_data["spill"]
        decision = item_data["decision_status"]
        bbox = item.get("bbox") or {}
        x = item.get("bbox_x", bbox.get("x"))
        y = item.get("bbox_y", bbox.get("y"))
        w = item.get("bbox_width", bbox.get("width"))
        h = item.get("bbox_height", bbox.get("height"))
        row = conn.execute(
            """INSERT INTO detections
               (frame_id, camera_device_id, detected_at, class_name, confidence,
                bbox_x, bbox_y, bbox_width, bbox_height, image_path,
                model_name, model_version, inference_ms, decision_status)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               RETURNING detection_id, detected_at""",
            (frame_id, camera_id, frame_time, class_name, confidence, x, y, w, h,
             image_path, model_name, model_version, inference_ms, decision),
        ).fetchone()
        detection_id = int(row["detection_id"])
        inserted.append({
            "detection_id": detection_id,
            "frame_id": frame_id,
            "class_name": class_name,
            "confidence": confidence,
            "spill": spill,
            "decision_status": decision,
            "detected_at": row["detected_at"].isoformat(),
        })
        if decision == "accepted":
            log_activity(
                conn,
                "spill_detected" if spill else "surface_classified",
                f"AI mendeteksi {class_name} dengan confidence {confidence * 100:.1f}%.",
                severity="warning" if spill else "info",
                detection_id=detection_id,
            )

    dispatched = None
    if frame_has_spill and settings["operation_mode"] == "automatic":
        # Count distinct processed frames, including negative frames.
        frame_rows = conn.execute(
            """SELECT has_spill
               FROM camera_frames
               WHERE camera_device_id = %s
                 AND processed = TRUE
                 AND captured_at >= CURRENT_TIMESTAMP - INTERVAL '30 seconds'
               ORDER BY captured_at DESC
               LIMIT %s""",
            (camera_id, int(settings["confirmation_frames"])),
        ).fetchall()
        confirmed = (
            len(frame_rows) >= int(settings["confirmation_frames"])
            and all(bool(row["has_spill"]) for row in frame_rows)
        )
        if confirmed:
            active = conn.execute(
                """SELECT session_id FROM cleaning_sessions
                   WHERE session_status IN ('pending','approaching','mopping','verifying')
                   ORDER BY created_at DESC LIMIT 1"""
            ).fetchone()
            if not active:
                latest = next(x for x in reversed(inserted) if x["spill"] and x["decision_status"] == "accepted")
                controller_id = device_id_by_code(conn, "ESP32_MAIN_01")
                robot_settings = conn.execute(
                    """SELECT mop_duration_seconds, cleaning_repeats,
                              soap_volume_preset, movement_speed
                       FROM robot_settings WHERE setting_id = 1"""
                ).fetchone() or {
                    "mop_duration_seconds": 10, "cleaning_repeats": 2,
                    "soap_volume_preset": "medium", "movement_speed": "slow",
                }
                session = conn.execute(
                    """INSERT INTO cleaning_sessions
                       (detection_id, controller_device_id, operation_mode, session_status,
                        started_at, mop_duration_seconds, notes)
                       VALUES (%s, %s, 'automatic', 'approaching', CURRENT_TIMESTAMP, %s,
                               'Dibuat otomatis setelah konfirmasi frame kamera berturut-turut.')
                       RETURNING session_id""",
                    (latest["detection_id"], controller_id, robot_settings["mop_duration_seconds"]),
                ).fetchone()
                session_id = int(session["session_id"])
                command_id = create_command(
                    conn,
                    "approach_spill",
                    {
                        "frame_id": frame_id,
                        "detection_id": latest["detection_id"],
                        "class_name": latest["class_name"],
                        "confidence": latest["confidence"],
                        "bbox": next((i.get("bbox") for i in items if is_spill_class(i.get("class_name", i.get("label", "")))), None),
                        "instruction": "approach_detected_spill",
                        "cleaning": {
                            "duration_seconds": int(robot_settings["mop_duration_seconds"]),
                            "cleaning_repeats": int(robot_settings["cleaning_repeats"]),
                            "soap_volume_preset": robot_settings["soap_volume_preset"],
                            "movement_speed": robot_settings["movement_speed"],
                        },
                    },
                    session_id=session_id,
                )
                log_activity(
                    conn, "automatic_cleaning_queued",
                    "Tumpahan terkonfirmasi pada beberapa frame kamera; perintah pendekatan masuk antrean robot.",
                    severity="warning", detection_id=latest["detection_id"], session_id=session_id,
                )
                dispatched = {"session_id": session_id, "command_id": command_id, "status": "queued"}

    return {
        "frame_id": frame_id,
        "frame_has_spill": frame_has_spill,
        "detections": inserted,
        "automatic_command": dispatched,
    }
