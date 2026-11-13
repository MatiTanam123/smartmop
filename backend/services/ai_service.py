"""Bridge between Flask routes and the app-scoped YOLO model."""
from __future__ import annotations

from flask import current_app

from ml.inference import ModelUnavailableError
from ml.preprocess import InvalidImageError


def predict_image(image_bytes: bytes) -> dict:
    detector = current_app.extensions.get("smartmop_detector")
    if detector is None:
        raise ModelUnavailableError("Komponen inferensi YOLO belum diinisialisasi.")
    if not detector.available:
        raise ModelUnavailableError(detector.load_error or "Model YOLO belum tersedia.")
    return detector.predict(image_bytes, confidence=current_app.config["ML_CONFIDENCE"])


__all__ = ["InvalidImageError", "ModelUnavailableError", "predict_image"]
