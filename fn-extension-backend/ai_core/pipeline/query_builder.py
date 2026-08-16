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

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

_CLIENT = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)
_MODEL = "openrouter/auto"
# Output is one short query line. Left unset, OpenRouter reserves the model's
# full output ceiling (65536) against the account balance and 402s on a small
# balance — for a ~15-word answer. But 64 is too tight: when auto-routing picks
# a reasoning model, reasoning tokens count against this budget and can consume
# it entirely, leaving content empty. 256 gives that headroom while still being
# a rounding error against the account balance.
_MAX_TOKENS = 256

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
            max_tokens=_MAX_TOKENS,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": cleaned},
            ],
        )
        # content can be None — a reasoning model that spent its whole token
        # budget on reasoning returns no content. Don't call .strip() on None.
        content = response.choices[0].message.content
        query = (content or "").strip()
        # Strip any accidental quotes or markdown the model might add
        query = re.sub(r"^[\"'`]+|[\"'`]+$", "", query).strip()
        if query:
            return query
        print("[query_builder] LLM returned empty query, falling back.")
    except Exception as e:
        print(f"[query_builder] LLM call failed: {e}")

    # Layer 3: entity extraction
    return _extract_entities(cleaned)
