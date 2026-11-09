
import os
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv

# Lokasi folder backend
BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

# Membaca .env dari folder backend
ENV_PATH = os.path.join(BASE_DIR, ".env")
load_dotenv(ENV_PATH)


def get_db_connection():
    DATABASE_URL = os.getenv("DATABASE_URL")

    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL tidak ditemukan. Periksa file .env"
        )

    connection = psycopg.connect(
        DATABASE_URL,
        row_factory=dict_row,
        connect_timeout=10
    )

    return connection
