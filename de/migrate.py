"""Apply idempotent PostgreSQL schema changes before seeding the DE service."""
import os
from pathlib import Path

import psycopg2


schema_path = Path(__file__).resolve().parent / "init.sql"
schema_sql = schema_path.read_text(encoding="utf-8")

conn = psycopg2.connect(os.environ["DATABASE_URL"])
try:
    with conn.cursor() as cur:
        cur.execute(schema_sql)
    conn.commit()
    print("[migrate] Database schema is up to date.")
except Exception:
    conn.rollback()
    raise
finally:
    conn.close()
