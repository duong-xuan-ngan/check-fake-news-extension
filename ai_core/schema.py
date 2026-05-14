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
    """Result from Serper web search (Sub-step 2.2)."""
    url: str
    title: str
    snippet: str
    domain: str


class Source(BaseModel):
    """A source used in the final verdict (Sub-step 2.5 output)."""
    url: str
    domain: str
    title: str
    credibility_score: float = Field(..., ge=0.0, le=1.0, description="From DE credibility DB.")
    stance: Stance = Field(..., description="Whether this source supports, contradicts, or is neutral.")


class FetchedArticle(BaseModel):
    """Article content fetched by Newspaper3k (Sub-step 2.4 output)."""
    url: str
    domain: str
    title: str
    body: str = Field(..., max_length=3000, description="Article text, truncated to 3000 chars.")
    credibility_score: float = Field(..., ge=0.0, le=1.0, description="Passed through from filtering step.")


class AnalysisResult(BaseModel):
    """Final output from the AI Pipeline — the contract with Backend."""
    verdict: Verdict
    explanation: str = Field(..., max_length=500, description="User-facing reasoning.")
    sources: List[Source] = Field(default_factory=list)
    confidence: ConfidenceLevel
    cached: bool = False
