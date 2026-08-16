import unittest
from unittest.mock import patch

from app import services


class CredibilityServiceTests(unittest.TestCase):
    def test_known_and_unknown_domain_responses(self):
        with patch("app.services.db.credibility_for", return_value=(0.85, "National News")):
            self.assertEqual(
                services.credibility_response("vnexpress.net"),
                {"credibility_score": 0.85, "category": "National News", "status": "found"},
            )
        with patch("app.services.db.credibility_for", return_value=None):
            self.assertEqual(
                services.credibility_response("unknown.example"),
                {"credibility_score": None, "category": "unknown", "status": "not_found"},
            )


if __name__ == "__main__":
    unittest.main()
