from datetime import datetime
from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum


class ConfidenceLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class Verdict(str, Enum):
    TRUE = "TRUE"
    FALSE = "FALSE"
    UNVERIFIED = "UNVERIFIED"
    NOT_SURE = "NOT_SURE"


class Stance(str, Enum):
    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"
    NEUTRAL = "NEUTRAL"


class FailureReason(str, Enum):
    """Why the pipeline could not produce a real verdict.

    None on success — including a genuine NOT_SURE where the LLM weighed the
    evidence and was honestly unsure. A non-None value always means the pipeline
    did not complete, which is a different thing from an unverifiable claim.

    Attribution is split by what each layer can actually see:
      - synthesizer sets LLM_ERROR / PARSE_ERROR (failures it owns)
      - analyze() sets the rest, since only it knows which list went empty first
    """
    EMPTY_INPUT         = "EMPTY_INPUT"
    NO_SEARCH_RESULTS   = "NO_SEARCH_RESULTS"
    NO_CREDIBLE_SOURCES = "NO_CREDIBLE_SOURCES"
    NO_ARTICLE_CONTENT  = "NO_ARTICLE_CONTENT"
    LLM_ERROR           = "LLM_ERROR"
    PARSE_ERROR         = "PARSE_ERROR"


# Failures worth offering the user a retry for — the claim is fine, we broke.
RETRYABLE_FAILURES = frozenset({
    FailureReason.LLM_ERROR,
    FailureReason.PARSE_ERROR,
})


class SearchResult(BaseModel):
    """Stage 1: Raw result from Serper web search."""
    url: str
    title: str
    snippet: str
    domain: str


class ScoredResult(BaseModel):
    """Stage 2: SearchResult + credibility score from MBFC lookup."""
    url: str
    title: str
    snippet: str
    domain: str
    credibility_score: float = Field(..., ge=0.0, le=1.0)


class FetchedArticle(BaseModel):
    """Stage 3: ScoredResult + downloaded article body."""
    url: str
    domain: str
    title: str
    body: str = Field(..., max_length=3000, description="Article text, truncated to 3000 chars.")
    credibility_score: float = Field(..., ge=0.0, le=1.0, description="Passed through from filtering step.")
    published_at: Optional[datetime] = Field(None, description="Article publication date. None if unavailable.")


class Source(BaseModel):
    """Stage 4: FetchedArticle + LLM-assigned stance. Final output type."""
    url: str
    domain: str
    title: str
    credibility_score: float = Field(..., ge=0.0, le=1.0)
    stance: Stance = Field(..., description="Whether this source supports, contradicts, or is neutral to the claim.")
    published_at: Optional[datetime] = Field(None, description="Article publication date. None if unavailable.")


class AnalysisResult(BaseModel):
    """Final output from the AI Pipeline — the contract with Backend."""
    verdict: Verdict
    explanation: str = Field(..., max_length=500, description="User-facing reasoning.")
    sources: List[Source] = Field(default_factory=list)
    confidence: ConfidenceLevel
    cached: bool = False
    failure_reason: Optional[FailureReason] = Field(
        None,
        description=(
            "Set only when the pipeline could not complete. None on success, "
            "including a genuine NOT_SURE verdict backed by sources. Clients can "
            "check RETRYABLE_FAILURES to decide whether to offer a retry."
        ),
    )


# Single source of truth for user-facing failure text. Kept honest: the message
# describes what actually happened, and system faults are not disguised as
# "we couldn't find evidence".
_FAILURE_EXPLANATION = {
    FailureReason.EMPTY_INPUT:
        "No text was provided to analyze.",
    FailureReason.NO_SEARCH_RESULTS:
        "We couldn't find any web results for this claim.",
    FailureReason.NO_CREDIBLE_SOURCES:
        "We found web results, but none from sources we can verify the credibility of.",
    FailureReason.NO_ARTICLE_CONTENT:
        "We found credible sources, but couldn't read enough of their content to judge this claim.",
    FailureReason.LLM_ERROR:
        "Something went wrong while analyzing this claim. Please try again.",
    FailureReason.PARSE_ERROR:
        "Something went wrong while analyzing this claim. Please try again.",
}


def failure_result(reason: FailureReason) -> AnalysisResult:
    """Build the standard NOT_SURE result for a given failure reason.

    Shape (NOT_SURE / LOW / no sources) is deliberately unchanged so that
    cache._is_insufficient_evidence still declines to cache these.
    """
    return AnalysisResult(
        verdict=Verdict.NOT_SURE,
        explanation=_FAILURE_EXPLANATION[reason],
        sources=[],
        confidence=ConfidenceLevel.LOW,
        failure_reason=reason,
    )
