import os
from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

from routes.device_routes import device_bp
from routes.detection_routes import detection_bp
from routes.cleaning_routes import cleaning_bp
from routes.command_routes import command_bp
from routes.settings_routes import settings_bp
from routes.dashboard_routes import dashboard_bp
from routes.log_routes import log_bp

def create_app():
    load_dotenv()

    app = Flask(__name__)
    app.config["DEBUG"] = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB
    CORS(app)  # Batasi origins saat deploy, jangan biarkan terbuka tanpa kebutuhan.

    @app.get("/api/health")
    def health():
        return jsonify({
            "success": True,
            "message": "SmartMop API is running"
        }), 200

    app.register_blueprint(device_bp, url_prefix="/api")
    app.register_blueprint(detection_bp, url_prefix="/api")
    app.register_blueprint(cleaning_bp, url_prefix="/api")
    app.register_blueprint(command_bp, url_prefix="/api")
    app.register_blueprint(settings_bp, url_prefix="/api")
    app.register_blueprint(dashboard_bp, url_prefix="/api")
    app.register_blueprint(log_bp, url_prefix="/api")

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify({"success": False, "message": "Endpoint tidak ditemukan"}), 404

    @app.errorhandler(413)
    def file_too_large(_error):
        return jsonify({"success": False, "message": "Ukuran request terlalu besar"}), 413

    return app
