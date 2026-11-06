"""Optional Ultralytics YOLO inference adapter.

The repository does not include trained weights. Copy your trained model to
backend/ml/models/best.pt or set ML_MODEL_PATH in .env. Without weights the
API accepts uploaded images but does not invent detection results.
"""
from __future__ import annotations
from pathlib import Path
from time import perf_counter
from typing import Any

from .preprocess import validate_image_path


class SpillDetector:
    def __init__(self, model_path: str | Path, image_size: int = 640):
        self.model_path = Path(model_path)
        self.image_size = image_size
        self.model = None
        self.load_error: str | None = None
        self._try_load()

    @property
    def available(self) -> bool:
        return self.model is not None

    def _try_load(self) -> None:
        if not self.model_path.exists() or self.model_path.stat().st_size == 0:
            self.load_error = f"Bobot model belum tersedia: {self.model_path}"
            return
        try:
            from ultralytics import YOLO  # Optional dependency
            self.model = YOLO(str(self.model_path))
            self.load_error = None
        except Exception as exc:  # Keep API alive even if ML stack is not installed.
            self.load_error = f"Model gagal dimuat: {exc}"
            self.model = None

    def predict(self, image_path: str | Path, confidence: float = 0.65, image_size: int | None = None) -> dict[str, Any]:
        if not self.available:
            return {"available": False, "error": self.load_error, "detections": [], "inference_ms": None}
        path = validate_image_path(image_path)
        start = perf_counter()
        results = self.model.predict(
            source=str(path),
            imgsz=int(image_size or self.image_size),
            conf=float(confidence),
            verbose=False,
        )
        elapsed_ms = int((perf_counter() - start) * 1000)
        detections: list[dict[str, Any]] = []
        for result in results:
            names = result.names or {}
            boxes = result.boxes
            if boxes is None:
                continue
            for box in boxes:
                cls_id = int(box.cls.item())
                name = str(names.get(cls_id, cls_id))
                conf = float(box.conf.item())
                xywhn = box.xywhn[0].tolist()
                detections.append({
                    "class_name": name,
                    "confidence": conf,
                    "bbox": {
                        "x": float(xywhn[0]),
                        "y": float(xywhn[1]),
                        "width": float(xywhn[2]),
                        "height": float(xywhn[3]),
                    },
                })
        return {
            "available": True,
            "detections": detections,
            "inference_ms": elapsed_ms,
            "model_name": "YOLO",
            "model_version": getattr(self.model, "task", None),
        }
