"""Step 1 (pre-pipeline): normalize raw user text to clean English.

Lifted out of query_builder.py — translation is no longer a side effect of
query construction. The pipeline downstream of this module always sees English.

Design:
  - is_english(): cheap rule (no diacritics / non-Latin chars) — no LLM call.
  - translate_to_english(): LLM call, used only when is_english() returns False.
  - normalize(): public entry point. Returns the English claim — used by
    analyze() to compute the cache key and to feed query_builder + synthesizer.

Graceful degradation: any LLM failure during translation falls back to the
cleaned original text. The pipeline will likely return NOT_SURE downstream,
which is the correct behavior (never crash, never lie).
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
# Output is a translation of the input claim, so roughly input-sized.
# See query_builder._MAX_TOKENS for why this must be set explicitly.
_MAX_TOKENS = 512

_MAX_INPUT_CHARS = 1500

# Allowed chars for the "is English" heuristic:
#   - ASCII letters, digits, whitespace
#   - Common punctuation (the typical set seen in English news / social media)
# Anything outside this set (Vietnamese diacritics, CJK, Cyrillic, Arabic, emoji)
# triggers translation.
_ENGLISH_CHAR_RE = re.compile(r"^[A-Za-z0-9\s.,!?;:'\"()\[\]{}\-–—_/\\@#$%&*+=<>|~`^]*$")

_TRANSLATION_PROMPT = """Translate the following text into natural English.

Rules:
1. Preserve all named entities, numbers, and dates verbatim.
2. Do not add commentary, explanation, or preamble.
3. Do not wrap the output in quotes or markdown.
4. Return only the translated text, nothing else.
"""


def is_english(text: str) -> bool:
    """Heuristic English check — no LLM call.

    Returns True if every character in `text` is within the basic Latin /
    common punctuation range. Returns False on any diacritic or non-Latin char.

    Known false positives:
      - Vietnamese written without diacritics (rare).
      - English text borrowing accented words ("café") — triggers translation,
        which is harmless: the LLM will return it mostly unchanged.
    """
    if not text:
        return True
    return bool(_ENGLISH_CHAR_RE.match(text))


def translate_to_english(text: str) -> str:
    """Send `text` to the LLM for translation. Returns the translated string.

    Raises on LLM failure — the caller (normalize) handles fallback.
    """
    response = _CLIENT.chat.completions.create(
        model=_MODEL,
        temperature=0.1,
        max_tokens=_MAX_TOKENS,
        messages=[
            {"role": "system", "content": _TRANSLATION_PROMPT},
            {"role": "user", "content": text},
        ],
    )
    return response.choices[0].message.content.strip()


def normalize(text: str) -> str:
    """Public entry point — clean + translate (if needed) → English claim.

    Pipeline:
      1. Strip + collapse whitespace.
      2. Truncate to MAX_INPUT_CHARS (caps LLM cost on long inputs).
      3. If already English → return as-is.
      4. Otherwise → translate via LLM.
      5. On translation failure → return cleaned original (graceful degradation).
    """
    # Step 1-2: clean & truncate
    cleaned = " ".join(text.strip().split())[:_MAX_INPUT_CHARS]
    if not cleaned:
        return ""

    # Step 3: skip LLM if already English
    if is_english(cleaned):
        return cleaned

    # Step 4: translate
    try:
        translated = translate_to_english(cleaned)
        if translated:
            return translated
        print("[preprocessor] LLM returned empty translation, falling back to original.")
    except Exception as e:
        print(f"[preprocessor] Translation failed: {e}")

    # Step 5: fallback
    return cleaned
