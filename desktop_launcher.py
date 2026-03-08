from __future__ import annotations

from pathlib import Path

from app.desktop_app import launch_desktop


if __name__ == "__main__":
    launch_desktop(config_path="config.json", output_root=Path("output"))
