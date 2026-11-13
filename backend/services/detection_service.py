"""Persist a single YOLO frame into camera_frames and detections."""
from __future__ import annotations

import ipaddress
from datetime import datetime, timezone
from typing import Any

from services.common import log_activity


NEGATIVE_LABELS = (
    "no spill", "no_spill", "not spill", "without spill", "clean",
    "bersih", "tidak ada", "lantai normal",
)
POSITIVE_LABELS = ("spill", "syrup", "sirup", "tumpahan")


def is_spill_class(class_name: str) -> bool:
    label = str(class_name or "").strip().lower().replace("-", " ")
    if any(term in label for term in NEGATIVE_LABELS):
        return False
    return any(term in label for term in POSITIVE_LABELS)


def _confidence(value: Any) -> float:
    score = float(value)
    if 1 < score <= 100:
        score /= 100.0
    if not 0.0 <= score <= 1.0:
        raise ValueError("Confidence harus berada pada rentang 0..1 atau 0..100 persen.")
    return round(score, 4)


def _bbox(item: dict[str, Any]) -> tuple[float, float, float, float]:
    box = item.get("bbox") or {}
    if not isinstance(box, dict):
        raise ValueError("bbox harus berupa object.")
    values = (
        item.get("bbox_x", box.get("x")),
        item.get("bbox_y", box.get("y")),
        item.get("bbox_width", box.get("width")),
        item.get("bbox_height", box.get("height")),
    )
    if any(value is None for value in values):
        raise ValueError("Setiap hasil YOLO wajib memiliki bbox x, y, width, height.")
    x, y, width, height = (float(value) for value in values)
    if not all(0.0 <= number <= 1.0 for number in (x, y, width, height)):
        raise ValueError("Bounding box harus ternormalisasi dalam rentang 0..1.")
    if width <= 0 or height <= 0 or x + width > 1.000001 or y + height > 1.000001:
        raise ValueError("Posisi atau ukuran bounding box tidak valid.")
    return tuple(round(number, 6) for number in (x, y, width, height))


