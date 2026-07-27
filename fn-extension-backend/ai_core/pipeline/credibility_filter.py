"""Step 5: Filter search results by MBFC credibility score via DE API."""
import os
import requests
from typing import List, Optional
from ..schema import SearchResult, ScoredResult

CREDIBILITY_THRESHOLD = 0.5
DE_API_URL = os.getenv("DE_API_URL", "http://de-api:8001")
DE_API_TIMEOUT = 2       # seconds, per attempt
DE_API_RETRIES = 1       # bounded: this is a synchronous request the user is waiting on

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

def filter_credible(results: List[SearchResult]) -> List[ScoredResult]:
    """Keep only results whose domain clears CREDIBILITY_THRESHOLD.
    Deduplicates by domain — only the first result per domain is kept.
    """
    output = []
    seen_domains = set()
    for result in results:
        if result.domain in seen_domains:
            continue
        score = lookup_score(result.domain)
        if score is None or score < CREDIBILITY_THRESHOLD:
            continue
        seen_domains.add(result.domain)
        output.append(ScoredResult(
            url=result.url,
            title=result.title,
            snippet=result.snippet,
            domain=result.domain,
            credibility_score=score,
        ))
    return output
