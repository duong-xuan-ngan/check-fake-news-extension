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

import os
import time

from .schema import (
    AnalysisResult,
    ConfidenceLevel,
    FailureReason,
    FetchedArticle,
    RETRYABLE_FAILURES,
    SearchResult,
    Source,
    Stance,
    Verdict,
    failure_result,
)
from . import cache
from .pipeline import preprocessor, query_builder, searcher, credibility_filter, fetcher, synthesizer

__all__ = [
    "analyze",
    "AnalysisResult",
    "ConfidenceLevel",
    "FailureReason",
    "FetchedArticle",
    "RETRYABLE_FAILURES",
    "SearchResult",
    "Source",
    "Stance",
    "Verdict",
]


def _no_evidence_reason(results, scored) -> FailureReason:
    """Attribute an empty article list to the stage that actually emptied it.

    The synthesizer cannot do this — it only receives the final list and has no
    way to tell "search found nothing" from "every domain was rejected" from
    "every fetch failed". Those are three different problems.
    """
    if not results:
        return FailureReason.NO_SEARCH_RESULTS
    if not scored:
        return FailureReason.NO_CREDIBLE_SOURCES
    return FailureReason.NO_ARTICLE_CONTENT

# --------------------------------------------------------------------------
# TEMPORARY stage timing — measurement only, remove when done.
# Off unless PIPELINE_TIMING=1 is set. Purely additive: no branch below
# changes a return value, an argument, or the order of any call.
# --------------------------------------------------------------------------
_TIMING = os.getenv("PIPELINE_TIMING", "").lower() in ("1", "true", "yes")


def _report(marks, counts):
    """Print per-stage wall-clock from a list of (label, perf_counter) marks."""
    total = marks[-1][1] - marks[0][1]
    print("\n" + "=" * 48)
    print(f"{'STAGE':<22}{'SECONDS':>10}{'SHARE':>10}")
    print("-" * 48)
    for (_, t0), (label, t1) in zip(marks, marks[1:]):
        dt = t1 - t0
        share = (dt / total * 100) if total else 0.0
        print(f"{label:<22}{dt:>10.2f}{share:>9.1f}%")
    print("-" * 48)
    print(f"{'TOTAL':<22}{total:>10.2f}{100.0:>9.1f}%")
    if counts:
        print("counts: " + "  ".join(f"{k}={v}" for k, v in counts.items()))
    print("=" * 48 + "\n")


def analyze(text: str) -> AnalysisResult:
    """Run the full pipeline on highlighted text.

    Never raises — every failure mode returns a valid AnalysisResult.
    cached=True means the result was served from disk cache (no LLM calls made).
    cached=False means the full pipeline ran and the result was freshly computed.
    """
    marks = [("", time.perf_counter())] if _TIMING else None
    counts = {}

    # 1. Normalize to English
    english_claim = preprocessor.normalize(text)
    if _TIMING:
        marks.append(("preprocessor", time.perf_counter()))
    if not english_claim:
        if _TIMING:
            _report(marks, counts)
        return failure_result(FailureReason.EMPTY_INPUT)

    # 2. Cache lookup — return early if fresh result exists
    cached_result = cache.get(english_claim)
    if _TIMING:
        marks.append(("cache lookup", time.perf_counter()))
    if cached_result is not None:
        if _TIMING:
            counts["cache"] = "HIT (timings below are not a pipeline run)"
            _report(marks, counts)
        return cached_result

    # 3. Build search query from the English claim
    search_query = query_builder.build_search_query(english_claim)
    if _TIMING:
        marks.append(("query_builder", time.perf_counter()))

    # 4. Search → filter → fetch → synthesize
    results  = searcher.search(search_query)
    if _TIMING:
        marks.append(("searcher", time.perf_counter()))

    scored   = credibility_filter.filter_credible(results)
    if _TIMING:
        marks.append(("credibility_filter", time.perf_counter()))

    articles = fetcher.fetch_all(scored)
    if _TIMING:
        marks.append(("fetcher", time.perf_counter()))

    result   = synthesizer.synthesize(english_claim, articles)
    if _TIMING:
        marks.append(("synthesizer", time.perf_counter()))

    # The synthesizer reports a missing-evidence failure as NO_ARTICLE_CONTENT
    # because that is all it can see. Only here are `results` and `scored` in
    # scope, so only here can the failure be attributed to the right stage.
    if result.failure_reason is FailureReason.NO_ARTICLE_CONTENT:
        result = failure_result(_no_evidence_reason(results, scored))

    # 5. Cache the fresh result for future requests
    cache.set(english_claim, result)
    if _TIMING:
        marks.append(("cache store", time.perf_counter()))
        counts.update(
            search_results=len(results),
            passed_filter=len(scored),
            fetched=len(articles),
            verdict=result.verdict.value,
            failure=result.failure_reason.value if result.failure_reason else "-",
        )
        _report(marks, counts)

    return result
