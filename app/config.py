from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class GenerationConfig(BaseModel):
    provider: Literal["mock", "openai"] = "mock"
    transparent_background: bool = True
    size: int = 1024
    single_icon_mode: bool = True
    openai_model: str = "gpt-image-1"
    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key_env: str = "OPENAI_API_KEY"


class VectorizationConfig(BaseModel):
    use_potrace: bool = True
    turdsize: int = 8
    approx_epsilon: float = 1.5
    keep_holes_above_area: int = 60


class CleanupConfig(BaseModel):
    remove_components_below_area: int = 40
    close_kernel: int = 3


class QualityConfig(BaseModel):
    max_nodes_warning: int = 1200
    max_small_holes_warning: int = 12


class PreviewConfig(BaseModel):
    card_size: int = 220
    background: str = "#e7e7e7"


class AppConfig(BaseModel):
    canvas_size: int = 512
    fill_color: str = "#1A1A1A"
    padding_ratio: float = 0.12
    mode: Literal["fast", "curated"] = "curated"
    generation: GenerationConfig = Field(default_factory=GenerationConfig)
    vectorization: VectorizationConfig = Field(default_factory=VectorizationConfig)
    cleanup: CleanupConfig = Field(default_factory=CleanupConfig)
    quality: QualityConfig = Field(default_factory=QualityConfig)
    preview: PreviewConfig = Field(default_factory=PreviewConfig)

    @classmethod
    def load(cls, path: str | Path | None) -> "AppConfig":
        if path is None:
            return cls()
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.model_validate(data)

    def dump_json(self, path: str | Path) -> None:
        Path(path).write_text(self.model_dump_json(indent=2), encoding="utf-8")
