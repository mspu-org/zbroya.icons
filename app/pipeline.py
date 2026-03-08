from __future__ import annotations

import json
import shutil
from pathlib import Path

from .config import AppConfig
from .generation import create_generator, generate_icons
from .normalize import choose_svg_for_preview
from .packaging import build_zip
from .preview import build_preview_sheet, compactness, raster_similarity, render_preview_html
from .runtime import resolve_project_path
from .schemas import IconManifestItem, IconRequest, Manifest, QualityMetrics
from .segmentation import preprocess_png
from .utils.logging import get_logger
from .vectorize import vectorize_mask_to_svg


def _load_requests(requests_path: Path) -> list[IconRequest]:
    data = json.loads(requests_path.read_text(encoding="utf-8"))
    return [IconRequest.model_validate(item) for item in data]


def _classify(metrics: QualityMetrics, cfg: AppConfig) -> str:
    if metrics.nodes > cfg.quality.max_nodes_warning * 1.8:
        return "bad_trace"
    if metrics.nodes > cfg.quality.max_nodes_warning:
        return "needs_cleanup"
    if metrics.small_holes > cfg.quality.max_small_holes_warning:
        return "needs_cleanup"
    if metrics.raster_similarity < 0.35:
        return "bad_trace"
    if metrics.black_ratio < 0.05 or metrics.black_ratio > 0.85:
        return "needs_cleanup"
    return "good"


def _quality_rank(status: str) -> int:
    if status == "good":
        return 3
    if status == "needs_cleanup":
        return 2
    return 1


def _build_metrics(preprocess_mask, vec, source_png: Path) -> QualityMetrics:
    black_ratio = float((preprocess_mask > 0).sum() / preprocess_mask.size)
    return QualityMetrics(
        nodes=vec.nodes,
        connected_regions=max(1, vec.contour_count - vec.hole_count),
        small_holes=vec.hole_count,
        compactness=compactness(preprocess_mask),
        black_ratio=black_ratio,
        raster_similarity=raster_similarity(preprocess_mask, source_png),
        smoothness_proxy=max(0.0, min(1.0, 1.0 - vec.nodes / 5000.0)),
    )


def run_generate(
    cfg: AppConfig,
    reference: Path,
    requests_path: Path,
    output_dir: Path,
    force: bool = False,
) -> list[Path]:
    logger = get_logger()
    requests = _load_requests(requests_path)
    generated_dir = output_dir / "generated_png"
    generator = create_generator(cfg.generation)
    reference_images = [str(reference)] if reference.exists() else []
    results = generate_icons(
        requests=requests,
        reference_images=reference_images,
        out_dir=generated_dir,
        generator=generator,
        size=(cfg.generation.size, cfg.generation.size),
        transparent_background=cfg.generation.transparent_background,
        force=force,
    )
    logger.info("generated %s PNG icons", len(results))
    return [Path(item.png_path) for item in results]


def run_vectorize(
    cfg: AppConfig,
    requests_path: Path,
    output_dir: Path,
    force: bool = False,
) -> list[IconManifestItem]:
    logger = get_logger()
    requests = _load_requests(requests_path)
    generated_dir = output_dir / "generated_png"
    debug_dir = output_dir / "debug"
    svg_dir = output_dir / "generated_svgs"

    items: list[IconManifestItem] = []
    for req in requests:
        png_path = generated_dir / f"{req.slug}.png"
        if not png_path.exists():
            continue

        preprocess = preprocess_png(
            png_path=png_path,
            output_debug_dir=debug_dir,
            canvas_size=cfg.generation.size,
            padding_ratio=cfg.padding_ratio,
            remove_components_below_area=cfg.cleanup.remove_components_below_area,
        )

        out_svg = svg_dir / f"{req.slug}.svg"
        vec = vectorize_mask_to_svg(
            slug=req.slug,
            mask=preprocess.mask,
            output_svg=out_svg,
            viewbox_size=cfg.canvas_size,
            fill_color=cfg.fill_color,
            approx_epsilon=cfg.vectorization.approx_epsilon,
        )

        metrics = _build_metrics(preprocess.mask, vec, png_path)
        quality = _classify(metrics, cfg)

        # Curated mode: automatic retry for bad traces with stricter cleanup.
        if cfg.mode == "curated" and quality == "bad_trace":
            preprocess_retry = preprocess_png(
                png_path=png_path,
                output_debug_dir=debug_dir,
                canvas_size=cfg.generation.size,
                padding_ratio=min(cfg.padding_ratio + 0.04, 0.2),
                remove_components_below_area=max(80, cfg.cleanup.remove_components_below_area * 2),
            )
            retry_svg = svg_dir / f"{req.slug}.retry.svg"
            vec_retry = vectorize_mask_to_svg(
                slug=req.slug,
                mask=preprocess_retry.mask,
                output_svg=retry_svg,
                viewbox_size=cfg.canvas_size,
                fill_color=cfg.fill_color,
                approx_epsilon=cfg.vectorization.approx_epsilon * 1.8,
            )
            metrics_retry = _build_metrics(preprocess_retry.mask, vec_retry, png_path)
            quality_retry = _classify(metrics_retry, cfg)

            prefer_retry = False
            if _quality_rank(quality_retry) > _quality_rank(quality):
                prefer_retry = True
            elif metrics_retry.raster_similarity > metrics.raster_similarity + 0.05:
                prefer_retry = True
            elif metrics_retry.nodes < max(1, int(metrics.nodes * 0.7)):
                prefer_retry = True

            if prefer_retry:
                shutil.copy2(retry_svg, out_svg)
                metrics = metrics_retry
                quality = quality_retry
                logger.info("auto-retry improved trace for %s: %s -> %s", req.slug, "bad_trace", quality)

            if retry_svg.exists():
                retry_svg.unlink(missing_ok=True)

        items.append(
            IconManifestItem(
                name=req.name,
                slug=req.slug,
                generated_png=str(png_path.relative_to(output_dir)),
                svg=str(out_svg.relative_to(output_dir)),
                quality=quality,
                used_manual_override=False,
                metrics=metrics,
            )
        )
    return items


