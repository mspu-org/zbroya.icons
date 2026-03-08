from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

try:
    import cv2  # type: ignore
except Exception:
    cv2 = None


@dataclass
class VectorizeResult:
    slug: str
    svg_path: str
    nodes: int
    contour_count: int
    hole_count: int


def _contours_cv(mask: np.ndarray, approx_epsilon: float):
    contours, hierarchy = cv2.findContours(mask.astype(np.uint8), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    parents = hierarchy[0] if hierarchy is not None else []
    paths = []
    nodes = 0
    hole_count = 0
    for i, cnt in enumerate(contours):
        peri = cv2.arcLength(cnt, True)
        eps = max(0.1, approx_epsilon / 100.0 * peri)
        approx = cv2.approxPolyDP(cnt, eps, True)
        pts = approx[:, 0, :]
        if len(pts) < 3:
            continue
        parent_idx = int(parents[i][3]) if len(parents) else -1
        if parent_idx >= 0:
            hole_count += 1
        commands = [f"M {int(pts[0][0])} {int(pts[0][1])}"]
        for p in pts[1:]:
            commands.append(f"L {int(p[0])} {int(p[1])}")
        commands.append("Z")
        nodes += len(pts)
        paths.append(" ".join(commands))
    return paths, nodes, len(contours), hole_count


def _pixel_rect_paths(mask: np.ndarray):
    ys, xs = np.where(mask > 0)
    paths = []
    for x, y in zip(xs, ys):
        paths.append(f"M {x} {y} L {x+1} {y} L {x+1} {y+1} L {x} {y+1} Z")
    return paths, len(paths) * 4, 1, 0


def vectorize_mask_to_svg(
    slug: str,
    mask: np.ndarray,
    output_svg: Path,
    viewbox_size: int = 512,
    fill_color: str = "#1A1A1A",
    approx_epsilon: float = 1.5,
) -> VectorizeResult:
    output_svg.parent.mkdir(parents=True, exist_ok=True)

    if cv2 is not None:
        paths, nodes, contour_count, hole_count = _contours_cv(mask, approx_epsilon)
    else:
        paths, nodes, contour_count, hole_count = _pixel_rect_paths(mask)

    h, w = mask.shape
    scale_x = viewbox_size / max(1, w)
    scale_y = viewbox_size / max(1, h)
    scale = min(scale_x, scale_y)

    scaled_paths = []
    for d in paths:
        parts = d.split()
        out = []
        i = 0
        while i < len(parts):
            token = parts[i]
            if token in {"M", "L"}:
                x = float(parts[i + 1]) * scale
                y = float(parts[i + 2]) * scale
                out.extend([token, f"{x:.2f}", f"{y:.2f}"])
                i += 3
            else:
                out.append(token)
                i += 1
        scaled_paths.append(" ".join(out))

    d_all = " ".join(scaled_paths) if scaled_paths else ""
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {viewbox_size} {viewbox_size}">'
        f'<path d="{d_all}" fill="{fill_color}" fill-rule="evenodd"/></svg>'
    )
    output_svg.write_text(svg, encoding="utf-8")

    return VectorizeResult(
        slug=slug,
        svg_path=str(output_svg),
        nodes=nodes,
        contour_count=contour_count,
        hole_count=hole_count,
    )
