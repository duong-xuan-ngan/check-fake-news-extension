import json
import unittest
from pathlib import Path

from scripts.update_cred1 import normalize_domain


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATASET_PATH = PROJECT_ROOT / "data" / "cred1_compact.json"


class Cred1DatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))

    def test_dataset_has_expected_coverage_and_compact_schema(self):
        self.assertGreaterEqual(len(self.dataset), 2_600)
        self.assertLessEqual(len(self.dataset), 2_674)
        for domain, metadata in self.dataset.items():
            self.assertEqual(domain, normalize_domain(domain))
            self.assertIn(metadata["c"], {"c", "f", "m", "r", "s", "u"})
            self.assertGreaterEqual(metadata["s"], 0)
            self.assertLessEqual(metadata["s"], 1)
            self.assertGreaterEqual(metadata["n"], 1)

    def test_known_risk_domain_and_neutral_absence(self):
        self.assertLess(self.dataset["infowars.com"]["s"], 0.5)
        self.assertNotIn("example.com", self.dataset)

    def test_url_aliases_normalize_to_hostnames(self):
        self.assertEqual(normalize_domain("https://www.example.com/news"), "example.com")
        self.assertEqual(normalize_domain("anews24.org/"), "anews24.org")


if __name__ == "__main__":
    unittest.main()
