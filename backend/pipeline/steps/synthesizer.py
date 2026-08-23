"""Step 7: Synthesize fetched articles into a final verdict via OpenRouter.

Single LLM call. LLM only judges stance + verdict — URLs, titles, scores are
filled in from our own FetchedArticle data (anti-hallucination).

To prevent stance label confusion, the prompt forces the LLM to write out
both the article's claim and the user's claim BEFORE picking a stance label.
This structured chain-of-thought makes the comparison explicit.

Falls back to NOT_SURE on any parse/API failure.
"""
import json
import os
import re
from typing import List

from openai import OpenAI

from ..schema import (
    AnalysisResult,
    ConfidenceLevel,
    FetchedArticle,
    RatingStatus,
    Source,
    Stance,
    Verdict,
)

_CLIENT = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)
_MODEL = "openrouter/auto"

_NOT_SURE = AnalysisResult(
    verdict=Verdict.NOT_SURE,
    explanation="Could not retrieve enough evidence to analyze this claim.",
    sources=[],
    confidence=ConfidenceLevel.LOW,
)

_SYSTEM_PROMPT = """You are a fact-checking assistant. You will be given a USER CLAIM and a numbered list of news articles.

Respond ONLY with a valid JSON object in this exact format:
{
  "stances": [
    {
      "article_index": <int matching the article number>,
      "claim_in_article": "<what the article actually says about the topic, in one sentence>",
      "user_claim": "<restate the user's claim, exactly as given>",
      "stance": "SUPPORTS" | "CONTRADICTS" | "NEUTRAL"
    }
  ],
  "verdict": "TRUE" | "FALSE" | "UNVERIFIED" | "NOT_SURE",
  "explanation": "<max 500 chars, user-facing reasoning>",
  "confidence": "HIGH" | "MEDIUM" | "LOW"
}

STANCE RULES (read carefully):
- First write `claim_in_article` (what the article asserts about the topic).
- Then write `user_claim` (what the user said, verbatim).
- Compare them DIRECTLY:
  * If they say the SAME thing → SUPPORTS
  * If they say DIFFERENT or OPPOSITE things → CONTRADICTS
  * If the article doesn't directly address the user's claim → NEUTRAL

Example:
  user_claim: "X is the president of Company A"
  claim_in_article: "X is the president of Company B"
  → These differ, so stance is CONTRADICTS.

VERDICT must align with the stances:
- Most sources CONTRADICT → verdict FALSE
- Most sources SUPPORT → verdict TRUE
- Mixed or no clear evidence → NOT_SURE or UNVERIFIED

TEMPORAL RULE (only when sources directly contradict each other):
- If two or more articles directly contradict each other about the same fact,
  prefer the article with the more recent publication date.
- Articles with no date (shown as "unknown") should not override articles with a known date.
- Mention the date in your explanation when this rule resolves a contradiction.

Other rules:
- A source marked UNRATED is unknown, not trustworthy and not low-credibility.
- If every usable source is UNRATED, confidence must be LOW. State this
  limitation clearly, but do not change a TRUE/FALSE verdict solely because
  the source has not yet been reviewed.
- If only one source is RATED, confidence cannot be HIGH.
- Weight rated sources with higher credibility scores more heavily.
- explanation: factual, concise, user-facing.
- One stances entry per article. article_index must match the number shown.
- Return ONLY the JSON object. No preamble, no markdown.
"""


def _build_evidence_block(articles: List[FetchedArticle]) -> str:
    """Format articles into a numbered evidence block for the LLM prompt."""
    blocks = []
    for i, article in enumerate(articles, start=1):
        date_str = article.published_at.strftime("%Y-%m-%d") if article.published_at else "unknown"
        rating = (
            f"RATED, score {article.credibility_score}"
            if article.rating_status == RatingStatus.RATED
            else "UNRATED (unknown; not automatically trustworthy)"
        )
        blocks.append(
            f"--- Article {i} ---\n"
            f"Domain: {article.domain} ({rating})\n"
            f"Published: {date_str}\n"
            f"Title: {article.title}\n"
            f"Body: {article.body}"
        )
    return "\n\n".join(blocks)


def _parse_response(raw: str, articles: List[FetchedArticle]) -> AnalysisResult:
    """Parse LLM JSON and build AnalysisResult from our own article data + LLM stances.

    URLs/titles/scores come from `articles`, NEVER from the LLM (anti-hallucination).
    Returns _NOT_SURE on any failure.
    """
    try:
        clean = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
        clean = re.sub(r"```json|```", "", clean).strip()
        data = json.loads(clean)

        # Build stance lookup: article_index -> Stance
        stance_by_index = {
            s["article_index"]: Stance(s["stance"])
            for s in data.get("stances", [])
        }

        # Assemble Source objects using our own article data + LLM's stance labels
        sources = []
        for i, article in enumerate(articles, start=1):
            stance = stance_by_index.get(i, Stance.NEUTRAL)
            sources.append(Source(
                url=article.url,
                domain=article.domain,
                title=article.title,
                credibility_score=article.credibility_score,
                rating_status=article.rating_status,
                stance=stance,
                published_at=article.published_at,
            ))

        verdict = Verdict(data["verdict"])
        confidence = ConfidenceLevel(data["confidence"])
        rated_count = sum(
            article.rating_status == RatingStatus.RATED
            for article in articles
        )
        if rated_count == 0:
            # Source rating measures evidence quality, not whether an article's
            # factual statement supports or contradicts the claim. Keep the
            # verdict selected from the evidence, but make confidence low.
            confidence = ConfidenceLevel.LOW
        elif rated_count == 1 and confidence == ConfidenceLevel.HIGH:
            confidence = ConfidenceLevel.MEDIUM

        return AnalysisResult(
            verdict=verdict,
            explanation=data["explanation"][:500],
            sources=sources,
            confidence=confidence,
        )
    except Exception as e:
        print(f"[synthesizer] failed to parse LLM response: {e}")
        return _NOT_SURE


def synthesize(claim: str, articles: List[FetchedArticle]) -> AnalysisResult:
    """Single LLM call: claim + articles -> AnalysisResult.

    Returns _NOT_SURE if articles list is empty or LLM call fails.
    """
    if not articles:
        return _NOT_SURE

    evidence = _build_evidence_block(articles)

    prompt = f"""USER CLAIM: {claim}

Evidence:
{evidence}

Analyze each article against the user's claim and respond with the JSON object."""

    try:
        response = _CLIENT.chat.completions.create(
            model=_MODEL,
            temperature=0.1,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
        return _parse_response(response.choices[0].message.content, articles)
    except Exception as e:
        print(f"[synthesizer] LLM call failed: {e}")
        return _NOT_SURE
