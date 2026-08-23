"""Step 5: Apply CRED-1/manual ratings without treating unknown as trusted.

Known low-rated domains are excluded. Unrated domains remain eligible as
limited evidence and are persisted to ``source_candidates`` by the batch
lookup so they can be reviewed later.
"""
from typing import List, Optional

from ..schema import RatingStatus, SearchResult, ScoredResult
from app.services import credibility_scores

CREDIBILITY_THRESHOLD = 0.5
MAX_EVIDENCE_SOURCES = 20


def _dedupe_by_domain(results: List[SearchResult]) -> List[SearchResult]:
    """Keep the first result per non-empty domain, preserving search rank."""
    seen = set()
    unique = []
    for result in results:
        if not result.domain or result.domain in seen:
            continue
        seen.add(result.domain)
        unique.append(result)
    return unique


def _batch_scores(results: List[SearchResult]) -> dict[str, Optional[float]]:
    try:
        return credibility_scores([
            {"domain": result.domain, "url": result.url}
            for result in results
        ])
    except Exception as exc:
        # A ratings outage must not silently classify every source as bad or
        # good. Preserve them as unrated evidence instead.
        print(f"[credibility_filter] CRED-1 lookup unavailable: {exc}")
        return {result.domain: None for result in results}


def select_evidence(results: List[SearchResult]) -> List[ScoredResult]:
    """Return up to 20 rated-eligible or explicitly unrated sources."""
    unique = _dedupe_by_domain(results)[:MAX_EVIDENCE_SOURCES]
    if not unique:
        return []

    scores = _batch_scores(unique)
    selected = []
    for result in unique:
        score = scores.get(result.domain)
        if score is not None and score < CREDIBILITY_THRESHOLD:
            continue
        selected.append(ScoredResult(
            url=result.url,
            title=result.title,
            snippet=result.snippet,
            domain=result.domain,
            credibility_score=score,
            rating_status=RatingStatus.RATED if score is not None else RatingStatus.UNRATED,
        ))
    return selected


def filter_credible(results: List[SearchResult]) -> List[ScoredResult]:
    """Backward-compatible name for the pipeline orchestrator."""
    return select_evidence(results)
