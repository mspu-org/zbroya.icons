from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_path(relative_path: str) -> Path:
    """Resolve path for source runs and PyInstaller-frozen runs."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(getattr(sys, "_MEIPASS")) / relative_path
    return Path(relative_path)
