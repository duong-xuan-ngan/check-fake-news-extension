"""AI core — fact-checking pipeline.

Public entry point for Backend:

    from ai_core import analyze
    result = analyze("highlighted text from the user")

Returns an `AnalysisResult` (see ai_core.schema).
"""

from .schema import (
    AnalysisResult,
    ConfidenceLevel,
    FetchedArticle,
    SearchResult,
    Source,
    Stance,
    Verdict,
)

__all__ = [
    "analyze",
    "AnalysisResult",
    "ConfidenceLevel",
    "FetchedArticle",
    "SearchResult",
    "Source",
    "Stance",
    "Verdict",
]


def analyze(text: str) -> AnalysisResult:
    """Run the full pipeline on highlighted text.

    Sequential: query → search → filter → fetch → LLM → verdict.
    Each step's failure is easy to locate.
    """
    raise NotImplementedError("Pipeline steps not yet implemented.")
