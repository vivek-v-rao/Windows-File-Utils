#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path


def _human_size(nbytes: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(nbytes)
    unit = 0
    while size >= 1024.0 and unit < len(units) - 1:
        size /= 1024.0
        unit += 1
    if unit == 0:
        return f"{int(size)} {units[unit]}"
    return f"{size:.1f} {units[unit]}"


def _suffix_key(path: Path, *, no_extension_label: str) -> str:
    suffix = path.suffix.lower()
    return suffix if suffix else no_extension_label


def _dir_key(path: Path, root: Path) -> str:
    parent = path.parent
    try:
        rel = parent.relative_to(root)
    except ValueError:
        return str(parent)
    return "." if str(rel) == "." else str(rel)


def build_summary(root: Path) -> dict[str, tuple[int, int, dict[str, int]]]:
    counts: dict[str, int] = defaultdict(int)
    sizes: dict[str, int] = defaultdict(int)
    dir_sizes: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        key = _suffix_key(path, no_extension_label="[no ext]")
        try:
            nbytes = path.stat().st_size
        except OSError:
            continue
        counts[key] += 1
        sizes[key] += nbytes
        dir_sizes[key][_dir_key(path, root)] += nbytes
    return {k: (counts[k], sizes[k], dict(dir_sizes[k])) for k in counts}


def _format_top_dirs(dir_map: dict[str, int], top_n: int) -> str:
    if top_n <= 0 or not dir_map:
        return ""
    rows = sorted(dir_map.items(), key=lambda t: (-t[1], t[0]))[:top_n]
    return "; ".join(f"{dirname}={_human_size(nbytes)}" for dirname, nbytes in rows)


def main() -> int:
    ap = argparse.ArgumentParser(description="Summarize files by extension: count and total size.")
    ap.add_argument("root", nargs="?", default=".", help="Directory to scan recursively. Defaults to current directory.")
    ap.add_argument("--sort", choices=["size-asc", "size-desc", "count", "ext"], default="size-asc", help="Sort output by total size ascending/descending, count, or extension.")
    ap.add_argument("--reverse", action="store_true", help="Reverse the selected sort order.")
    ap.add_argument("--top", type=int, default=0, help="Show only the top N rows. Default 0 means show all.")
    ap.add_argument("--top-dirs", type=int, default=5, help="Number of directories to show per extension, sorted by bytes descending.")
    ap.add_argument("--min-size-mb", type=float, default=100.0, help="Hide extensions smaller than this total size in MB. Use 0 to show all. Default 100.")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    if not root.exists():
        raise SystemExit(f"not found: {root}")
    if not root.is_dir():
        raise SystemExit(f"not a directory: {root}")

    summary = build_summary(root)
    rows = [(ext, count, size, dir_map) for ext, (count, size, dir_map) in summary.items()]
    min_size_bytes = int(args.min_size_mb * 1024 * 1024)
    rows = [row for row in rows if row[2] >= min_size_bytes]
    if args.sort == "size-asc":
        rows.sort(key=lambda t: (t[2], t[1], t[0]), reverse=args.reverse)
    elif args.sort == "size-desc":
        rows.sort(key=lambda t: (t[2], t[1], t[0]), reverse=not args.reverse)
    elif args.sort == "count":
        rows.sort(key=lambda t: (t[1], t[2], t[0]), reverse=not args.reverse)
    else:
        rows.sort(key=lambda t: t[0], reverse=args.reverse)

    if args.top > 0:
        rows = rows[: args.top]

    ext_w = max([len("Extension")] + [len(r[0]) for r in rows]) if rows else len("Extension")
    count_w = max([len("Files")] + [len(str(r[1])) for r in rows]) if rows else len("Files")
    size_w = max([len("Bytes")] + [len(str(r[2])) for r in rows]) if rows else len("Bytes")

    print(f"Root: {root}")
    print(f"{'Extension':<{ext_w}}  {'Files':>{count_w}}  {'Bytes':>{size_w}}  Size      Top dirs")
    print(f"{'-' * ext_w}  {'-' * count_w}  {'-' * size_w}  {'-' * 8}  {'-' * 40}")
    for ext, count, size, dir_map in rows:
        top_dirs = _format_top_dirs(dir_map, args.top_dirs)
        print(f"{ext:<{ext_w}}  {count:>{count_w}}  {size:>{size_w}}  {_human_size(size):<8}  {top_dirs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
