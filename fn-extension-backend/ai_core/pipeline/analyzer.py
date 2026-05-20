"""Step 7: Gemini analysis.

Migrated from the old ai_core/llm_service.py. Two entry points:
- analyze_standalone: original text only (no retrieved evidence) — used as a
  baseline path and by batch evals on the LIAR dataset.
- analyze_with_evidence: original text + fetched article bodies (RAG path).
"""

import json
import os
from typing import List

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

from ..prefilter import is_checkable_claim
from ..schema import CredibilityAnalysis, Source

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
MODEL = "gemini-2.0-flash"

SYSTEM_PROMPT_STANDALONE = """
You are the core logic engine for a "Credibility Evaluator" system.
Your primary task is to analyze user-highlighted text from social media, extract verifiable claims, and assess their factual credibility.

You must think step-by-step to arrive at your conclusion, but your final output MUST be a strictly formatted JSON object.

### INSTRUCTIONS:
1. Identify if the text contains distinct, objectively checkable factual claims.
2. If YES, list the extracted claims. If NO, set `is_factual` false.
3. Assess the credibility of the claims based on general knowledge consensus.
4. Calculate a `credibility_score` from 0.0 (Completely False/Fabricated) to 1.0 (Completely True/Verified).
5. Determine your `confidence_level` based strictly on these definitions:
   - HIGH: The claim is widely documented, and consensus is clear.
   - MEDIUM: The claim is plausible but lacks definitive consensus.
   - LOW: The claim is highly speculative, extremely recent, or lacks sufficient data.
   - UNVERIFIABLE: The text is an opinion, prediction, or subjective.
6. Write a concise `reasoning_trace` explaining your logic.

### JSON OUTPUT SCHEMA:
{
  "is_factual": boolean,
  "extracted_claims": ["claim 1", "claim 2"],
  "credibility_score": float (0.0 to 1.0),
  "confidence_level": "HIGH" | "MEDIUM" | "LOW" | "UNVERIFIABLE",
  "reasoning_trace": "String explaining your chain of thought step-by-step."
}
"""

SYSTEM_PROMPT_WITH_EVIDENCE = SYSTEM_PROMPT_STANDALONE + """

### ADDITIONAL CONTEXT:
You will be given retrieved evidence from credible sources. Ground your assessment in that evidence.
If the evidence is thin, contradictory, or absent, prefer `UNVERIFIABLE` — never force a confident verdict.
"""


def analyze_standalone(user_text: str) -> CredibilityAnalysis:
    """Layer-1 prefilter + Gemini call without retrieval. Used by evals."""
    if not is_checkable_claim(user_text):
        return CredibilityAnalysis(
            is_factual=False,
            extracted_claims=[],
            credibility_score=0.5,
            confidence_level="UNVERIFIABLE",
            reasoning_trace="Layer 1 Prefilter: input does not appear to contain an objectively verifiable claim.",
        )

    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=user_text,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT_STANDALONE,
                response_mime_type="application/json",
            ),
        )
        return CredibilityAnalysis(**json.loads(response.text))
    except errors.ClientError as e:
        raise Exception(f"AI Provider Error: Please try again in a moment. {e}")
    except Exception as e:
        raise Exception(f"System Error: Connection to AI failed. {e}")


def analyze_with_evidence(user_text: str, sources: List[Source]) -> CredibilityAnalysis:
    """RAG path: prompt Gemini with the original text + fetched article bodies.

    TODO: format sources as a numbered context block, send through generate_content
    with SYSTEM_PROMPT_WITH_EVIDENCE.
    """
    raise NotImplementedError
