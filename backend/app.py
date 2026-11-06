"""Flask application factory for SmartMop."""
from __future__ import annotations
from pathlib import Path

from flask import Flask, jsonify, send_from_directory, request

from .config import Config
from .routes.api import api
from .ml.inference import SpillDetector


def create_app(config_object=Config) -> Flask:
    project_root = Path(__file__).resolve().parents[1]
    app = Flask(__name__)
    app.config.from_object(config_object)
    app.config["FRONTEND_DIR"] = project_root / "frontend"
    app.config["CAPTURE_DIR"] = project_root / "backend" / "storage" / "captures"
    app.config["CAPTURE_DIR"].mkdir(parents=True, exist_ok=True)

    app.extensions["spill_detector"] = SpillDetector(
        app.config["ML_MODEL_PATH"], app.config["ML_IMAGE_SIZE"]
    )
    app.register_blueprint(api)

    @app.after_request
    def add_cors_headers(response):
        origins = app.config.get("CORS_ORIGINS", "*")
        origin = request.headers.get("Origin")
        if origins == "*":
            response.headers["Access-Control-Allow-Origin"] = "*"
        elif origin and origin in [x.strip() for x in origins.split(",")]:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers.add("Vary", "Origin")
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Device-Key"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    @app.errorhandler(413)
    def file_too_large(_error):
        return jsonify({"ok": False, "error": "Ukuran gambar melebihi batas MAX_UPLOAD_MB."}), 413

    @app.errorhandler(404)
    def not_found(_error):
        if request.path.startswith("/api/"):
            return jsonify({"ok": False, "error": "Endpoint API tidak ditemukan."}), 404
        return jsonify({"ok": False, "error": "Halaman atau file tidak ditemukan."}), 404

    @app.errorhandler(500)
    def internal_error(_error):
        app.logger.exception("Unhandled SmartMop backend error")
        return jsonify({"ok": False, "error": "Terjadi kesalahan internal pada backend. Periksa terminal server."}), 500

    @app.get("/")
    def home():
        return send_from_directory(app.config["FRONTEND_DIR"], "index.html")

    @app.get("/<path:asset_path>")
    def frontend_files(asset_path: str):
        # API endpoints are registered above; this catch-all only serves files.
        return send_from_directory(app.config["FRONTEND_DIR"], asset_path)

    return app
