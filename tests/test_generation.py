import unittest
from unittest.mock import patch

from app.config import GenerationConfig
from app.generation import MockImageGenerator, OpenAIImageGenerator, create_generator


class GenerationProviderTests(unittest.TestCase):
    def test_mock_provider(self):
        cfg = GenerationConfig(provider="mock")
        gen = create_generator(cfg)
        self.assertIsInstance(gen, MockImageGenerator)

    def test_openai_provider_without_key(self):
        cfg = GenerationConfig(provider="openai", openai_api_key_env="TEST_OPENAI_KEY")
        with patch.dict("os.environ", {}, clear=False):
            with self.assertRaises(RuntimeError):
                create_generator(cfg)

    def test_openai_provider_with_key(self):
        cfg = GenerationConfig(provider="openai", openai_api_key_env="TEST_OPENAI_KEY")
        with patch.dict("os.environ", {"TEST_OPENAI_KEY": "sk-test"}, clear=False):
            gen = create_generator(cfg)
        self.assertIsInstance(gen, OpenAIImageGenerator)


if __name__ == "__main__":
    unittest.main()
