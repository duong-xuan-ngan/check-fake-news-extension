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


class Source(BaseModel):
    """Stage 4: FetchedArticle + LLM-assigned stance. Final output type."""
    url: str
    domain: str
    title: str
    credibility_score: float = Field(..., ge=0.0, le=1.0)
    stance: Stance = Field(..., description="Whether this source supports, contradicts, or is neutral to the claim.")


class AnalysisResult(BaseModel):
    """Final output from the AI Pipeline — the contract with Backend."""
    verdict: Verdict
    explanation: str = Field(..., max_length=500, description="User-facing reasoning.")
    sources: List[Source] = Field(default_factory=list)
    confidence: ConfidenceLevel
    cached: bool = False
