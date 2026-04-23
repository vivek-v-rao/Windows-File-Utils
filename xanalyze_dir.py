#!/usr/bin/env python3
"""
Analyze Windows disk usage from a text file produced by: dir /s

Example:
    python analyze_dir_s.py partial_file_list.txt
    python analyze_dir_s.py partial_file_list.txt --focus c:\backtests --csv-prefix report
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import PureWindowsPath
from typing import Iterable, Optional

from windows_dir_parser import FileEntry, parse_dir_s_file
from windows_fs_report import human_size

ARCHIVE_EXTS = {".zip", ".7z", ".rar", ".tar", ".gz", ".bz2", ".xz", ".iso", ".img"}
REPORT_EXTS = {".xlsx", ".xls", ".xlsm", ".csv", ".pdf"}
CACHE_MARKERS = {"__pycache__", ".mypy_cache", ".cache", "cache", "tmp", "temp"}


@dataclass
class CleanupCandidate:
    category: str
    path: str
    size: int
    reason: str

def is_under(path: str, root: Optional[str]) -> bool:
    if not root:
        return True
    p = path.lower()
    r = root.lower().rstrip("\\")
    return p == r or p.startswith(r + "\\")


def aggregate_directories(files: Iterable[FileEntry], focus: Optional[str]) -> tuple[dict[str, int], dict[str, int]]:
    direct_sizes: dict[str, int] = defaultdict(int)
    recursive_sizes: dict[str, int] = defaultdict(int)

    for entry in files:
        if not is_under(entry.path, focus):
            continue

        direct_sizes[entry.directory] += entry.size

        current = PureWindowsPath(entry.directory)
        while True:
            current_str = str(current)
            if is_under(current_str, focus):
                recursive_sizes[current_str] += entry.size

            anchor = current.anchor.rstrip("\\")
            current_cmp = current_str.rstrip("\\")
            if current_cmp.lower() == anchor.lower():
                break
            current = current.parent

    return dict(direct_sizes), dict(recursive_sizes)


def aggregate_extensions(files: Iterable[FileEntry], focus: Optional[str]) -> dict[str, int]:
    totals: dict[str, int] = defaultdict(int)
    for entry in files:
        if is_under(entry.path, focus):
            totals[entry.ext or "[no extension]"] += entry.size
    return dict(totals)


def top_items(mapping: dict[str, int], limit: int) -> list[tuple[str, int]]:
    return sorted(mapping.items(), key=lambda item: item[1], reverse=True)[:limit]


def find_cleanup_candidates(
    files: list[FileEntry],
    recursive_sizes: dict[str, int],
    focus: Optional[str],
    archive_threshold_mb: float,
    old_file_threshold_mb: float,
    old_years: int,
    cache_threshold_mb: float,
) -> list[CleanupCandidate]:
    candidates: list[CleanupCandidate] = []

    archive_threshold = int(archive_threshold_mb * 1024 * 1024)
    old_file_threshold = int(old_file_threshold_mb * 1024 * 1024)
    cache_threshold = int(cache_threshold_mb * 1024 * 1024)
    now = datetime.now()

    # Large archives
    for entry in files:
        if not is_under(entry.path, focus):
            continue
        if entry.ext in ARCHIVE_EXTS and entry.size >= archive_threshold:
            candidates.append(
                CleanupCandidate(
                    category="archive",
                    path=entry.path,
                    size=entry.size,
                    reason="Large archive; delete if it is just a backup copy or move it off this drive.",
                )
            )

    # Recycle Bin
    recycle_total = sum(
        entry.size for entry in files
        if is_under(entry.path, focus) and entry.path.lower().startswith(r"c:\$recycle.bin")
    )
    if recycle_total:
        candidates.append(
            CleanupCandidate(
                category="recycle_bin",
                path=r"c:\$Recycle.Bin",
                size=recycle_total,
                reason="Files already deleted once; emptying the Recycle Bin usually reclaims this immediately.",
            )
        )

    # Cache-like directories
    for directory, total_size in recursive_sizes.items():
        parts = {part.lower() for part in PureWindowsPath(directory).parts}
        if parts & CACHE_MARKERS and total_size >= cache_threshold and is_under(directory, focus):
            candidates.append(
                CleanupCandidate(
                    category="cache_dir",
                    path=directory,
                    size=total_size,
                    reason="Cache/temp directory; usually safer to clear than project data, but still review first.",
                )
            )

    # Old large files
    for entry in files:
        if not is_under(entry.path, focus):
            continue
        if entry.modified is None:
            continue
        age_years = (now - entry.modified).days / 365.25
        if age_years >= old_years and entry.size >= old_file_threshold:
            candidates.append(
                CleanupCandidate(
                    category="old_large_file",
                    path=entry.path,
                    size=entry.size,
                    reason=f"Old large file (~{age_years:.1f} years old); good candidate to archive or move elsewhere.",
                )
            )

    # Report-heavy directories
    report_dir_sizes: dict[str, int] = defaultdict(int)
    report_dir_counts: dict[str, int] = defaultdict(int)
    for entry in files:
        if not is_under(entry.path, focus):
            continue
        if entry.ext in REPORT_EXTS:
            report_dir_sizes[entry.directory] += entry.size
            report_dir_counts[entry.directory] += 1

    for directory, total_size in report_dir_sizes.items():
        if total_size >= 100 * 1024 * 1024 and report_dir_counts[directory] >= 4:
            candidates.append(
                CleanupCandidate(
                    category="report_dir",
                    path=directory,
                    size=total_size,
                    reason=f"Contains many large report/output files ({report_dir_counts[directory]} files).",
                )
            )

    # Deduplicate by path/category pair and keep the biggest categories first.
    dedup: dict[tuple[str, str], CleanupCandidate] = {}
    for candidate in candidates:
        dedup[(candidate.category, candidate.path)] = candidate

    return sorted(dedup.values(), key=lambda c: c.size, reverse=True)


def write_csv_reports(
    csv_prefix: str,
    files: list[FileEntry],
    recursive_sizes: dict[str, int],
    ext_sizes: dict[str, int],
    focus: Optional[str],
) -> None:
    filtered_files = [f for f in files if is_under(f.path, focus)]

    with open(f"{csv_prefix}_files.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["path", "directory", "name", "size_bytes", "extension", "modified"])
        for entry in sorted(filtered_files, key=lambda x: x.size, reverse=True):
            writer.writerow([
                entry.path,
                entry.directory,
                entry.name,
                entry.size,
                entry.ext or "",
                entry.modified.isoformat(sep=" ") if entry.modified else "",
            ])

    with open(f"{csv_prefix}_directories.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["directory", "recursive_size_bytes"])
        for directory, size in sorted(recursive_sizes.items(), key=lambda item: item[1], reverse=True):
            writer.writerow([directory, size])

    with open(f"{csv_prefix}_extensions.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["extension", "size_bytes"])
        for ext, size in sorted(ext_sizes.items(), key=lambda item: item[1], reverse=True):
            writer.writerow([ext, size])


def print_section(title: str) -> None:
    print()
    print(title)
    print("-" * len(title))


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze disk usage from Windows dir /s output.")
    parser.add_argument("input_file", help="Path to the text file produced by dir /s")
    parser.add_argument("--focus", help=r"Only analyze files under this path, e.g. c:\backtests")
    parser.add_argument("--top-files", type=int, default=20, help="How many largest files to show")
    parser.add_argument("--top-dirs", type=int, default=20, help="How many largest directories to show")
    parser.add_argument("--top-exts", type=int, default=15, help="How many extensions to show")
    parser.add_argument("--archive-threshold-mb", type=float, default=100.0, help="Minimum archive size to flag")
    parser.add_argument("--old-file-threshold-mb", type=float, default=50.0, help="Minimum old file size to flag")
    parser.add_argument("--old-years", type=int, default=3, help="Minimum age in years for old-file candidates")
    parser.add_argument("--cache-threshold-mb", type=float, default=25.0, help="Minimum cache directory size to flag")
    parser.add_argument("--csv-prefix", help="Write CSV reports using this file prefix")
    args = parser.parse_args()

    files = parse_dir_s_file(args.input_file).files
    if not files:
        raise SystemExit("No files were parsed. Check that the input really came from 'dir /s'.")

    direct_sizes, recursive_sizes = aggregate_directories(files, args.focus)
    ext_sizes = aggregate_extensions(files, args.focus)
    filtered_files = [f for f in files if is_under(f.path, args.focus)]
    total_size = sum(f.size for f in filtered_files)

    print(f"Parsed {len(filtered_files):,} files totaling {human_size(total_size)}")
    if args.focus:
        print(f"Focus path: {args.focus}")

    print_section("Largest directories (recursive)")
    for directory, size in top_items(recursive_sizes, args.top_dirs):
        print(f"{human_size(size):>10}  {directory}")

    print_section("Largest files")
    for entry in sorted(filtered_files, key=lambda x: x.size, reverse=True)[: args.top_files]:
        print(f"{human_size(entry.size):>10}  {entry.path}")

    print_section("Largest extensions")
    for ext, size in top_items(ext_sizes, args.top_exts):
        label = ext if ext else "[no extension]"
        print(f"{human_size(size):>10}  {label}")

    candidates = find_cleanup_candidates(
        files=files,
        recursive_sizes=recursive_sizes,
        focus=args.focus,
        archive_threshold_mb=args.archive_threshold_mb,
        old_file_threshold_mb=args.old_file_threshold_mb,
        old_years=args.old_years,
        cache_threshold_mb=args.cache_threshold_mb,
    )

    print_section("Cleanup candidates to review")
    if not candidates:
        print("No candidates matched the current thresholds.")
    else:
        for candidate in candidates[:25]:
            print(f"[{candidate.category:<13}] {human_size(candidate.size):>10}  {candidate.path}")
            print(f"    {candidate.reason}")

    if args.csv_prefix:
        write_csv_reports(args.csv_prefix, files, recursive_sizes, ext_sizes, args.focus)
        print()
        print(f"Wrote CSV reports with prefix: {args.csv_prefix}")


if __name__ == "__main__":
    main()
