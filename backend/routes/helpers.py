"""Common API response, JSON body and serialization helpers."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from flask import jsonify, request


def serialize(value):
    if isinstance(value, dict):
        return {key: serialize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [serialize(item) for item in value]
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def json_body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None, (jsonify({
            "success": False,
            "message": "Body request harus berupa JSON object.",
        }), 400)
    return data, None


def error_response(message: str, status: int = 400):
    return jsonify({"success": False, "message": message}), status


def success_response(data=None, message: str = "Berhasil", status: int = 200):
    payload = {"success": True, "message": message}
    if data is not None:
        payload["data"] = serialize(data)
    return jsonify(payload), status
