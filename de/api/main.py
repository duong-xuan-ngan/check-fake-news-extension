import os
from datetime import date

import psycopg2
from fastapi import FastAPI

from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, Filter
import uuid

app = FastAPI()

QDRANT_HOST = os.getenv("QDRANT_HOST", "qdrant")
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.92"))
COLLECTION = "claim_cache"

def get_conn():
    return psycopg2.connect(os.environ["DATABASE_URL"])


def _root_domain(domain: str) -> str:
    """'en.wikipedia.org' -> 'wikipedia.org'"""
    parts = domain.split(".")
    return ".".join(parts[-2:]) if len(parts) > 2 else domain

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
        # Use query_points (modern API) instead of search
        results = client.query_points(
            collection_name=COLLECTION,
            query=embedding,
            limit=1,
            score_threshold=SIMILARITY_THRESHOLD,
        ).points
        
        if results:
            return {"hit": True, "result": results[0].payload}
        return {"hit": False}
    except Exception as e:
        print(f"[qdrant] lookup failed: {e}")
        return {"hit": False}


@app.post("/cache/store")
def cache_store(payload: dict):
    """
    Input:  { "embedding": [...], "verdict": "...", "explanation": "...", "sources": [...], ... }
    Output: { "status": "ok" }
    """
    embedding = payload.pop("embedding", None)
    if not embedding:
        return {"status": "error", "reason": "missing embedding"}

    try:
        client = get_qdrant()
        client.upsert(
            collection_name=COLLECTION,
            points=[PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding,
                payload=payload
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

    # Try exact match, then root domain
    for lookup in [domain, _root_domain(domain)]:
        cur.execute(
            "SELECT credibility_score, category FROM sources WHERE domain = %s",
            (lookup,)
        )
        row = cur.fetchone()
        if row:
            cur.close()
            conn.close()
            return {"credibility_score": row[0], "category": row[1]}

    cur.close()
    conn.close()
    # Not found — return neutral score (matches credibility_filter.py behavior)
    return {"credibility_score": 0.5, "category": "unknown"}


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