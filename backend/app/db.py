from contextlib import contextmanager
from datetime import date, datetime
from typing import Iterator, Optional
import uuid

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
                (id, input_hash, timestamp, steps_completed, verdict, error_stage, error_message, response_time_ms, user_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
            """,
            (
                log["id"], log["input_hash"], log["timestamp"], log["steps_completed"],
                log["verdict"], log["error_stage"], log["error_message"], log["response_time_ms"],
                log.get("user_id"),
            ),
        )


def upsert_user(google_sub: str, email: Optional[str], name: Optional[str], picture: Optional[str] = None) -> str:
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO users (id, google_sub, email, name, picture)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (google_sub) DO UPDATE
                SET email = EXCLUDED.email, name = EXCLUDED.name, picture = EXCLUDED.picture
            RETURNING id
            """,
            (str(uuid.uuid4()), google_sub, email, name, picture),
        )
        row = cur.fetchone()
        return row[0]


def user_for_id(user_id: str) -> Optional[dict]:
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, google_sub, email, name, picture FROM users WHERE id = %s",
            (user_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return {"id": row[0], "google_sub": row[1], "email": row[2], "name": row[3], "picture": row[4]}


def consume_daily_check(user_id: str, check_date: date, limit: int) -> Optional[int]:
    """Atomically increment today's counter unless the limit is already reached.

    Returns the new checks_used count, or None if the limit was hit.
    """
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO usage (user_id, check_date, checks_used)
            VALUES (%s, %s, 1)
            ON CONFLICT (user_id, check_date)
            DO UPDATE SET checks_used = usage.checks_used + 1
            WHERE usage.checks_used < %s
            RETURNING checks_used
            """,
            (user_id, check_date, limit),
        )
        row = cur.fetchone()
        return row[0] if row else None


def usage_for(user_id: str, check_date: date) -> int:
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT checks_used FROM usage WHERE user_id = %s AND check_date = %s",
            (user_id, check_date),
        )
        row = cur.fetchone()
        return row[0] if row else 0


def store_refresh_token(token_hash: str, user_id: str, expires_at: datetime) -> None:
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO refresh_tokens (id, user_id, token_hash, expires_at)
            VALUES (%s, %s, %s, %s)
            """,
            (str(uuid.uuid4()), user_id, token_hash, expires_at),
        )


def get_refresh_token(token_hash: str) -> Optional[dict]:
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT user_id, expires_at, revoked_at
            FROM refresh_tokens WHERE token_hash = %s
            """,
            (token_hash,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return {"user_id": row[0], "expires_at": row[1], "revoked_at": row[2]}


def revoke_refresh_token(token_hash: str) -> None:
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE refresh_tokens SET revoked_at = now() WHERE token_hash = %s",
            (token_hash,),
        )
