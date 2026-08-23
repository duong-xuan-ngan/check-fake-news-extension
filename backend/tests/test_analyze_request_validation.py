import unittest

from pydantic import ValidationError

from main import AnalyzeRequest


class AnalyzeRequestValidationTests(unittest.TestCase):
    def test_normalizes_a_valid_claim(self):
        request = AnalyzeRequest(text="  5G   causes cancer  ")

        self.assertEqual(request.text, "5G causes cancer")

    def test_rejects_a_short_or_vague_selection(self):
        for text in ("COVID", "Trump dead", "!!!!"):
            with self.subTest(text=text):
                with self.assertRaises(ValidationError):
                    AnalyzeRequest(text=text)

    def test_rejects_a_url_without_a_claim(self):
        with self.assertRaises(ValidationError):
            AnalyzeRequest(text="https://example.com/article")


if __name__ == "__main__":
    unittest.main()
