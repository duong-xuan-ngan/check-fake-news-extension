"""Step 5: Filter search results by MBFC credibility score.

Loads data/mbfc_credibility.json at import time.
When DE delivers their /credibility API, replace _load_db() with an HTTP call.
"""
import json
from pathlib import Path
from typing import List, Optional

from ..schema import SearchResult, ScoredResult

# Domains scoring below this threshold are dropped.
CREDIBILITY_THRESHOLD = 0.5

_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "mbfc_credibility.json"


def _load_db() -> dict[str, float]:
    """Load MBFC credibility scores from JSON. Returns empty dict on failure."""
    try:
        return json.loads(_DB_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[credibility_filter] failed to load MBFC db: {e}")
        return {}


_CREDIBILITY_DB: dict[str, float] = _load_db()


def _root_domain(domain: str) -> str:
    """Strip subdomains: 'en.wikipedia.org' -> 'wikipedia.org'."""
    parts = domain.split(".")
    return ".".join(parts[-2:]) if len(parts) > 2 else domain


def lookup_score(domain: str) -> Optional[float]:
    """Return credibility score for a domain, or None if not in DB.
    Falls back to root domain if subdomain not found.
    """
    return _CREDIBILITY_DB.get(domain) or _CREDIBILITY_DB.get(_root_domain(domain))


def filter_credible(results: List[SearchResult]) -> List[ScoredResult]:
    """Keep only results whose domain clears CREDIBILITY_THRESHOLD."""
    output = []
    for result in results:
        score = lookup_score(result.domain)
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
