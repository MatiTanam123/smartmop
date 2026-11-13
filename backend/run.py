"""Local development runner. Production uses Gunicorn: app:app."""
import os

from app import app

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000")),
        debug=app.config["DEBUG"],
        threaded=True,
    )
