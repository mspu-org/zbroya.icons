from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from PIL import Image, ImageDraw

from .config import GenerationConfig
from .prompting import build_prompt, simplify_semantic_request
from .schemas import GeneratedImageResult, IconRequest


class ImageGenerator(Protocol):
    def generate_icon(
        self,
        prompt: str,
        reference_images: list[str] | None,
        output_path: Path,
        size: tuple[int, int] = (1024, 1024),
        transparent_background: bool = True,
    ) -> GeneratedImageResult:
        ...


class MockImageGenerator:
    """Deterministic local generator for MVP/demo without external APIs."""

    def generate_icon(
        self,
        prompt: str,
        reference_images: list[str] | None,
        output_path: Path,
        size: tuple[int, int] = (1024, 1024),
        transparent_background: bool = True,
    ) -> GeneratedImageResult:
        w, h = size
        mode = "RGBA"
        bg = (255, 255, 255, 0) if transparent_background else (255, 255, 255, 255)
        image = Image.new(mode, (w, h), bg)
        draw = ImageDraw.Draw(image)

        token = prompt.lower()
        fill = (26, 26, 26, 255)

        if "factory" in token or "manufacturer" in token:
            draw.rectangle((140, 260, 880, 820), fill=fill)
            draw.polygon(
                [
                    (140, 380),
                    (260, 260),
                    (360, 380),
                    (460, 260),
                    (560, 380),
                    (660, 260),
                    (760, 380),
                    (880, 260),
                    (880, 220),
                    (140, 220),
                ],
                fill=fill,
            )
            draw.rectangle((210, 470, 430, 820), fill=(255, 255, 255, 0))
            draw.rectangle((550, 510, 810, 820), fill=(255, 255, 255, 0))
            draw.rectangle((620, 120, 760, 300), fill=fill)
        elif "rocket" in token or "startup" in token:
            draw.polygon([(512, 100), (700, 560), (512, 880), (324, 560)], fill=fill)
            draw.rectangle((435, 370, 590, 700), fill=(255, 255, 255, 0))
            draw.rectangle((180, 780, 840, 900), fill=fill)
            draw.rectangle((260, 820, 330, 900), fill=(255, 255, 255, 0))
            draw.rectangle((500, 820, 570, 900), fill=(255, 255, 255, 0))
            draw.rectangle((690, 820, 760, 900), fill=(255, 255, 255, 0))
        else:
            draw.ellipse((120, 120, 904, 904), fill=fill)
            draw.pieslice((220, 220, 804, 804), start=40, end=220, fill=(255, 255, 255, 0))
            draw.polygon([(430, 470), (610, 360), (670, 430), (490, 540)], fill=(255, 255, 255, 0))

        output_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(output_path)
        return GeneratedImageResult(
            slug=output_path.stem,
            png_path=str(output_path),
            prompt_used=prompt,
            metadata={"reference_images": reference_images or []},
            debug={"generator": "mock"},
        )


@dataclass
class OpenAIImageGenerator:
    api_key: str
    model: str = "gpt-image-1"
    base_url: str = "https://api.openai.com/v1"

    def generate_icon(
        self,
        prompt: str,
        reference_images: list[str] | None,
        output_path: Path,
        size: tuple[int, int] = (1024, 1024),
        transparent_background: bool = True,
    ) -> GeneratedImageResult:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "size": f"{size[0]}x{size[1]}",
            "background": "transparent" if transparent_background else "white",
            "n": 1,
            "output_format": "png",
        }

        url = f"{self.base_url.rstrip('/')}/images/generations"
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore") if hasattr(exc, "read") else str(exc)
            raise RuntimeError(f"OpenAI image generation failed: HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"OpenAI image generation failed: {exc}") from exc

        data = json.loads(body)
        items = data.get("data") or []
        if not items:
            raise RuntimeError("OpenAI image generation returned no data field")

        image_item = items[0]
        png_bytes: bytes
        if image_item.get("b64_json"):
            png_bytes = base64.b64decode(image_item["b64_json"])
        elif image_item.get("url"):
            with urllib.request.urlopen(image_item["url"], timeout=120) as image_response:
                png_bytes = image_response.read()
        else:
            raise RuntimeError("OpenAI image response missing both b64_json and url")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(png_bytes)

        # Validate output quickly; raises if corrupt.
        Image.open(output_path).verify()

        return GeneratedImageResult(
            slug=output_path.stem,
            png_path=str(output_path),
            prompt_used=prompt,
            metadata={
                "reference_images": reference_images or [],
                "provider": "openai",
                "model": self.model,
            },
            debug={
                "generator": "openai",
                "note": "Reference images are not directly uploaded in this provider path.",
            },
        )


def create_generator(cfg: GenerationConfig) -> ImageGenerator:
    if cfg.provider == "mock":
        return MockImageGenerator()

    if cfg.provider == "openai":
        api_key = os.getenv(cfg.openai_api_key_env, "")
        if not api_key:
            raise RuntimeError(
                f"Generation provider is 'openai' but env var '{cfg.openai_api_key_env}' is empty. "
                f"Set it before running (for example: $env:{cfg.openai_api_key_env}='...')."
            )
        return OpenAIImageGenerator(api_key=api_key, model=cfg.openai_model, base_url=cfg.openai_base_url)

    raise RuntimeError(f"Unsupported generation provider: {cfg.provider}")


def generate_icons(
    requests: list[IconRequest],
    reference_images: list[str] | None,
    out_dir: Path,
    generator: ImageGenerator,
    size: tuple[int, int],
    transparent_background: bool,
    force: bool = False,
) -> list[GeneratedImageResult]:
    out_dir.mkdir(parents=True, exist_ok=True)
    results: list[GeneratedImageResult] = []
    for item in requests:
        output_path = out_dir / f"{item.slug}.png"
        prompt = build_prompt(item.name)
        if output_path.exists() and not force:
            results.append(
                GeneratedImageResult(
                    slug=item.slug,
                    png_path=str(output_path),
                    prompt_used=prompt,
                    metadata={"cached": True},
                    debug={},
                )
            )
            continue
        result = generator.generate_icon(
            prompt=prompt,
            reference_images=reference_images,
            output_path=output_path,
            size=size,
            transparent_background=transparent_background,
        )
        results.append(result)
    return results


def build_semantic_prompts(requests: list[IconRequest]) -> dict[str, str]:
    return {item.slug: simplify_semantic_request(item.name) for item in requests}
