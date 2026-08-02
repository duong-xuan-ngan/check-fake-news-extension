import os
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("OPENROUTER_API_KEY", "test-key")

from ai_core.pipeline import credibility_filter, synthesizer
from ai_core.schema import (
    AnalysisResult,
    ConfidenceLevel,
    EvidenceStatus,
    RatingStatus,
    SearchResult,
    Source,
    Stance,
    Verdict,
)


def search_result(domain: str) -> SearchResult:
    return SearchResult(
        url=f"https://{domain}/article",
        title=f"Article from {domain}",
        snippet="Relevant search result",
        domain=domain,
    )


def source(domain: str, status: RatingStatus, stance: Stance) -> Source:
    return Source(
        url=f"https://{domain}/article",
        title=f"Article from {domain}",
        domain=domain,
        credibility_score=0.8 if status == RatingStatus.RATED else None,
        rating_status=status,
        stance=stance,
    )


class EvidenceSelectionTests(unittest.TestCase):
    def test_selects_rated_first_keeps_unrated_and_drops_low_rated(self):
        results = [
            search_result("unknown.example"),
            search_result("low.example"),
            search_result("rated.example"),
        ]
        ratings = {
            "unknown.example": None,
            "low.example": 0.2,
            "rated.example": 0.9,
        }

        with patch.object(credibility_filter, "_batch_ratings", return_value=ratings):
            selected = credibility_filter.select_evidence(results)

        self.assertEqual([item.domain for item in selected], [
            "rated.example",
            "unknown.example",
        ])
        self.assertEqual(selected[0].rating_status, RatingStatus.RATED)
        self.assertEqual(selected[1].rating_status, RatingStatus.UNRATED)
        self.assertIsNone(selected[1].credibility_score)

    def test_batch_lookup_sends_search_urls_for_candidate_discovery(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "results": [{
                "domain": "new.example",
                "credibility_score": None,
                "rating_status": "unrated",
            }]
        }
        result = search_result("new.example")

        with patch.object(credibility_filter.requests, "post", return_value=response) as post:
            ratings = credibility_filter._batch_ratings([result])

        self.assertEqual(ratings, {"new.example": None})
        self.assertEqual(
            post.call_args.kwargs["json"]["sources"],
            [{"domain": "new.example", "url": result.url}],
        )


class VerdictPolicyTests(unittest.TestCase):
    def test_unrated_only_evidence_cannot_produce_true_or_high_confidence(self):
        result = AnalysisResult(
            verdict=Verdict.TRUE,
            explanation="The claim is supported.",
            sources=[
                source("first.example", RatingStatus.UNRATED, Stance.SUPPORTS),
                source("second.example", RatingStatus.UNRATED, Stance.SUPPORTS),
            ],
            confidence=ConfidenceLevel.HIGH,
            evidence_status=EvidenceStatus.LIMITED_UNRATED,
        )

        protected = synthesizer._apply_evidence_policy(result)

        self.assertEqual(protected.verdict, Verdict.UNVERIFIED)
        self.assertEqual(protected.confidence, ConfidenceLevel.LOW)
        self.assertIn("early signal", protected.explanation)

    def test_one_rated_source_caps_high_confidence_at_medium(self):
        result = AnalysisResult(
            verdict=Verdict.TRUE,
            explanation="The claim is supported.",
            sources=[source("rated.example", RatingStatus.RATED, Stance.SUPPORTS)],
            confidence=ConfidenceLevel.HIGH,
            evidence_status=EvidenceStatus.RATED,
        )

        protected = synthesizer._apply_evidence_policy(result)

        self.assertEqual(protected.verdict, Verdict.TRUE)
        self.assertEqual(protected.confidence, ConfidenceLevel.MEDIUM)


if __name__ == "__main__":
    unittest.main()
