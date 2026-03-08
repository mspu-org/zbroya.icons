import tempfile
import unittest
from pathlib import Path

from app.preview import render_preview_html


class PreviewTests(unittest.TestCase):
    def test_render_preview(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            tpl_dir = root / "templates"
            tpl_dir.mkdir()
            (tpl_dir / "preview_template.html.j2").write_text("<html>{{ title }} {{ items|length }}</html>", encoding="utf-8")

            out = root / "preview.html"
            render_preview_html(out, tpl_dir, "Test", [{"x": 1}], {"reference": "r"})
            html = out.read_text(encoding="utf-8")
            self.assertIn("Test", html)


if __name__ == "__main__":
    unittest.main()