def run_preview(
    cfg: AppConfig,
    reference: Path,
    output_dir: Path,
    items: list[IconManifestItem] | None = None,
) -> Path:
    manifest_path = output_dir / "manifest.json"
    if items is None and manifest_path.exists():
        manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
        items = [IconManifestItem.model_validate(i) for i in manifest_data.get("icons", [])]
    items = items or []

    generated_dir = output_dir / "generated_svgs"
    curated_dir = output_dir / "curated_svgs"
    curated_dir.mkdir(parents=True, exist_ok=True)

    preview_items = []
    for item in items:
        svg_path, overridden = choose_svg_for_preview(item.slug, generated_dir, curated_dir)
        if not svg_path.exists():
            continue

        svg_content = svg_path.read_text(encoding="utf-8")
        badge = "Manual override" if overridden else ("OK" if item.quality == "good" else "Needs cleanup")
        preview_items.append(
            {
                "title": item.name,
                "slug": item.slug,
                "filename": svg_path.name,
                "quality": item.quality,
                "badge": badge,
                "svg_inline": svg_content,
                "metrics": item.metrics.model_dump(),
                "manual_override": overridden,
                "png": item.generated_png,
            }
        )
        item.used_manual_override = overridden
        item.svg = str(svg_path.relative_to(output_dir))

    summary = {
        "total": len(preview_items),
        "good": len([i for i in items if i.quality == "good"]),
        "needs_cleanup": len([i for i in items if i.quality == "needs_cleanup"]),
        "bad_trace": len([i for i in items if i.quality == "bad_trace"]),
        "manual_overrides": len([i for i in items if i.used_manual_override]),
        "reference": str(reference),
    }

    render_preview_html(
        output_html=output_dir / "preview.html",
        template_dir=resolve_project_path("templates"),
        title="Icon Pack Extension Preview",
        items=preview_items,
        summary=summary,
    )
    build_preview_sheet(output_png=output_dir / "preview_sheet.png", icons=items, card_size=cfg.preview.card_size)

    # Persist override flags and selected SVG paths for GUI/CLI refreshes.
    Manifest(reference=str(reference), icons=items).write(manifest_path)
    return output_dir / "preview.html"


def run_package(output_dir: Path) -> Path:
    zip_path = output_dir / "icon_pack_bundle.zip"
    build_zip(zip_path, output_dir)
    return zip_path


def run_full(
    cfg: AppConfig,
    reference: Path,
    requests_path: Path,
    output_dir: Path,
    force: bool = False,
) -> Manifest:
    output_dir.mkdir(parents=True, exist_ok=True)
    run_generate(cfg, reference, requests_path, output_dir, force=force)
    items = run_vectorize(cfg, requests_path, output_dir, force=force)

    manifest = Manifest(reference=str(reference), icons=items)
    manifest.write(output_dir / "manifest.json")

    run_preview(cfg, reference, output_dir, items=items)
    run_package(output_dir)

    # Re-read manifest to ensure persisted override fields are reflected.
    manifest_data = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    return Manifest.model_validate(manifest_data)
