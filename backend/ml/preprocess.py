"""Safe image validation helpers for ESP32-CAM uploads."""
from __future__ import annotations

from io import BytesIO

from PIL import Image, UnidentifiedImageError


class InvalidImageError(ValueError):
    """Raised when an upload is not a supported, valid image."""


def open_valid_image(image_bytes: bytes, max_pixels: int):
    if not image_bytes:
        raise InvalidImageError("File gambar kosong.")

    try:
        with Image.open(BytesIO(image_bytes)) as probe:
            image_format = (probe.format or "").lower()
            width, height = probe.size
            if image_format not in {"jpeg", "png", "webp"}:
                raise InvalidImageError("Format gambar harus JPEG, PNG, atau WEBP.")
            if width <= 0 or height <= 0 or width * height > max_pixels:
                raise InvalidImageError("Resolusi gambar tidak valid atau melebihi batas.")
            probe.verify()

        with Image.open(BytesIO(image_bytes)) as reopened:
            image = reopened.convert("RGB")
            image.load()

        return image, image_format, width, height
    except InvalidImageError:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise InvalidImageError("Isi file bukan gambar yang valid atau gambar rusak.") from exc
