from __future__ import annotations

import zipfile
from pathlib import Path


def build_zip(output_zip: Path, source_dir: Path) -> None:
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in source_dir.rglob("*"):
            if path.is_file() and path != output_zip:
                zf.write(path, arcname=str(path.relative_to(source_dir)))
