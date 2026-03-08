import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from app.segmentation import preprocess_png
from app.vectorize import vectorize_mask_to_svg


class VectorizeTests(unittest.TestCase):
    def test_preprocess_and_vectorize(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            png = root / "icon.png"
            img = Image.new("RGBA", (128, 128), (255, 255, 255, 0))
            d = ImageDraw.Draw(img)
            d.rectangle((20, 20, 108, 108), fill=(26, 26, 26, 255))
            img.save(png)

            prep = preprocess_png(png, root / "debug", canvas_size=256)
            self.assertGreater(int(np.sum(prep.mask)), 0)

            out_svg = root / "a.svg"
            res = vectorize_mask_to_svg("icon", prep.mask, out_svg)
            self.assertTrue(out_svg.exists())
            self.assertGreaterEqual(res.nodes, 4)


if __name__ == "__main__":
    unittest.main()
