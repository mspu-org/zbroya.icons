from __future__ import annotations

import json
import re
from pathlib import Path

from .schemas import IconRequest


def slugify(value: str) -> str:
    v = value.strip().lower()
    v = re.sub(r"[^a-z0-9\s-]", "", v)
    v = re.sub(r"[\s-]+", "_", v).strip("_")
    return v or "icon"


def parse_entities(text: str) -> list[str]:
    raw = text.strip()
    if not raw:
        return []

    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    if len(lines) == 1 and any(sep in lines[0] for sep in [",", ";"]):
        lines = [part.strip() for part in re.split(r"[,;]", lines[0]) if part.strip()]

    cleaned: list[str] = []
    for line in lines:
        line = re.sub(r"^[\-\*\u2022\d\.\)\(\s]+", "", line).strip()
        if line:
            cleaned.append(line)

    dedup: list[str] = []
    seen = set()
    for item in cleaned:
        k = item.casefold()
        if k in seen:
            continue
        seen.add(k)
        dedup.append(item)
    return dedup


def build_requests_from_text(text: str) -> list[IconRequest]:
    entities = parse_entities(text)
    results: list[IconRequest] = []
    used_slugs: set[str] = set()
    for name in entities:
        base = slugify(name)
        slug = base
        i = 2
        while slug in used_slugs:
            slug = f"{base}_{i}"
            i += 1
        used_slugs.add(slug)
        results.append(IconRequest(name=name, slug=slug))
    return results


def write_requests_json(path: Path, requests: list[IconRequest]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = [r.model_dump() for r in requests]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
