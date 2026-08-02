"""AI core — fact-checking pipeline.

Public entry point for Backend:

    from ai_core import analyze
    result = analyze("highlighted text from the user")

Returns an `AnalysisResult` (see ai_core.schema).

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

from .schema import (
    AnalysisResult,
    ConfidenceLevel,
    EvidenceStatus,
    FetchedArticle,
    SearchResult,
    Source,
    RatingStatus,
    Stance,
    Verdict,
)
from . import cache
from .pipeline import preprocessor, query_builder, searcher, credibility_filter, fetcher, synthesizer

__all__ = [
    "analyze",
    "AnalysisResult",
    "ConfidenceLevel",
    "EvidenceStatus",
    "FetchedArticle",
    "SearchResult",
    "Source",
    "RatingStatus",
    "Stance",
    "Verdict",
]

_EMPTY_INPUT = AnalysisResult(
    verdict=Verdict.NOT_SURE,
    explanation="No text was provided to analyze.",
    sources=[],
    confidence=ConfidenceLevel.LOW,
)


def analyze(text: str) -> AnalysisResult:
    """Run the full pipeline on highlighted text.

    Never raises — every failure mode returns a valid AnalysisResult.
    cached=True means the result was served from disk cache (no LLM calls made).
    cached=False means the full pipeline ran and the result was freshly computed.
    """
    # 1. Normalize to English
    english_claim = preprocessor.normalize(text)
    if not english_claim:
        return _EMPTY_INPUT

    # 2. Cache lookup — return early if fresh result exists
    cached_result = cache.get(english_claim)
    if cached_result is not None:
        return cached_result

    # 3. Build search query from the English claim
    search_query = query_builder.build_search_query(english_claim)

    # 4. Search → filter → fetch → synthesize
    results  = searcher.search(search_query)
    scored   = credibility_filter.select_evidence(results)
    articles = fetcher.fetch_all(scored)
    result   = synthesizer.synthesize(english_claim, articles)

    # 5. Cache the fresh result for future requests
    cache.set(english_claim, result)

    return result
