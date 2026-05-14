"""Step 4–5: filter search results by source credibility BEFORE fetching content.

Today: MBFC database lookup.
Future: DE exposes a Postgres-backed lookup API (Vietnamese sources). When that
lands, swap the implementation behind `lookup_domain` without touching callers.
"""

from typing import List, Optional

from ..schema import SearchResult, Source


def lookup_domain(domain: str) -> Optional[Source]:
    """Return credibility info for a domain, or None if unknown.

    TODO v1: load MBFC dataset (CSV/JSON) once at import time, do dict lookup.
    TODO v2: call DE's /credibility/{domain} endpoint.
    """
    raise NotImplementedError


def filter_credible(
    results: List[SearchResult],
    min_score: float = 0.5,
) -> List[Source]:
    """Drop results whose domain is unknown or below `min_score`.

    Returns Source objects (without fetched_text yet — that's the fetcher's job).
    """
    raise NotImplementedError
