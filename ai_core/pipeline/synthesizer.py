"""Step 8: turn the LLM analysis + sources into the user-facing CredibilityReport.

This is where the "Not sure" rule is enforced: weak/contradictory evidence MUST
collapse to Verdict.NOT_SURE rather than a confident TRUE/FALSE.
"""

from typing import List

from ..schema import (
    ConfidenceLevel,
    CredibilityAnalysis,
    CredibilityReport,
    Source,
    Verdict,
)


def synthesize(
    analysis: CredibilityAnalysis,
    sources: List[Source],
    min_sources_for_verdict: int = 2,
) -> CredibilityReport:
    """Combine the Gemini analysis + retrieved sources into the final report.

    Rules:
    - If `analysis.confidence_level` is UNVERIFIABLE → Verdict.NOT_SURE.
    - If fewer than `min_sources_for_verdict` credible sources were used → NOT_SURE.
    - Otherwise map credibility_score to TRUE / PARTIALLY_TRUE / FALSE bands.
    """
    raise NotImplementedError
