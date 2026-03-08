import unittest

from app.prompting import build_prompt, simplify_semantic_request


class PromptingTests(unittest.TestCase):
    def test_simplifier_known_label(self):
        out = simplify_semantic_request("Defense Equipment Manufacturer")
        self.assertIn("factory silhouette", out)

    def test_prompt_contains_avoid_block(self):
        prompt = build_prompt("Dual-Use Technology")
        self.assertIn("Avoid:", prompt)
        self.assertIn("cohesive", prompt)


if __name__ == "__main__":
    unittest.main()
