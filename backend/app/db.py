from contextlib import contextmanager
from typing import Iterator, Optional

import psycopg2

from .config import get_settings


@contextmanager
def connection() -> Iterator:
    conn = psycopg2.connect(get_settings().database_url)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def credibility_for(domain: str) -> Optional[tuple[float, str]]:
    parts = domain.split(".")
    candidates = [domain]
    if len(parts) > 2:
        candidates.append(".".join(parts[-2:]))

    with connection() as conn, conn.cursor() as cur:
        for candidate in candidates:
            cur.execute(
                "SELECT credibility_score, category FROM sources WHERE domain = %s",
                (candidate,),
            )
            if row := cur.fetchone():
                return row[0], row[1]
    return None


def write_log(log: dict) -> None:
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO pipeline_logs
                (id, input_hash, timestamp, steps_completed, verdict, error_stage, error_message, response_time_ms)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
            """,
            (
                log["id"], log["input_hash"], log["timestamp"], log["steps_completed"],
                log["verdict"], log["error_stage"], log["error_message"], log["response_time_ms"],
            ),
        )
