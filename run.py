"""Run the SmartMop backend on the local network."""
from backend.app import create_app
from backend.config import Config

app = create_app()

if __name__ == "__main__":
    print("SmartMop backend starting...")
    print(f"Dashboard : http://127.0.0.1:{Config.PORT}/")
    print(f"API health: http://127.0.0.1:{Config.PORT}/api/health")
    print("Untuk akses dari HP, gunakan IP lokal komputer pada Wi-Fi yang sama.")
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG, threaded=True)
