"""SMARTMOP Flask API application factory."""
from __future__ import annotations

import logging
from pathlib import Path

from flask import Flask, jsonify
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix

from config import Config
from database.connection import get_db_connection
from ml.inference import SpillDetector
from routes.camera_routes import camera_bp
from routes.cleaning_routes import cleaning_bp
from routes.command_routes import command_bp
from routes.dashboard_routes import dashboard_bp
from routes.detection_routes import detection_bp
from routes.device_routes import device_bp
from routes.log_routes import log_bp
from routes.settings_routes import settings_bp


def create_app(test_config: dict | None = None) -> Flask:
    Config.validate_for_production()

    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    app.config["MAX_CONTENT_LENGTH"] = app.config["MAX_CONTENT_LENGTH"]
    Path(app.config["MEDIA_ROOT"]).mkdir(parents=True, exist_ok=True)

    # Railway is a reverse proxy; trust one proxy hop for the public scheme/host.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

    origins = app.config.get("CORS_ORIGINS", [])
    if origins:
        CORS(
            app,
            resources={r"/api/*": {"origins": origins}},
            allow_headers=["Content-Type", "X-Device-Key", "X-Admin-Key"],
            methods=["GET", "POST", "PUT", "OPTIONS"],
            expose_headers=["Content-Disposition"],
            supports_credentials=False,
        )
    elif app.config.get("APP_ENV") != "production":
        CORS(app, resources={r"/api/*": {"origins": "*"}})
    else:
        app.logger.warning("CORS_ORIGINS kosong; browser lintas-origin tidak akan diizinkan.")

    # Model absence must not prevent health checks/API startup. Upload will return 503.
    detector = SpillDetector(
        app.config["ML_MODEL_PATH"],
        image_size=app.config["ML_IMAGE_SIZE"],
        model_name=app.config["ML_MODEL_NAME"],
        model_version=app.config["ML_MODEL_VERSION"],
        device=app.config["ML_DEVICE"],
        max_image_pixels=app.config["ML_MAX_IMAGE_PIXELS"],
    )
    app.extensions["smartmop_detector"] = detector
    if detector.available:
        app.logger.info("YOLO model loaded: %s", app.config["ML_MODEL_PATH"])
    else:
        app.logger.warning("YOLO belum siap: %s", detector.load_error)

    @app.get("/")
    def root():
        return jsonify({
            "success": True,
            "service": "SMARTMOP API",
            "message": "Backend SMARTMOP aktif.",
            "health": "/api/health",
        }), 200

    @app.get("/api/health")
    def health():
        return jsonify({
            "success": True,
            "service": "SMARTMOP API",
            "status": "running",
            "model_available": detector.available,
            "model_error": None if detector.available else detector.load_error,
        }), 200

    @app.get("/api/health/database")
    def health_database():
        try:
            with get_db_connection() as conn:
                conn.execute("SELECT 1").fetchone()
            return jsonify({"success": True, "database": "connected"}), 200
        except Exception:
            app.logger.exception("Database health check failed")
            return jsonify({"success": False, "database": "unavailable"}), 503

    @app.get("/api/health/model")
    def health_model():
        if not detector.available:
            return jsonify({
                "success": False,
                "model_available": False,
                "message": detector.load_error,
            }), 503
        return jsonify({
            "success": True,
            "model_available": True,
            "model_name": app.config["ML_MODEL_NAME"],
            "model_version": app.config["ML_MODEL_VERSION"],
        }), 200

    # Route prefixes are defined by this app. camera_bp owns /api/camera itself.
    app.register_blueprint(device_bp, url_prefix="/api")
    app.register_blueprint(detection_bp, url_prefix="/api")
    app.register_blueprint(cleaning_bp, url_prefix="/api")
    app.register_blueprint(command_bp, url_prefix="/api")
    app.register_blueprint(settings_bp, url_prefix="/api")
    app.register_blueprint(dashboard_bp, url_prefix="/api")
    app.register_blueprint(log_bp, url_prefix="/api")
    app.register_blueprint(camera_bp)

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify({"success": False, "message": "Endpoint tidak ditemukan."}), 404

    @app.errorhandler(413)
    def file_too_large(_error):
        return jsonify({"success": False, "message": "Ukuran request melebihi batas upload."}), 413

    @app.errorhandler(500)
    def internal_error(_error):
        app.logger.exception("Unhandled SMARTMOP API error")
        return jsonify({"success": False, "message": "Terjadi kesalahan internal server."}), 500

    return app


app = create_app()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app.run(
        host="0.0.0.0",
        port=int(__import__("os").getenv("PORT", "5000")),
        debug=app.config["DEBUG"],
    )
