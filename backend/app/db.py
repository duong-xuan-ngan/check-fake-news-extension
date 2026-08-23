from contextlib import contextmanager
from datetime import date, datetime
from typing import Iterator, Optional
from urllib.parse import urlsplit, urlunsplit
import uuid

import psycopg2
from psycopg2.extras import execute_values

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


def _normalize_domain(value: str) -> str:
    candidate = str(value or "").strip().lower()
    parsed = urlsplit(candidate if "://" in candidate else f"//{candidate}")
    return (parsed.hostname or "").removeprefix("www.").rstrip(".")


def _lookup_candidates(domain: str) -> list[str]:
    normalized = _normalize_domain(domain)
    if not normalized:
        return []
    parts = normalized.split(".")
    return [normalized, ".".join(parts[-2:])] if len(parts) > 2 else [normalized]


def _sanitize_sample_url(url: str) -> Optional[str]:
    try:
        parsed = urlsplit(str(url or ""))
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return None
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
    except ValueError:
        return None


def credibility_for_many(sources: list[dict[str, str]]) -> dict[str, Optional[tuple[float, str]]]:
    """Batch-rate sources and queue unknown domains for human review.

    The returned keys are normalized domains. Unknown means unrated; it is not
    an assertion that the source is credible or non-credible.
    """
    normalized_sources: list[tuple[str, Optional[str]]] = []
    all_candidates: set[str] = set()
    for source in sources:
        domain = _normalize_domain(source.get("domain", ""))
        if not domain:
            continue
        normalized_sources.append((domain, _sanitize_sample_url(source.get("url", ""))))
        all_candidates.update(_lookup_candidates(domain))

    if not normalized_sources:
        return {}

    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT domain, credibility_score, category FROM sources WHERE domain = ANY(%s)",
            (list(all_candidates),),
        )
        known = {row[0]: (row[1], row[2]) for row in cur.fetchall()}

        ratings: dict[str, Optional[tuple[float, str]]] = {}
        unknown_rows = []
        for domain, sample_url in normalized_sources:
            rating = next(
                (known[candidate] for candidate in _lookup_candidates(domain) if candidate in known),
                None,
            )
            ratings[domain] = rating
            if rating is None:
                unknown_rows.append((domain, sample_url))

        if unknown_rows:
            execute_values(cur, """
                INSERT INTO source_candidates (domain, sample_url)
                VALUES %s
                ON CONFLICT (domain) DO UPDATE SET
                    sample_url = COALESCE(EXCLUDED.sample_url, source_candidates.sample_url),
                    last_seen_at = now(),
                    discovery_count = source_candidates.discovery_count + 1
            """, unknown_rows)

    return ratings


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
