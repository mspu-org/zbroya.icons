from __future__ import annotations


def count_svg_nodes(path_data: str) -> int:
    return path_data.count("L") + path_data.count("M")
