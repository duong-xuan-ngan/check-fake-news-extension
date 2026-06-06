"""Step 5: Filter search results by MBFC credibility score via DE API."""
import os
import requests
from typing import List, Optional
from ..schema import SearchResult, ScoredResult

CREDIBILITY_THRESHOLD = 0.5
DE_API_URL = os.getenv("DE_API_URL", "http://de-api:8001")

def lookup_score(domain: str) -> Optional[float]:
    """Fetch credibility score from DE API."""
    try:
        resp = requests.get(f"{DE_API_URL}/credibility", params={"domain": domain}, timeout=2)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("credibility_score")
    except Exception as e:
        print(f"[credibility_filter] API lookup failed for {domain}: {e}")
    # Return neutral score on failure, matching DE API default
    return 0.5

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
