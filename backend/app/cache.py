"""Semantic cache stored directly in Qdrant."""
from typing import Optional
import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from pipeline.schema import AnalysisResult, ConfidenceLevel, Verdict
from .config import get_settings

COLLECTION = "claim_cache"
VECTOR_SIZE = 384
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


def get(claim: str) -> Optional[AnalysisResult]:
    try:
        points = _client().query_points(
            collection_name=COLLECTION,
            query=_embedding(claim),
            limit=1,
            score_threshold=get_settings().similarity_threshold,
        ).points
        if not points:
            return None
        result = AnalysisResult(**points[0].payload)
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
        _client().upsert(
            collection_name=COLLECTION,
            points=[PointStruct(id=str(uuid.uuid4()), vector=_embedding(claim), payload=result.model_dump(mode="json", exclude={"cached"}))],
        )
    except Exception as exc:
        print(f"[cache] Store failed: {exc}")
