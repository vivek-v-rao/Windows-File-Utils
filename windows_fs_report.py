from __future__ import annotations

from pathlib import PureWindowsPath
import ntpath


def human_size(num_bytes: int) -> str:
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024.0 or unit == "TB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024.0
    return f"{num_bytes} B"


def bucket_relative_path(rel_dir: str, max_depth: int) -> str:
    if max_depth == 0:
        return "."
    parts = [p for p in str(PureWindowsPath(rel_dir)).split("\\") if p and p != "."]
    if not parts:
        return ""
    return "\\".join(parts[:max_depth])


def common_base_path(paths: list[str]) -> str:
    if not paths:
        return ""
    try:
        return ntpath.commonpath(paths)
    except ValueError:
        return ""


def relative_to_base(paths: list[str], base: str) -> list[str]:
    if not base:
        return list(paths)
    return [ntpath.relpath(path, base) for path in paths]
