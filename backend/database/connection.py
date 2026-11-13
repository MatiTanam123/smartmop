"""PostgreSQL connection factory (Supabase compatible)."""
from __future__ import annotations

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env", override=False)


def get_db_connection() -> psycopg.Connection:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL belum dikonfigurasi.")

    try:
        timeout = int(os.getenv("DB_CONNECT_TIMEOUT", "10"))
    except ValueError:
        timeout = 10

    return psycopg.connect(
        database_url,
        row_factory=dict_row,
        connect_timeout=max(3, min(timeout, 60)),
        application_name="smartmop-flask-api",
    )
