from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image


@dataclass
class PreprocessResult:
    slug: str
    gray_path: str
    mask_raw_path: str
    mask_clean_path: str
    crop_path: str
    norm_path: str
    mask: np.ndarray


def _binary_threshold(gray: np.ndarray) -> np.ndarray:
    # Otsu-like threshold without external dependency.
    hist = np.bincount(gray.ravel(), minlength=256).astype(np.float64)
    total = gray.size
    sum_total = np.dot(np.arange(256), hist)
    sum_bg = 0.0
    w_bg = 0.0
    var_max = -1.0
    threshold = 127
    for t in range(256):
        w_bg += hist[t]
        if w_bg == 0:
            continue
        w_fg = total - w_bg
        if w_fg == 0:
            break
        sum_bg += t * hist[t]
        m_bg = sum_bg / w_bg
        m_fg = (sum_total - sum_bg) / w_fg
        var_between = w_bg * w_fg * (m_bg - m_fg) ** 2
        if var_between > var_max:
            var_max = var_between
            threshold = t
    # icon expected dark; mask true where icon is present
    return (gray <= threshold).astype(np.uint8)


def _connected_components(mask: np.ndarray) -> list[list[tuple[int, int]]]:
    h, w = mask.shape
    seen = np.zeros_like(mask, dtype=np.uint8)
    comps: list[list[tuple[int, int]]] = []
    for y in range(h):
        for x in range(w):
            if mask[y, x] == 0 or seen[y, x]:
                continue
            stack = [(x, y)]
            seen[y, x] = 1
            comp: list[tuple[int, int]] = []
            while stack:
                cx, cy = stack.pop()
                comp.append((cx, cy))
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if 0 <= nx < w and 0 <= ny < h and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = 1
                        stack.append((nx, ny))
            comps.append(comp)
    return comps


def _close_mask(mask: np.ndarray) -> np.ndarray:
    padded = np.pad(mask, 1, mode="constant")
    out = mask.copy()
    h, w = mask.shape
    for y in range(h):
        for x in range(w):
            win = padded[y : y + 3, x : x + 3]
            if win.sum() >= 5:
                out[y, x] = 1
    return out


def preprocess_png(
    png_path: Path,
    output_debug_dir: Path,
    canvas_size: int = 1024,
    padding_ratio: float = 0.12,
    remove_components_below_area: int = 40,
) -> PreprocessResult:
    slug = png_path.stem
    output_debug_dir.mkdir(parents=True, exist_ok=True)

    image = Image.open(png_path).convert("RGBA")
    arr = np.array(image)
    rgb = arr[:, :, :3]
    alpha = arr[:, :, 3]

    gray = (0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]).astype(np.uint8)
    if alpha.max() > 0:
        gray = np.where(alpha > 0, gray, 255).astype(np.uint8)

    raw_mask = _binary_threshold(gray)
    clean_mask = _close_mask(raw_mask)

    components = _connected_components(clean_mask)
    filtered = [c for c in components if len(c) >= remove_components_below_area]
    if not filtered:
        filtered = components

    chosen = max(filtered, key=len) if filtered else []
    main_mask = np.zeros_like(clean_mask)
    for x, y in chosen:
        main_mask[y, x] = 1

    ys, xs = np.where(main_mask > 0)
    if len(xs) == 0:
        ys, xs = np.where(clean_mask > 0)
        main_mask = clean_mask

    min_x, max_x = int(xs.min()), int(xs.max())
    min_y, max_y = int(ys.min()), int(ys.max())

    crop = main_mask[min_y : max_y + 1, min_x : max_x + 1]
    pad = max(8, int(max(crop.shape) * padding_ratio))
    crop_pad = np.pad(crop, pad, mode="constant")

    canvas = np.zeros((canvas_size, canvas_size), dtype=np.uint8)
    h, w = crop_pad.shape
    scale = min((canvas_size * (1 - 2 * padding_ratio)) / w, (canvas_size * (1 - 2 * padding_ratio)) / h)
    new_w = max(1, int(w * scale))
    new_h = max(1, int(h * scale))

    resized = np.array(Image.fromarray((crop_pad * 255).astype(np.uint8)).resize((new_w, new_h), Image.Resampling.NEAREST))
    resized = (resized > 0).astype(np.uint8)
    off_x = (canvas_size - new_w) // 2
    off_y = (canvas_size - new_h) // 2
    canvas[off_y : off_y + new_h, off_x : off_x + new_w] = resized

    gray_path = output_debug_dir / f"{slug}_gray.png"
    mask_raw_path = output_debug_dir / f"{slug}_mask_raw.png"
    mask_clean_path = output_debug_dir / f"{slug}_mask_clean.png"
    crop_path = output_debug_dir / f"{slug}_crop.png"
    norm_path = output_debug_dir / f"{slug}_norm.png"

    Image.fromarray(gray).save(gray_path)
    Image.fromarray((raw_mask * 255).astype(np.uint8)).save(mask_raw_path)
    Image.fromarray((main_mask * 255).astype(np.uint8)).save(mask_clean_path)
    Image.fromarray((crop_pad * 255).astype(np.uint8)).save(crop_path)
    Image.fromarray((canvas * 255).astype(np.uint8)).save(norm_path)

    return PreprocessResult(
        slug=slug,
        gray_path=str(gray_path),
        mask_raw_path=str(mask_raw_path),
        mask_clean_path=str(mask_clean_path),
        crop_path=str(crop_path),
        norm_path=str(norm_path),
        mask=canvas,
    )
