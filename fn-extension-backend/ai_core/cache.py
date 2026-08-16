"""Semantic Vector Cache via DE API."""
import os
import requests
from typing import Optional
from .schema import AnalysisResult, ConfidenceLevel, Verdict

DE_API_URL = os.getenv("DE_API_URL", "http://de-api:8001")

# We lazily load the model so it doesn't block fast startup if not needed immediately
_embed_model = None


def _is_insufficient_evidence(result: AnalysisResult) -> bool:
    return (
        result.verdict == Verdict.NOT_SURE
        and result.confidence == ConfidenceLevel.LOW
        and not result.sources
    )

def _get_embedding(text: str) -> list[float]:
    global _embed_model
    if _embed_model is None:
        from sentence_transformers import SentenceTransformer
        print("[cache] Loading embedding model...")
        # Note: Match the dimension (384) in de/qdrant_setup.py
        _embed_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    return _embed_model.encode(text).tolist()

def get(english_claim: str) -> Optional[AnalysisResult]:
    """Look up a cached result via vector embedding."""
    try:
        embedding = _get_embedding(english_claim)
        resp = requests.post(
            f"{DE_API_URL}/cache/lookup", 
            json={"embedding": embedding},
            timeout=3
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("hit"):
                result_payload = data["result"]
                result = AnalysisResult(**result_payload)
                if _is_insufficient_evidence(result):
                    print("[cache] Ignoring cached insufficient-evidence result.")
                    return None
                result.cached = True
                print("[cache] Qdrant Hit!")
                return result
    except Exception as e:
        print(f"[cache] Lookup failed: {e}")
    return None

def set(english_claim: str, result: AnalysisResult) -> None:
    """Store a result via vector embedding."""
    if result.cached or _is_insufficient_evidence(result):
        return

    try:
        embedding = _get_embedding(english_claim)
        # Dump the model to a JSON-safe dict, exclude 'cached' as we set it on hit.
        # 'failure_reason' is excluded too: only successful results reach this
        # point (see _is_insufficient_evidence above), so it is always None here,
        # and omitting it keeps the DE /cache/store payload unchanged.
        result_dict = result.model_dump(mode='json', exclude={'cached', 'failure_reason'})
        payload = {
            "embedding": embedding,
            **result_dict
        }
        requests.post(
            f"{DE_API_URL}/cache/store", 
            json=payload,
            timeout=3
        )
        print("[cache] Result sent to Qdrant.")
    except Exception as e:
        print(f"[cache] Store failed: {e}")
