from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from .config import AppConfig
from .intake import build_requests_from_text, write_requests_json
from .pipeline import run_full, run_generate, run_package, run_preview, run_vectorize
from .schemas import Manifest


def _common_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--config", type=str, default=None, help="Path to JSON config")
    p.add_argument("--output", type=str, required=True, help="Output directory")
    p.add_argument("--force", action="store_true", help="Force regenerate cached artifacts")


def _resolve_one_click_output(output: str | None, session_name: str | None) -> Path:
    if output:
        return Path(output)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    session = session_name or f"session_{stamp}"
    return Path("output") / session


def main() -> None:
    parser = argparse.ArgumentParser(prog="icon-pack-tool")
    sub = parser.add_subparsers(dest="command", required=True)

    p_gen = sub.add_parser("generate", help="Generate PNG icons")
    _common_args(p_gen)
    p_gen.add_argument("--reference", required=True)
    p_gen.add_argument("--requests", required=True)

    p_vec = sub.add_parser("vectorize", help="Vectorize generated PNG icons")
    _common_args(p_vec)
    p_vec.add_argument("--requests", required=True)

    p_prev = sub.add_parser("preview", help="Build HTML preview")
    _common_args(p_prev)
    p_prev.add_argument("--reference", required=True)

    p_pack = sub.add_parser("package", help="Build ZIP package")
    _common_args(p_pack)

    p_full = sub.add_parser("full-run", help="Run full pipeline")
    _common_args(p_full)
    p_full.add_argument("--reference", required=True)
    p_full.add_argument("--requests", required=True)

    p_one = sub.add_parser("one-click", help="Single command: entities text -> preview.html")
    p_one.add_argument("--config", type=str, default=None, help="Path to JSON config")
    p_one.add_argument("--reference", required=True, help="Path to reference PNG/SVG")
    p_one.add_argument("--entities", default="", help="Entities list (lines or comma-separated)")
    p_one.add_argument("--entities-file", default=None, help="Path to TXT/MD file with entities")
    p_one.add_argument("--output", default=None, help="Output dir (default: output/session_TIMESTAMP)")
    p_one.add_argument("--session-name", default=None, help="Optional session folder name")
    p_one.add_argument("--force", action="store_true", help="Force regenerate cached artifacts")

    args = parser.parse_args()

    if args.command == "one-click":
        cfg = AppConfig.load(args.config)
        out = _resolve_one_click_output(args.output, args.session_name)

        source_text = args.entities or ""
        if args.entities_file:
            source_text = Path(args.entities_file).read_text(encoding="utf-8")
        requests = build_requests_from_text(source_text)
        if not requests:
            raise SystemExit("No entities found. Pass --entities or --entities-file with at least one item.")

        requests_path = out / "intake" / "requests.generated.json"
        write_requests_json(requests_path, requests)
        manifest = run_full(cfg, Path(args.reference), requests_path, out, force=args.force)

        print(f"Preview ready: {out / 'preview.html'}")
        print(f"Manifest: {out / 'manifest.json'}")
        print(f"Icons: {len(manifest.icons)}")
        return

    cfg = AppConfig.load(args.config)
    out = Path(args.output)

    if args.command == "generate":
        run_generate(cfg, Path(args.reference), Path(args.requests), out, force=args.force)
        return

    if args.command == "vectorize":
        items = run_vectorize(cfg, Path(args.requests), out, force=args.force)
        Manifest(reference="", icons=items).write(out / "manifest.json")
        return

    if args.command == "preview":
        run_preview(cfg, Path(args.reference), out)
        return

    if args.command == "package":
        run_package(out)
        return

    if args.command == "full-run":
        run_full(cfg, Path(args.reference), Path(args.requests), out, force=args.force)
        return


if __name__ == "__main__":
    main()
