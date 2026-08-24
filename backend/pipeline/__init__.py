"""VeriFact fact-checking pipeline.

Public entry point for the backend:

    from pipeline import analyze
    result = analyze("highlighted text from the user")

Returns an `AnalysisResult` (see pipeline.schema).

Pipeline (sequential):
    preprocessor  → normalize raw text to English claim
    cache         → return early on hit
    query_builder → rewrite claim as search query
    searcher      → fetch web results
    credibility_filter → drop low-credibility domains
    fetcher       → download article bodies
    synthesizer   → single LLM call → verdict + explanation + sources
    cache         → store result for future requests
"""

from time import perf_counter

from .schema import (
    AnalysisResult,
    ConfidenceLevel,
    FetchedArticle,
    RatingStatus,
    SearchResult,
    Source,
    Stance,
    Verdict,
)
from . import cache
from .steps import preprocessor, query_builder, searcher, credibility_filter, fetcher, synthesizer

__all__ = [
    "analyze",
    "AnalysisResult",
    "ConfidenceLevel",
    "FetchedArticle",
    "RatingStatus",
    "SearchResult",
    "Source",
    "Stance",
    "Verdict",
]

_EMPTY_INPUT = AnalysisResult(
    verdict=Verdict.NOT_SURE,
    explanation="No text was provided to analyze.",
    sources=[],
    confidence=ConfidenceLevel.LOW,
)


def _run_stage(name, operation):
    """Run one pipeline stage and emit an operational timing without user text."""
    started_at = perf_counter()
    try:
        return operation()
    finally:
        duration_ms = round((perf_counter() - started_at) * 1000)
        print(f"[pipeline] stage={name} duration_ms={duration_ms}")


def analyze(text: str) -> AnalysisResult:
    """Run the full pipeline on highlighted text.

    Never raises — every failure mode returns a valid AnalysisResult.
    cached=True means the result was served from disk cache (no LLM calls made).
    cached=False means the full pipeline ran and the result was freshly computed.
    """
    total_started_at = perf_counter()
    try:
        # 1. Normalize to English
        english_claim = _run_stage("normalize", lambda: preprocessor.normalize(text))
        if not english_claim:
            return _EMPTY_INPUT

        # 2. Cache lookup — return early if fresh result exists
        cached_result = _run_stage("cache_lookup", lambda: cache.get(english_claim))
        if cached_result is not None:
            print("[pipeline] cache=hit")
            return cached_result
        print("[pipeline] cache=miss")

        # 3. Build search query from the English claim
        search_query = _run_stage("query_builder", lambda: query_builder.build_search_query(english_claim))

        # 4. Search → filter → fetch → synthesize
        results = _run_stage("search", lambda: searcher.search(search_query))
        scored = _run_stage("credibility_filter", lambda: credibility_filter.filter_credible(results))
        articles = _run_stage("fetch_articles", lambda: fetcher.fetch_all(scored, english_claim))
        result = _run_stage("synthesize", lambda: synthesizer.synthesize(english_claim, articles))

        # 5. Cache the fresh result for future requests
        _run_stage("cache_store", lambda: cache.set(english_claim, result))
        return result
    finally:
        total_ms = round((perf_counter() - total_started_at) * 1000)
        print(f"[pipeline] stage=total duration_ms={total_ms}")