def _valid_ip(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        return None


def record_detections(
    conn,
    items: list[dict[str, Any]],
    *,
    camera_device_code: str,
    image_path: str,
    model_name: str,
    model_version: str,
    inference_ms: int,
    captured_at: datetime | None = None,
    device_ip: str | None = None,
) -> dict[str, Any]:
    """Insert one camera frame plus zero or more YOLO objects.

    IMPORTANT: this service records detection evidence only. It does not create
    motor/movement commands from an image alone. Controller safety logic must
    independently authorize physical movement.
    """
    camera = conn.execute(
        """SELECT device_id, device_type FROM devices
           WHERE device_code = %s AND is_enabled = TRUE""",
        (camera_device_code,),
    ).fetchone()
    if not camera or camera["device_type"] != "esp32_cam":
        raise LookupError(f"Kamera {camera_device_code} tidak terdaftar/aktif sebagai esp32_cam.")

    if inference_ms is None or int(inference_ms) < 0:
        raise ValueError("inference_ms wajib berupa bilangan nol atau lebih.")

    timestamp = captured_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    timestamp = timestamp.astimezone(timezone.utc)

    settings = conn.execute(
        """SELECT operation_mode, confidence_threshold, confirmation_frames
           FROM robot_settings WHERE setting_id = 1"""
    ).fetchone() or {
        "operation_mode": "automatic",
        "confidence_threshold": 0.65,
        "confirmation_frames": 3,
    }
    threshold = float(settings["confidence_threshold"])

    prepared: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        class_name = str(item.get("class_name") or item.get("label") or "unknown")[:80]
        score = _confidence(item.get("confidence", 0))
        x, y, width, height = _bbox(item)
        spill = is_spill_class(class_name)
        prepared.append({
            "class_name": class_name,
            "confidence": score,
            "bbox_x": x,
            "bbox_y": y,
            "bbox_width": width,
            "bbox_height": height,
            "spill": spill,
            "decision_status": "accepted" if score >= threshold else "rejected",
        })

    accepted_spills = [
        item for item in prepared
        if item["spill"] and item["decision_status"] == "accepted"
    ]
    has_spill = bool(accepted_spills)
    highest_confidence = max(
        (item["confidence"] for item in accepted_spills),
        default=None,
    )

    frame = conn.execute(
        """INSERT INTO camera_frames
           (camera_device_id, captured_at, image_path, has_spill,
            highest_spill_confidence, model_name, model_version, inference_ms, processed)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, TRUE)
           RETURNING frame_id, captured_at""",
        (
            camera["device_id"], timestamp, image_path, has_spill,
            highest_confidence, model_name, model_version, int(inference_ms),
        ),
    ).fetchone()
    frame_id = int(frame["frame_id"])

    saved_detections: list[dict[str, Any]] = []
    for item in prepared:
        row = conn.execute(
            """INSERT INTO detections
               (frame_id, camera_device_id, detected_at, class_name, confidence,
                bbox_x, bbox_y, bbox_width, bbox_height, image_path,
                model_name, model_version, inference_ms, decision_status)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               RETURNING detection_id, detected_at""",
            (
                frame_id, camera["device_id"], timestamp, item["class_name"],
                item["confidence"], item["bbox_x"], item["bbox_y"],
                item["bbox_width"], item["bbox_height"], image_path,
                model_name, model_version, int(inference_ms), item["decision_status"],
            ),
        ).fetchone()
        detection = {
            "detection_id": int(row["detection_id"]),
            "frame_id": frame_id,
            **item,
            "detected_at": row["detected_at"].isoformat(),
        }
        saved_detections.append(detection)

        if item["decision_status"] == "accepted":
            is_spill = item["spill"]
            log_activity(
                conn,
                "spill_detected" if is_spill else "object_detected",
                f"YOLO mendeteksi {item['class_name']} dengan confidence {item['confidence'] * 100:.1f}%.",
                severity="warning" if is_spill else "info",
                detection_id=detection["detection_id"],
            )

    clean_ip = _valid_ip(device_ip)
    conn.execute(
        """UPDATE devices
           SET last_seen_at = %s,
               ip_address = COALESCE(%s::inet, ip_address)
           WHERE device_id = %s""",
        (timestamp, clean_ip, camera["device_id"]),
    )
    conn.execute(
        """INSERT INTO device_heartbeats (device_id, ip_address, wifi_rssi)
           VALUES (%s, %s::inet, NULL)""",
        (camera["device_id"], clean_ip),
    )

    needed = int(settings["confirmation_frames"])
    recent = conn.execute(
        """SELECT has_spill FROM camera_frames
           WHERE camera_device_id = %s
           ORDER BY frame_id DESC LIMIT %s""",
        (camera["device_id"], needed),
    ).fetchall()
    spill_confirmed = (
        has_spill
        and len(recent) >= needed
        and all(bool(row["has_spill"]) for row in recent)
    )

    if has_spill:
        log_activity(
            conn,
            "spill_frame_confirmed" if spill_confirmed else "spill_frame_detected",
            (
                f"Tumpahan terkonfirmasi pada {needed} frame berturut-turut."
                if spill_confirmed
                else "Tumpahan terdeteksi; menunggu konfirmasi frame berturut-turut."
            ),
            severity="warning",
        )

    return {
        "frame_id": frame_id,
        "captured_at": frame["captured_at"].isoformat(),
        "image_path": image_path,
        "has_spill": has_spill,
        "highest_spill_confidence": highest_confidence,
        "model_name": model_name,
        "model_version": model_version,
        "inference_ms": int(inference_ms),
        "processed": True,
        "spill_confirmed": spill_confirmed,
        "required_confirmation_frames": needed,
        "operation_mode": settings["operation_mode"],
        "detections": saved_detections,
        "automatic_command": None,
    }
