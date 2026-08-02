"""Select search evidence using independent source ratings when available.

The DE batch endpoint has two responsibilities:
1. return ratings for known domains;
2. persist unknown domains in `source_candidates` for later review.

Unknown means *unrated*, not unreliable. Unrated results remain eligible as
limited evidence, while explicitly low-rated results are excluded.
"""
import ipaddress
import json
import os
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlsplit

import requests

from ..schema import RatingStatus, ScoredResult, SearchResult

CREDIBILITY_THRESHOLD = 0.5
MAX_EVIDENCE_SOURCES = 5
DE_API_URL = os.getenv("DE_API_URL", "http://localhost:8001").rstrip("/")
DE_API_TIMEOUT_SECONDS = float(os.getenv("DE_API_TIMEOUT_SECONDS", "2"))

_DB_PATH = Path(__file__).resolve().parents[3] / "data" / "cred1_compact.json"


def _load_db() -> dict[str, float]:
    """Load CRED-1 compact scores for the local negative-signal fallback."""
    try:
        raw = json.loads(_DB_PATH.read_text(encoding="utf-8"))
        return {
            _normalize_domain(domain): float(metadata["s"])
            for domain, metadata in raw.items()
            if _normalize_domain(domain) and isinstance(metadata, dict) and "s" in metadata
        }
    except Exception as exc:
        print(f"[credibility_filter] failed to load local credibility db: {exc}")
        return {}


def _normalize_domain(value: str) -> str:
    """Return a normalized hostname from a domain, URL, or hostname/path."""
    candidate = str(value or "").strip().lower()
    parsed = urlsplit(candidate if "://" in candidate else f"//{candidate}")
    return (parsed.hostname or "").removeprefix("www.").rstrip(".")


_CREDIBILITY_DB: dict[str, float] = _load_db()


def _lookup_candidates(domain: str) -> list[str]:
    """Return exact hostname followed by progressively broader suffixes."""
    normalized = _normalize_domain(domain)
    if not normalized:
        return []
    try:
        ipaddress.ip_address(normalized)
        return [normalized]
    except ValueError:
        parts = normalized.split(".")
        return [".".join(parts[index:]) for index in range(max(1, len(parts) - 1))]


def lookup_score(domain: str) -> Optional[float]:
    """Return the local fallback score for a domain, or None if unrated."""
    for candidate in _lookup_candidates(domain):
        score = _CREDIBILITY_DB.get(candidate)
        if score is not None:
            return score
    return None


def _batch_ratings(results: List[SearchResult]) -> dict[str, Optional[float]]:
    """Discover domains through DE and return domain -> score/null.

    If DE is temporarily unavailable, analysis still works using the local
    rating data. The failed discovery is logged so it can be monitored.
    """
    try:
        response = requests.post(
            f"{DE_API_URL}/credibility/batch",
            json={
                "sources": [
                    {"domain": result.domain, "url": result.url}
                    for result in results
                ]
            },
            timeout=DE_API_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return {
            item["domain"]: item.get("credibility_score")
            for item in response.json().get("results", [])
        }
    except Exception as exc:
        print(f"[credibility_filter] DE discovery/rating unavailable: {exc}")
        return {result.domain: lookup_score(result.domain) for result in results}


def select_evidence(results: List[SearchResult]) -> List[ScoredResult]:
    """Return up to five rated-credible or unrated results.

    Rated evidence is prioritized. A known score below the threshold is
    excluded; a missing score is retained with `UNRATED` status so downstream
    policy can provide a useful but explicitly limited result.
    """
    ratings = _batch_ratings(results)
    rated: list[ScoredResult] = []
    unrated: list[ScoredResult] = []
    seen_domains = set()

    for result in results:
        if not result.domain or result.domain in seen_domains:
            continue
        seen_domains.add(result.domain)
        score = ratings.get(result.domain)

        if score is not None and score < CREDIBILITY_THRESHOLD:
            continue

        selected = ScoredResult(
            url=result.url,
            title=result.title,
            snippet=result.snippet,
            domain=result.domain,
            credibility_score=score,
            rating_status=(
                RatingStatus.RATED if score is not None else RatingStatus.UNRATED
            ),
        )
        (rated if score is not None else unrated).append(selected)

    return (rated + unrated)[:MAX_EVIDENCE_SOURCES]


def filter_credible(results: List[SearchResult]) -> List[ScoredResult]:
    """Backward-compatible alias for callers using the old stage name."""
    return select_evidence(results)
