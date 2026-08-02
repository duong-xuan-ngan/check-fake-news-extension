import os
from urllib.parse import urlparse, urlunparse

import psycopg2
from fastapi import FastAPI
from pydantic import BaseModel, Field

from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
import uuid

app = FastAPI()

QDRANT_HOST = os.getenv("QDRANT_HOST", "qdrant")
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.92"))
COLLECTION = "claim_cache"

def get_conn():
    return psycopg2.connect(os.environ["DATABASE_URL"])


def _root_domain(domain: str) -> str:
    """Best-effort registrable domain, including common country suffixes."""
    parts = domain.split(".")
    compound_suffixes = {
        "co.uk", "org.uk", "ac.uk",
        "com.au", "net.au", "org.au",
        "co.jp", "co.kr", "co.nz",
        "com.vn", "net.vn", "org.vn", "gov.vn", "edu.vn",
    }
    if len(parts) > 2 and ".".join(parts[-2:]) in compound_suffixes:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) > 2 else domain


def _normalize_domain(domain: str = "", url: str = "") -> str:
    """Return the lowercase hostname format used by the credibility tables."""
    # Prefer the URL itself so a caller cannot associate an arbitrary domain
    # with an unrelated sample URL.
    candidate = (urlparse(url).hostname or "").lower() if url else ""
    if not candidate:
        candidate = (domain or "").strip().lower()
    if ":" in candidate:
        candidate = candidate.split(":", 1)[0]
    return candidate.removeprefix("www.").rstrip(".")


def _sanitize_sample_url(url: str) -> str:
    """Drop query parameters and fragments before persistence."""
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


class SourceDiscovery(BaseModel):
    domain: str = Field(default="", max_length=253)
    url: str = Field(max_length=2048)


class CredibilityBatchRequest(BaseModel):
    sources: list[SourceDiscovery] = Field(default_factory=list, max_length=50)

def get_qdrant():
    return QdrantClient(host=QDRANT_HOST, port=6333)


@app.post("/cache/lookup")
def cache_lookup(payload: dict):
    """
    Input:  { "embedding": [0.1, 0.2, ...] }
    Output: cached AnalysisResult or {"hit": false}
    """
    embedding = payload.get("embedding")
    if not embedding:
        return {"hit": False}

    try:
        client = get_qdrant()
        results = client.search(
            collection_name=COLLECTION,
            query_vector=embedding,
            limit=1,
            score_threshold=SIMILARITY_THRESHOLD,
        )
        if results:
            return {"hit": True, "result": results[0].payload}
        return {"hit": False}
    except Exception as e:
        print(f"[qdrant] lookup failed: {e}")
        return {"hit": False}


@app.post("/cache/store")
def cache_store(payload: dict):
    """
    Input:  { "embedding": [...], "verdict": "...", "explanation": "...", "sources": [...] }
    Output: { "status": "ok" }
    """
    embedding = payload.get("embedding")
    if not embedding:
        return {"status": "error", "reason": "missing embedding"}

    try:
        client = get_qdrant()
        client.upsert(
            collection_name=COLLECTION,
            points=[PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding,
                payload={
                    "verdict":     payload.get("verdict"),
                    "explanation": payload.get("explanation"),
                    "sources":     payload.get("sources"),
                    "cached":      True,
                }
            )]
        )
        return {"status": "ok"}
    except Exception as e:
        print(f"[qdrant] store failed: {e}")
        return {"status": "error", "reason": str(e)}


@app.get("/credibility")
def get_credibility(domain: str):
    conn = get_conn()
    cur = conn.cursor()
    domain = _normalize_domain(domain)

    # Try exact match, then root domain
    for lookup in [domain, _root_domain(domain)]:
        cur.execute(
            """
            SELECT credibility_score, category, rating_source,
                   source_count, source_version
            FROM sources
            WHERE domain = %s
            """,
            (lookup,)
        )
        row = cur.fetchone()
        if row:
            cur.close()
            conn.close()
            return {
                "credibility_score": row[0],
                "category": row[1],
                "rating_status": "rated",
                "rating_source": row[2],
                "source_count": row[3],
                "source_version": row[4],
            }

    cur.close()
    conn.close()
    # Not found — null preserves the distinction between neutral and unrated.
    return {
        "credibility_score": None,
        "category": "unknown",
        "rating_status": "unrated",
    }


@app.post("/credibility/batch")
def get_credibility_batch(payload: CredibilityBatchRequest):
    """Rate known domains and atomically queue newly discovered domains.

    Unknown is intentionally represented by a null score. A neutral numeric
    score would make an unrated source look as if it had been reviewed.
    """
    normalized = []
    seen = set()
    for item in payload.sources:
        domain = _normalize_domain(item.domain, item.url)
        if not domain or domain in seen:
            continue
        seen.add(domain)
        normalized.append((domain, _sanitize_sample_url(item.url)))

    if not normalized:
        return {"results": []}

    conn = get_conn()
    cur = conn.cursor()
    try:
        domains = {
            lookup
            for domain, _ in normalized
            for lookup in (domain, _root_domain(domain))
        }
        cur.execute(
            """
            SELECT domain, credibility_score, category, rating_source,
                   source_count, source_version
            FROM sources
            WHERE domain = ANY(%s)
            """,
            (list(domains),),
        )
        rated = {
            row[0]: {
                "credibility_score": row[1],
                "category": row[2],
                "rating_source": row[3],
                "source_count": row[4],
                "source_version": row[5],
            }
            for row in cur.fetchall()
        }

        def rating_for(domain):
            return rated.get(domain) or rated.get(_root_domain(domain))

        unknown = [
            (domain, url) for domain, url in normalized if rating_for(domain) is None
        ]
        if unknown:
            cur.executemany(
                """
                INSERT INTO source_candidates (domain, sample_url)
                VALUES (%s, %s)
                ON CONFLICT (domain) DO UPDATE SET
                    sample_url = EXCLUDED.sample_url,
                    last_seen_at = NOW(),
                    discovery_count = source_candidates.discovery_count + 1
                """,
                unknown,
            )

        conn.commit()
        return {
            "results": [
                {
                    "domain": domain,
                    "credibility_score": (rating_for(domain) or {}).get("credibility_score"),
                    "category": (rating_for(domain) or {}).get("category", "unknown"),
                    "rating_status": "rated" if rating_for(domain) else "unrated",
                    "rating_source": (rating_for(domain) or {}).get("rating_source"),
                    "source_count": (rating_for(domain) or {}).get("source_count"),
                    "source_version": (rating_for(domain) or {}).get("source_version"),
                }
                for domain, _ in normalized
            ]
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


@app.post("/logs")
def write_log(log: dict):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO pipeline_logs
            (id, input_hash, timestamp, steps_completed,
             verdict, error_stage, error_message, response_time_ms)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING
    """, (
        log.get("id"),
        log.get("input_hash"),
        log.get("timestamp"),
        log.get("steps_completed"),
        log.get("verdict"),
        log.get("error_stage"),
        log.get("error_message"),
        log.get("response_time_ms"),
    ))
    conn.commit()
    cur.close()
    conn.close()
    return {"status": "ok"}


@app.get("/health")
def health():
    return {"status": "ok"}
