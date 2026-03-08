from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from jinja2 import Environment, FileSystemLoader, select_autoescape
from PIL import Image, ImageDraw

from .schemas import IconManifestItem


def render_preview_html(
    output_html: Path,
    template_dir: Path,
    title: str,
    items: list[dict],
    summary: dict,
) -> None:
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(enabled_extensions=("html",)),
    )
    template = env.get_template("preview_template.html.j2")
    html = template.render(title=title, items=items, summary=summary)
    output_html.write_text(html, encoding="utf-8")


def build_preview_sheet(output_png: Path, icons: list[IconManifestItem], card_size: int = 220, cols: int = 3) -> None:
    rows = max(1, math.ceil(len(icons) / cols))
    gap = 20
    margin = 24
    width = margin * 2 + cols * card_size + (cols - 1) * gap
    height = margin * 2 + rows * card_size + (rows - 1) * gap + 40
    image = Image.new("RGB", (width, height), "#e7e7e7")
    draw = ImageDraw.Draw(image)

    for i, item in enumerate(icons):
        c = i % cols
        r = i // cols
        x = margin + c * (card_size + gap)
        y = margin + r * (card_size + gap)
        draw.rectangle((x, y, x + card_size, y + card_size), fill="white", outline="#cfcfcf", width=2)
        draw.text((x + 8, y + card_size + 6), item.slug, fill="#333333")

    output_png.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_png)


def compactness(mask: np.ndarray) -> float:
    area = float((mask > 0).sum())
    if area == 0:
        return 0.0
    perimeter = 0.0
    h, w = mask.shape
    for y in range(h):
        for x in range(w):
            if mask[y, x] == 0:
                continue
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if nx < 0 or ny < 0 or nx >= w or ny >= h or mask[ny, nx] == 0:
                    perimeter += 1
    if perimeter == 0:
        return 0.0
    return float(4 * math.pi * area / (perimeter * perimeter))


def raster_similarity(mask_a: np.ndarray, png_path: Path) -> float:
    img = Image.open(png_path).convert("L")
    arr = np.array(img)
    a = (mask_a > 0).astype(np.uint8)
    b = (arr < 245).astype(np.uint8)
    if a.shape != b.shape:
        b = np.array(Image.fromarray((b * 255).astype(np.uint8)).resize((a.shape[1], a.shape[0]), Image.Resampling.NEAREST))
        b = (b > 0).astype(np.uint8)
    inter = np.logical_and(a, b).sum()
    union = np.logical_or(a, b).sum()
    if union == 0:
        return 1.0
    return float(inter / union)
