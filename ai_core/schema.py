from pydantic import BaseModel, Field, field_validator
from typing import List
from enum import Enum

class ConfidenceLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNVERIFIABLE = "UNVERIFIABLE"

class CredibilityAnalysis(BaseModel):
    is_factual: bool = Field(..., description="Whether the input contains checkable factual claims.")
    extracted_claims: List[str] = Field(..., description="List of discrete verifiable claims.")
    credibility_score: float = Field(..., description="Score from 0.0 to 1.0.")
    confidence_level: ConfidenceLevel = Field(..., description="The system's certainty.")
    reasoning_trace: str = Field(..., description="Chain-of-thought explanation.")
    
    # NEW V2 SYNTAX
    @field_validator('credibility_score')
    @classmethod
    def score_range(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError('Score must be between 0.0 and 1.0')
        return v

