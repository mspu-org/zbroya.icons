from __future__ import annotations

import numpy as np
from PIL import Image


def load_mask(path: str) -> np.ndarray:
    arr = np.array(Image.open(path).convert("L"))
    return (arr > 0).astype(np.uint8)
