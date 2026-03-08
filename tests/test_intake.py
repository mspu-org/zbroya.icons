import unittest

from app.intake import build_requests_from_text, parse_entities, slugify


class IntakeTests(unittest.TestCase):
    def test_parse_entities_lines(self):
        text = "- A\n- B\n- A"
        self.assertEqual(parse_entities(text), ["A", "B"])

    def test_parse_entities_csv(self):
        text = "A, B; C"
        self.assertEqual(parse_entities(text), ["A", "B", "C"])

    def test_slugify(self):
        self.assertEqual(slugify("Dual-Use Technology"), "dual_use_technology")

    def test_build_requests_deduplicates_entities(self):
        reqs = build_requests_from_text("A\nA")
        self.assertEqual([r.slug for r in reqs], ["a"])


if __name__ == "__main__":
    unittest.main()
