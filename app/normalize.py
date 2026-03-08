from __future__ import annotations

from pathlib import Path


def choose_svg_for_preview(slug: str, generated_dir: Path, curated_dir: Path) -> tuple[Path, bool]:
    curated = curated_dir / f"{slug}.svg"
    if curated.exists():
        return curated, True
    return generated_dir / f"{slug}.svg", False
