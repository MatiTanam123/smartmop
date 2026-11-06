"""Check PostgreSQL connectivity and required SmartMop tables."""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")
import os
import psycopg

url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:5432/smartmop_db")
required = {
    "devices", "device_heartbeats", "robot_settings", "notification_settings",
    "detections", "cleaning_sessions", "robot_commands", "activity_logs",
    "device_telemetry", "app_settings", "camera_frames",
}
try:
    with psycopg.connect(url, connect_timeout=5) as conn:
        rows = conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'"
        ).fetchall()
        found = {r[0] for r in rows}
        missing = sorted(required - found)
        print("PostgreSQL: CONNECTED")
        print(f"Tabel ditemukan: {len(found)}")
        if missing:
            print("Tabel yang belum ada:", ", ".join(missing))
            print("Jalankan backend/database/schema.sql di database smartmop_db.")
            raise SystemExit(1)
        print("Semua tabel SmartMop tersedia.")
except Exception as exc:
    print("Gagal menghubungkan database:", exc)
    raise SystemExit(1)
