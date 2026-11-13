"""API-key guards for device and administrative write endpoints."""
from __future__ import annotations

import hmac
from functools import wraps
from typing import Callable, TypeVar, cast

from flask import current_app, jsonify, request

F = TypeVar("F", bound=Callable)


def _check_key(expected: str, supplied: str) -> bool:
    return bool(expected and supplied) and hmac.compare_digest(expected, supplied)


def require_device_key(fn: F) -> F:
    @wraps(fn)
    def wrapper(*args, **kwargs):
        expected = current_app.config.get("DEVICE_API_KEY", "")
        if not expected:
            return jsonify({
                "success": False,
                "message": "DEVICE_API_KEY belum dikonfigurasi pada server.",
            }), 503
        supplied = request.headers.get("X-Device-Key", "")
        if not _check_key(expected, supplied):
            return jsonify({"success": False, "message": "Autentikasi perangkat gagal."}), 401
        return fn(*args, **kwargs)

    return cast(F, wrapper)


def require_admin_key(fn: F) -> F:
    """Protect control/settings writes until a proper user-login flow exists."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        expected = current_app.config.get("ADMIN_API_KEY", "")
        if not expected:
            return jsonify({
                "success": False,
                "message": "ADMIN_API_KEY belum dikonfigurasi. Endpoint tulis dikunci demi keamanan.",
            }), 503
        supplied = request.headers.get("X-Admin-Key", "")
        if not _check_key(expected, supplied):
            return jsonify({"success": False, "message": "Autentikasi administrator gagal."}), 401
        return fn(*args, **kwargs)

    return cast(F, wrapper)
