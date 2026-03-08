from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class IconRequest(BaseModel):
    name: str
    slug: str


class GeneratedImageResult(BaseModel):
    slug: str
    png_path: str
    prompt_used: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    debug: dict[str, Any] = Field(default_factory=dict)


class QualityMetrics(BaseModel):
    nodes: int = 0
    connected_regions: int = 0
    small_holes: int = 0
    compactness: float = 0.0
    black_ratio: float = 0.0
    raster_similarity: float = 0.0
    smoothness_proxy: float = 0.0


class IconManifestItem(BaseModel):
    name: str
    slug: str
    generated_png: str
    svg: str
    quality: str
    used_manual_override: bool = False
    metrics: QualityMetrics = Field(default_factory=QualityMetrics)


class Manifest(BaseModel):
    project: str = "icon-pack-extension"
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    reference: str
    icons: list[IconManifestItem]

    def write(self, path: str | Path) -> None:
        Path(path).write_text(self.model_dump_json(indent=2), encoding="utf-8")
