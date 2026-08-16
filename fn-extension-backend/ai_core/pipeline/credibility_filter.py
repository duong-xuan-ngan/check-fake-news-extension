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

# User-generated content. MBFC scores these as companies (facebook.com is 0.9 in
# the seed), but the score describes the platform, not the arbitrary post we
# would be citing. Rejected before any lookup.
BLOCKED_DOMAINS = frozenset({
    "facebook.com",
    "youtube.com",
    "twitter.com",
    "x.com",
    "reddit.com",
    "tiktok.com",
    "instagram.com",
    "linkedin.com",
    "quora.com",
    "medium.com",
})

# MBFC rates news and media outlets. Of 4336 seeded domains, 7 are .gov and 6
# are .edu — so government agencies and universities are almost always
# `not_found`, and the fail-closed default drops them. Admitted by TLD instead.
INSTITUTIONAL_TLDS = (".gov", ".edu")
INSTITUTIONAL_SCORE = 0.8

def _request_credibility(domain: str) -> Optional[dict]:
    """Single attempt against DE API. Returns parsed JSON, or None on any failure."""
    try:
        resp = requests.get(f"{DE_API_URL}/credibility", params={"domain": domain}, timeout=DE_API_TIMEOUT)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"[credibility_filter] API lookup failed for {domain}: {e}")
    return None

def _is_blocked(domain: str) -> bool:
    """User-generated-content platforms, including subdomains (m.facebook.com)."""
    domain = domain.lower()
    return any(domain == b or domain.endswith(f".{b}") for b in BLOCKED_DOMAINS)


def _is_institutional(domain: str) -> bool:
    """True for government and academic domains, including compound TLDs.

    Matches on label position rather than a plain suffix test so that
    `des.sc.gov` and `moh.gov.vn` both qualify, while `gov.com` does not —
    a real institutional domain never has `gov` or `edu` as its first label.
    """
    labels = domain.lower().split(".")[1:]
    return any(tld.lstrip(".") in labels for tld in INSTITUTIONAL_TLDS)


def lookup_score(domain: str) -> Optional[float]:
    """Fetch credibility score from DE API.

    Fails closed in both cases the caller should reject:
      - domain not in `sources` (status="not_found")
      - DE API unreachable after retry
    Returns None for either case; filter_credible treats None as "exclude".

    Two exceptions to the lookup:
      - BLOCKED_DOMAINS are rejected outright, before any request
      - government and academic domains fall back to INSTITUTIONAL_SCORE when
        the seed has no row for them, rather than being dropped
    """
    if _is_blocked(domain):
        print(f"[credibility_filter] {domain} is a user-content platform, excluding")
        return None

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
        # Seeded scores win where they exist, so this is checked only on a miss.
        if _is_institutional(domain):
            return INSTITUTIONAL_SCORE
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
