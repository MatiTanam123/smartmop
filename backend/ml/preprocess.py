"""Image validation helpers used before model inference."""
from pathlib import Path

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def validate_image_path(path: str | Path) -> Path:
    p = Path(path)
    if p.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise ValueError("Format gambar yang didukung: JPG, JPEG, PNG, WEBP.")
    if not p.exists() or not p.is_file():
        raise FileNotFoundError("File gambar tidak ditemukan.")
    if p.stat().st_size <= 0:
        raise ValueError("File gambar kosong.")
    return p
