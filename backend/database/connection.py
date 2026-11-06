"""Small psycopg 3 connection helper."""
from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg.rows import dict_row
from flask import current_app


@contextmanager
def get_db() -> Iterator[psycopg.Connection]:
    """Open one short-lived database connection for a request/service call."""
    conn = psycopg.connect(
        current_app.config["DATABASE_URL"],
        row_factory=dict_row,
        connect_timeout=5,
    )
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def ping_database() -> bool:
    with get_db() as conn:
        conn.execute("SELECT 1")
    return True
