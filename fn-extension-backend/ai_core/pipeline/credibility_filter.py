"""Step 5: Filter search results by MBFC credibility score via DE API.

Lookups run concurrently — they are independent I/O-bound calls, and running
them serially made the stage cost N x (timeout x retries) in the worst case.
Threads rather than asyncio: `requests` is blocking, and keeping this module
synchronous means `analyze()` and the FastAPI endpoint are unchanged.
"""
import os
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional

import requests

from ..schema import SearchResult, ScoredResult

CREDIBILITY_THRESHOLD = 0.5
DE_API_URL = os.getenv("DE_API_URL", "http://de-api:8001")
DE_API_TIMEOUT = 2       # seconds, per attempt
DE_API_RETRIES = 1       # bounded: this is a synchronous request the user is waiting on
MAX_WORKERS = 10         # cap on in-flight lookups against the DE API

def _request_credibility(domain: str) -> Optional[dict]:
    """Single attempt against DE API. Returns parsed JSON, or None on any failure."""
    try:
        resp = requests.get(f"{DE_API_URL}/credibility", params={"domain": domain}, timeout=DE_API_TIMEOUT)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"[credibility_filter] API lookup failed for {domain}: {e}")
    return None

def lookup_score(domain: str) -> Optional[float]:
    """Fetch credibility score from DE API.

    Fails closed in both cases the caller should reject:
      - domain not in `sources` (status="not_found")
      - DE API unreachable after retry
    Returns None for either case; filter_credible treats None as "exclude".
    """
    data = _request_credibility(domain)
    for _ in range(DE_API_RETRIES):
        if data is not None:
            break
        data = _request_credibility(domain)

    if data is None:
        # DE API unreachable after retry — fail closed, don't silently admit at 0.5.
        print(f"[credibility_filter] DE API unreachable for {domain} after retry, excluding")
        return None

    if data.get("status") == "not_found":
        # Genuinely unscored domain — fail closed. (Logging for later review comes later.)
        return None

    return data.get("credibility_score")

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
