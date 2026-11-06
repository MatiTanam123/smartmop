"""Configuration for the SmartMop Flask backend."""
from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


def _bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "change-this-local-development-secret")
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@127.0.0.1:5432/smartmop_db",
    )
    HOST = os.getenv("FLASK_HOST", "0.0.0.0")
    PORT = int(os.getenv("FLASK_PORT", "5000"))
    DEBUG = _bool("FLASK_DEBUG", True)
    DEVICE_API_KEY = os.getenv("DEVICE_API_KEY", "")
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_UPLOAD_MB", "8")) * 1024 * 1024
    CAPTURE_DIR = PROJECT_ROOT / "backend" / "storage" / "captures"
    FRONTEND_DIR = PROJECT_ROOT / "frontend"
    _model_path = Path(os.getenv(
        "ML_MODEL_PATH",
        str(PROJECT_ROOT / "backend" / "ml" / "models" / "best.pt"),
    ))
    ML_MODEL_PATH = _model_path if _model_path.is_absolute() else PROJECT_ROOT / _model_path
    ML_IMAGE_SIZE = int(os.getenv("ML_IMAGE_SIZE", "640"))
    DEVICE_ONLINE_SECONDS = int(os.getenv("DEVICE_ONLINE_SECONDS", "60"))
    TIMEZONE = os.getenv("APP_TIMEZONE", "Asia/Pontianak")
