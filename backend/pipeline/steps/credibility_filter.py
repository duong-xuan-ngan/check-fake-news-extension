"""Step 5: Filter search results by MBFC credibility score via DE API.

Lookups run concurrently — they are independent I/O-bound calls, and running
them serially made the stage cost N x (timeout x retries) in the worst case.
Threads rather than asyncio: `requests` is blocking, and keeping this module
synchronous means `analyze()` and the FastAPI endpoint are unchanged.
"""
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional

from ..schema import SearchResult, ScoredResult
from app.services import credibility_score

CREDIBILITY_THRESHOLD = 0.5
MAX_WORKERS = 10         # cap on in-flight lookups against the DE API

def lookup_score(domain: str) -> Optional[float]:
    """Read a score from the local PostgreSQL service; unknown/failing is excluded."""
    try:
        return credibility_score(domain)
    except Exception as exc:
        print(f"[credibility_filter] lookup failed for {domain}: {exc}")
        return None

def _dedupe_by_domain(results: List[SearchResult]) -> List[SearchResult]:
    """First result per domain, preserving search rank order.

    Runs before any lookup is dispatched. Previously dedup was interleaved with
    scoring and the `seen` entry was only recorded for domains that passed the
    threshold, so every extra result from a rejected domain triggered another
    full lookup — on exactly the not_found/unreachable path that costs the most.
    """
    seen = set()
    unique = []
    for result in results:
        if result.domain in seen:
            continue
        seen.add(result.domain)
        unique.append(result)
    return unique


def filter_credible(results: List[SearchResult]) -> List[ScoredResult]:
    """Keep only results whose domain clears CREDIBILITY_THRESHOLD.

    Deduplicates by domain — only the first result per domain is kept.
    Lookups run concurrently; output preserves the input's rank order.
    """
    if not results:
        return []

    unique = _dedupe_by_domain(results)

    # pool.map preserves input order regardless of completion order.
    with ThreadPoolExecutor(max_workers=min(len(unique), MAX_WORKERS)) as pool:
        scores = list(pool.map(lambda r: lookup_score(r.domain), unique))

    output = []
    for result, score in zip(unique, scores):
        if score is None or score < CREDIBILITY_THRESHOLD:
            continue
        output.append(ScoredResult(
            url=result.url,
            title=result.title,
            snippet=result.snippet,
            domain=result.domain,
            credibility_score=score,
        ))
    return output
