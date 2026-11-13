"""Ultralytics YOLO inference adapter for SMARTMOP camera frames."""
from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import Any

from PIL import Image

from ml.preprocess import InvalidImageError, open_valid_image


class ModelUnavailableError(RuntimeError):
    """Raised when trained weights or the inference runtime are unavailable."""


class SpillDetector:
    def __init__(
        self,
        model_path: str | Path,
        *,
        image_size: int = 640,
        model_name: str = "YOLO26",
        model_version: str = "custom-liquid-spill-v1",
        device: str = "cpu",
        max_image_pixels: int = 12_000_000,
    ) -> None:
        self.model_path = Path(model_path).expanduser().resolve()
        self.image_size = int(image_size)
        self.model_name = model_name
        self.model_version = model_version
        self.device = device
        self.max_image_pixels = int(max_image_pixels)
        self.model = None
        self.load_error: str | None = None
        self._load_model()

    @property
    def available(self) -> bool:
        return self.model is not None

    def _load_model(self) -> None:
        if not self.model_path.is_file():
            self.load_error = f"Bobot YOLO tidak ditemukan: {self.model_path}"
            return
        if self.model_path.stat().st_size <= 0:
            self.load_error = f"File bobot YOLO kosong: {self.model_path}"
            return
        try:
            from ultralytics import YOLO
            self.model = YOLO(str(self.model_path))
            self.load_error = None
        except Exception as exc:
            self.model = None
            self.load_error = f"Gagal memuat model YOLO: {type(exc).__name__}: {exc}"

    def predict(self, image_bytes: bytes, confidence: float = 0.10) -> dict[str, Any]:
        image, image_format, width, height = open_valid_image(
            image_bytes,
            max_pixels=self.max_image_pixels,
        )
        if not self.available:
            raise ModelUnavailableError(self.load_error or "Model YOLO belum siap.")
        return self._predict_image(image, image_format, width, height, confidence)

    def _predict_image(
        self,
        image: Image.Image,
        image_format: str,
        width: int,
        height: int,
        confidence: float,
    ) -> dict[str, Any]:
        if not 0.01 <= float(confidence) <= 0.99:
            raise ValueError("ML_CONFIDENCE harus berada pada rentang 0.01 sampai 0.99.")

        start = perf_counter()
        results = self.model.predict(
            source=image,
            imgsz=self.image_size,
            conf=float(confidence),
            device=self.device,
            verbose=False,
        )
        inference_ms = max(0, int((perf_counter() - start) * 1000))

        detections: list[dict[str, Any]] = []
        for result in results or []:
            names = result.names or {}
            boxes = result.boxes
            if boxes is None:
                continue
            for box in boxes:
                class_id = int(box.cls.item())
                class_name = str(names[class_id] if isinstance(names, (list, tuple)) and class_id < len(names) else names.get(class_id, class_id) if isinstance(names, dict) else class_id)
                score = float(box.conf.item())
                # xyxyn = normalized top-left and bottom-right coordinates.
                x1, y1, x2, y2 = [float(v) for v in box.xyxyn[0].tolist()]
                x1 = min(1.0, max(0.0, x1))
                y1 = min(1.0, max(0.0, y1))
                x2 = min(1.0, max(0.0, x2))
                y2 = min(1.0, max(0.0, y2))
                box_width = max(0.0, x2 - x1)
                box_height = max(0.0, y2 - y1)
                if box_width <= 0 or box_height <= 0:
                    continue
                detections.append({
                    "class_name": class_name,
                    "confidence": score,
                    "bbox": {
                        "x": round(x1, 6),
                        "y": round(y1, 6),
                        "width": round(box_width, 6),
                        "height": round(box_height, 6),
                    },
                })

        return {
            "available": True,
            "detections": detections,
            "inference_ms": inference_ms,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "image_format": image_format,
            "image_width": width,
            "image_height": height,
        }
