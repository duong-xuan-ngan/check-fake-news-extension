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


class RatingStatus(str, Enum):
    RATED = "RATED"
    UNRATED = "UNRATED"


class EvidenceStatus(str, Enum):
    RATED = "RATED"
    LIMITED_UNRATED = "LIMITED_UNRATED"
    NONE = "NONE"


class SearchResult(BaseModel):
    """Stage 1: Raw result from Serper web search."""
    url: str
    title: str
    snippet: str
    domain: str


class ScoredResult(BaseModel):
    """Stage 2: SearchResult + optional independent source rating."""
    url: str
    title: str
    snippet: str
    domain: str
    credibility_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    rating_status: RatingStatus = RatingStatus.RATED


class FetchedArticle(BaseModel):
    """Stage 3: ScoredResult + downloaded article body."""
    url: str
    domain: str
    title: str
    body: str = Field(..., max_length=3000, description="Article text, truncated to 3000 chars.")
    credibility_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="None means the source has not been rated.")
    rating_status: RatingStatus = RatingStatus.RATED
    published_at: Optional[datetime] = Field(None, description="Article publication date. None if unavailable.")


class Source(BaseModel):
    """Stage 4: FetchedArticle + LLM-assigned stance. Final output type."""
    url: str
    domain: str
    title: str
    credibility_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    rating_status: RatingStatus = RatingStatus.RATED
    stance: Stance = Field(..., description="Whether this source supports, contradicts, or is neutral to the claim.")
    published_at: Optional[datetime] = Field(None, description="Article publication date. None if unavailable.")


class AnalysisResult(BaseModel):
    """Final output from the AI Pipeline — the contract with Backend."""
    verdict: Verdict
    explanation: str = Field(..., max_length=500, description="User-facing reasoning.")
    sources: List[Source] = Field(default_factory=list)
    confidence: ConfidenceLevel
    evidence_status: EvidenceStatus = EvidenceStatus.NONE
    cached: bool = False
