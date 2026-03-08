from __future__ import annotations

from pathlib import Path
from typing import Protocol

from PIL import Image, ImageDraw

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
            draw.polygon([(140, 380), (260, 260), (360, 380), (460, 260), (560, 380), (660, 260), (760, 380), (880, 260), (880, 220), (140, 220)], fill=fill)
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
