"""Read-only detection history endpoints."""
from urllib.parse import urlparse

from flask import Blueprint, request, url_for

from database.connection import get_db_connection
from routes.helpers import success_response

detection_bp = Blueprint("detections", __name__)


@detection_bp.get("/detections")
def list_detections():
    limit = request.args.get("limit", default=50, type=int) or 50
    limit = max(1, min(limit, 200))
    with get_db_connection() as conn:
        rows = conn.execute(
            """SELECT d.detection_id, d.camera_device_id, d.frame_id,
                      d.detected_at, d.class_name, d.confidence,
                      d.bbox_x, d.bbox_y, d.bbox_width, d.bbox_height,
                      d.image_path, d.model_name, d.model_version,
                      d.inference_ms, d.decision_status,
                      cf.image_path AS frame_image_path
               FROM detections d
               LEFT JOIN camera_frames cf ON cf.frame_id = d.frame_id
               ORDER BY d.detected_at DESC, d.detection_id DESC
               LIMIT %s""",
            (limit,),
        ).fetchall()

    # Return usable URLs while retaining the DB path for diagnostics.
    result = []
    for source in rows:
        row = dict(source)
        image_path = row.get("frame_image_path") or row.get("image_path")
        if image_path:
            parsed = urlparse(str(image_path))
            if parsed.scheme in {"http", "https"}:
                row["image_url"] = str(image_path)
            elif row.get("frame_id") is not None:
                row["image_url"] = url_for(
                    "camera.get_frame_image",
                    frame_id=int(row["frame_id"]),
                    _external=True,
                )
            else:
                row["image_url"] = None
        else:
            row["image_url"] = None
        row.pop("frame_image_path", None)
        result.append(row)

    return success_response(result)
