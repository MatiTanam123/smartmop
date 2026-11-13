"""One-off database connection check. Run from any working directory."""
from __future__ import annotations

from database.connection import get_db_connection

try:
    with get_db_connection() as conn:
        result = conn.execute("SELECT current_database() AS database_name, NOW() AS server_time").fetchone()
    print("BERHASIL TERHUBUNG KE DATABASE SMARTMOP")
    print(f"Database : {result['database_name']}")
    print(f"Server   : {result['server_time']}")
except Exception as exc:
    print("GAGAL TERHUBUNG KE DATABASE:")
    print(f"{type(exc).__name__}: {exc}")
    raise SystemExit(1)
