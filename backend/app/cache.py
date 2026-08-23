"""Semantic cache stored directly in Qdrant."""
from datetime import datetime, timedelta, timezone
from typing import Optional
import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from pipeline.schema import AnalysisResult, ConfidenceLevel, Verdict
from .config import get_settings

COLLECTION = "claim_cache"
VECTOR_SIZE = 384
CACHE_TTL = timedelta(hours=24)
CACHE_CREATED_AT_FIELD = "cache_created_at"
CACHE_VERSION_FIELD = "cache_version"
CACHE_VERSION = "2026-08-22-evidence-v2"
_embed_model = None


def _client() -> QdrantClient:
    settings = get_settings()
    return QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)


def ensure_collection() -> None:
    try:
        client = _client()
        if not client.collection_exists(COLLECTION):
            client.create_collection(COLLECTION, vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE))
    except Exception as exc:
        print(f"[cache] Qdrant initialization deferred: {exc}")


def _embedding(text: str) -> list[float]:
    global _embed_model
    if _embed_model is None:
        from sentence_transformers import SentenceTransformer
        print("[cache] Loading embedding model...")
        _embed_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    return _embed_model.encode(text).tolist()


def _is_insufficient_evidence(result: AnalysisResult) -> bool:
    return result.verdict == Verdict.NOT_SURE and result.confidence == ConfidenceLevel.LOW and not result.sources


def _payload_is_expired(payload: dict, now: Optional[datetime] = None) -> bool:
    """Treat stale pipeline versions and entries older than 24 hours as expired."""
    if payload.get(CACHE_VERSION_FIELD) != CACHE_VERSION:
        return True
    raw_created_at = payload.get(CACHE_CREATED_AT_FIELD)
    if not isinstance(raw_created_at, str):
        return True
    try:
        created_at = datetime.fromisoformat(raw_created_at.replace("Z", "+00:00"))
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
    except ValueError:
        return True
    current_time = now or datetime.now(timezone.utc)
    return current_time >= created_at + CACHE_TTL


def get(claim: str) -> Optional[AnalysisResult]:
    try:
        client = _client()
        points = client.query_points(
            collection_name=COLLECTION,
            query=_embedding(claim),
            limit=1,
            score_threshold=get_settings().similarity_threshold,
        ).points
        if not points:
            return None
        point = points[0]
        payload = dict(point.payload or {})
        if _payload_is_expired(payload):
            try:
                client.delete(collection_name=COLLECTION, points_selector=[point.id])
            except Exception as exc:
                print(f"[cache] Failed to remove expired entry: {exc}")
            return None
        payload.pop(CACHE_CREATED_AT_FIELD, None)
        payload.pop(CACHE_VERSION_FIELD, None)
        result = AnalysisResult(**payload)
        if _is_insufficient_evidence(result):
            return None
        result.cached = True
        return result
    except Exception as exc:
        print(f"[cache] Lookup failed: {exc}")
        return None


def set(claim: str, result: AnalysisResult) -> None:
    if result.cached or _is_insufficient_evidence(result):
        return
    try:
        payload = result.model_dump(mode="json", exclude={"cached"})
        payload[CACHE_CREATED_AT_FIELD] = datetime.now(timezone.utc).isoformat()
        payload[CACHE_VERSION_FIELD] = CACHE_VERSION
        _client().upsert(
            collection_name=COLLECTION,
            points=[PointStruct(id=str(uuid.uuid4()), vector=_embedding(claim), payload=payload)],
        )
    except Exception as exc:
        print(f"[cache] Store failed: {exc}")
