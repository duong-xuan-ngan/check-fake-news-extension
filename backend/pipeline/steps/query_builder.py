"""Step 2: turn an English claim into a keyword-focused search query.

Input is always English — translation has been lifted out to preprocessor.py.
Single responsibility: rewrite the claim as an optimized Serper query string.

Three-layer fallback:
  Layer 1 — the cleaned English claim itself (immediate, no LLM)
  Layer 2 — LLM rewrites it as a keyword-focused query
  Layer 3 — regex entity extraction when LLM fails
"""
import os
import re

from openai import OpenAI


_CLIENT = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)
_MODEL = "openrouter/auto"
_REQUEST_TIMEOUT_SECONDS = 15.0

_SYSTEM_PROMPT = """You are a search query optimizer.

Given an English factual claim, rewrite it as a short, keyword-focused search
engine query (max 15 words). Drop filler words and stop words. Keep all named
entities, numbers, dates, and key facts verbatim.

Return ONLY the query string. No preamble, no punctuation at the end, no markdown.

Examples:
  Input:  "Florentino Perez is the president of FC Barcelona"
  Output: Florentino Perez president FC Barcelona

  Input:  "Apple announced a new iPhone model in September 2025"
  Output: Apple new iPhone model September 2025
"""


def _extract_entities(text: str) -> str:
    """Layer 3 fallback: pull capitalised tokens and numbers from English text."""
    tokens = re.findall(r'\b[A-Z][^\s]*(?:\s+[A-Z][^\s]*)*|\d+', text)
    return " ".join(tokens[:8]) or text


def build_search_query(english_claim: str) -> str:
    """Turn an English claim into an optimized search query string.

    Falls back gracefully through three layers — never raises to caller.

    Args:
        english_claim: Clean English text from preprocessor.normalize().

    Returns:
        A keyword-focused query string, max ~15 words.
    """
    # Layer 1: use the claim directly if it's already short enough
    cleaned = " ".join(english_claim.strip().split())
    if len(cleaned.split()) <= 10:
        return cleaned

    # Layer 2: LLM rewrite
    try:
        response = _CLIENT.chat.completions.create(
            model=_MODEL,
            temperature=0.1,
            timeout=_REQUEST_TIMEOUT_SECONDS,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": cleaned},
            ],
        )
        query = response.choices[0].message.content.strip()
        # Strip any accidental quotes or markdown the model might add
        query = re.sub(r"^[\"'`]+|[\"'`]+$", "", query).strip()
        if query:
            return query
        print("[query_builder] LLM returned empty query, falling back.")
    except Exception as e:
        print(f"[query_builder] LLM call failed: {e}")

    # Layer 3: entity extraction
    return _extract_entities(cleaned)
