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
from dotenv import load_dotenv

from ..schema import (
    AnalysisResult,
    ConfidenceLevel,
    EvidenceStatus,
    FetchedArticle,
    RatingStatus,
    Source,
    Stance,
    Verdict,
)

load_dotenv()
_CLIENT = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)
_MODEL = "openrouter/auto"

_NOT_SURE = AnalysisResult(
    verdict=Verdict.NOT_SURE,
    explanation=(
        "We couldn't gather enough accessible evidence to assess this claim "
        "right now. This does not mean the claim is true or false."
    ),
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
- Weight higher-credibility sources more heavily.
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
            f"rated {article.credibility_score:.2f}"
            if article.credibility_score is not None
            else "unrated"
        )
        blocks.append(
            f"--- Article {i} ---\n"
            f"Domain: {article.domain} (source status: {rating})\n"
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

        return AnalysisResult(
            verdict=Verdict(data["verdict"]),
            explanation=data["explanation"][:500],
            sources=sources,
            confidence=ConfidenceLevel(data["confidence"]),
            evidence_status=(
                EvidenceStatus.RATED
                if any(a.rating_status == RatingStatus.RATED for a in articles)
                else EvidenceStatus.LIMITED_UNRATED
            ),
        )
    except Exception as e:
        print(f"[synthesizer] failed to parse LLM response: {e}")
        return _NOT_SURE


def _apply_evidence_policy(result: AnalysisResult) -> AnalysisResult:
    """Prevent unrated coverage from masquerading as verified evidence."""
    if not result.sources:
        return result

    rated_count = sum(
        source.rating_status == RatingStatus.RATED for source in result.sources
    )
    if rated_count == 0:
        supports = sum(source.stance == Stance.SUPPORTS for source in result.sources)
        contradicts = sum(source.stance == Stance.CONTRADICTS for source in result.sources)
        if supports and not contradicts:
            signal = "The available coverage reports the claim"
        elif contradicts and not supports:
            signal = "The available coverage disputes the claim"
        else:
            signal = "The available coverage does not reach a clear consensus"

        return result.model_copy(update={
            "verdict": Verdict.UNVERIFIED,
            "confidence": ConfidenceLevel.LOW,
            "evidence_status": EvidenceStatus.LIMITED_UNRATED,
            "explanation": (
                f"{signal}, but none of these sources has been independently "
                "rated yet. Treat this as an early signal, not confirmation."
            )[:500],
        })

    # A single independently rated source can be useful, but is not enough for
    # the strongest confidence label by itself.
    if rated_count == 1 and result.confidence == ConfidenceLevel.HIGH:
        return result.model_copy(update={"confidence": ConfidenceLevel.MEDIUM})
    return result


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
        parsed = _parse_response(response.choices[0].message.content, articles)
        return _apply_evidence_policy(parsed)
    except Exception as e:
        print(f"[synthesizer] LLM call failed: {e}")
        return _NOT_SURE
