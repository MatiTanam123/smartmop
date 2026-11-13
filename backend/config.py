"""Central application configuration for SMARTMOP Flask backend."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=False)


def _as_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"Environment variable {name} harus berupa integer.") from exc
    if not minimum <= value <= maximum:
        raise RuntimeError(f"Environment variable {name} harus di antara {minimum} dan {maximum}.")
    return value


def _as_float(name: str, default: float, minimum: float, maximum: float) -> float:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = float(raw)
    except ValueError as exc:
        raise RuntimeError(f"Environment variable {name} harus berupa angka.") from exc
    if not minimum <= value <= maximum:
        raise RuntimeError(f"Environment variable {name} harus di antara {minimum} dan {maximum}.")
    return value


def _resolve_path(raw: str, fallback: Path) -> Path:
    value = Path(raw).expanduser() if raw else fallback
    if not value.is_absolute():
        value = BASE_DIR / value
    return value.resolve()


class Config:
    APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
    DEBUG = _as_bool("FLASK_DEBUG", False) and APP_ENV != "production"
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "").strip()

    DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
    DB_CONNECT_TIMEOUT = _as_int("DB_CONNECT_TIMEOUT", 10, 3, 60)

    DEVICE_API_KEY = os.getenv("DEVICE_API_KEY", "").strip()
    # Admin key is for protected write APIs called from trusted tooling only.
    # Do not place this key in frontend JavaScript.
    ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "").strip()

    CORS_ORIGINS = [
        item.strip() for item in os.getenv("CORS_ORIGINS", "").split(",") if item.strip()
    ]

    MAX_UPLOAD_MB = _as_int("MAX_UPLOAD_MB", 8, 1, 20)
    MAX_IMAGE_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
    MAX_CONTENT_LENGTH = MAX_IMAGE_UPLOAD_BYTES + (256 * 1024)

    MEDIA_ROOT = _resolve_path(os.getenv("MEDIA_ROOT", "storage"), BASE_DIR / "storage")
    ML_MODEL_PATH = _resolve_path(
        os.getenv("ML_MODEL_PATH", "ml/models/best.pt"),
        BASE_DIR / "ml" / "models" / "best.pt",
    )
    ML_MODEL_NAME = os.getenv("ML_MODEL_NAME", "YOLO26").strip() or "YOLO26"
    ML_MODEL_VERSION = os.getenv("ML_MODEL_VERSION", "custom-liquid-spill-v1").strip()
    ML_IMAGE_SIZE = _as_int("ML_IMAGE_SIZE", 640, 320, 1280)
    ML_CONFIDENCE = _as_float("ML_CONFIDENCE", 0.10, 0.01, 0.99)
    ML_DEVICE = os.getenv("ML_DEVICE", "cpu").strip() or "cpu"
    ML_MAX_IMAGE_PIXELS = _as_int("ML_MAX_IMAGE_PIXELS", 12000000, 100000, 40000000)

    CAMERA_DEVICE_CODE = os.getenv("CAMERA_DEVICE_CODE", "ESP32_CAM_01").strip()
    CONTROLLER_DEVICE_CODE = os.getenv("CONTROLLER_DEVICE_CODE", "ESP32_MAIN_01").strip()

    @classmethod
    def validate_for_production(cls) -> None:
        if cls.APP_ENV == "production":
            if not cls.DATABASE_URL:
                raise RuntimeError("DATABASE_URL wajib diisi pada APP_ENV=production.")
            if not cls.DEVICE_API_KEY:
                raise RuntimeError("DEVICE_API_KEY wajib diisi pada APP_ENV=production.")
            if not cls.SECRET_KEY or len(cls.SECRET_KEY) < 32:
                raise RuntimeError("FLASK_SECRET_KEY wajib berupa secret acak minimal 32 karakter.")
