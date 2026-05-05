#!/usr/bin/env python3
"""Compare file membership between two zip archives."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import PurePosixPath


@dataclass(frozen=True)
class ArchiveEntry:
    file_size: int
    compress_size: int | None


def normalize_zip_name(name: str, *, ignore_case: bool) -> str:
    normalized = str(PurePosixPath(name.replace("\\", "/")))
    return normalized.lower() if ignore_case else normalized


def read_files(
    zip_path: str,
    *,
    ignore_case: bool,
    external_fallback: bool,
) -> dict[str, ArchiveEntry]:
    files: dict[str, ArchiveEntry] = {}
    try:
        with zipfile.ZipFile(zip_path) as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                key = normalize_zip_name(info.filename, ignore_case=ignore_case)
                if key in files:
                    print(
                        f"warning: duplicate normalized path in {zip_path!r}: {info.filename!r}",
                        file=sys.stderr,
                    )
                    continue
                files[key] = ArchiveEntry(
                    file_size=info.file_size,
                    compress_size=info.compress_size,
                )
    except FileNotFoundError as exc:
        raise ValueError(f"{zip_path!r} does not exist") from exc
    except zipfile.BadZipFile as exc:
        if external_fallback:
            return read_files_with_external_tools(zip_path, ignore_case=ignore_case)
        size = Path(zip_path).stat().st_size if Path(zip_path).exists() else None
        size_text = f" ({size} bytes)" if size is not None else ""
        raise ValueError(f"{zip_path!r} is not a readable zip file{size_text}") from exc
    return files


def read_files_with_external_tools(zip_path: str, *, ignore_case: bool) -> dict[str, ArchiveEntry]:
    try:
        return read_files_with_7z(zip_path, ignore_case=ignore_case)
    except ValueError as seven_zip_error:
        try:
            return read_files_with_tar(zip_path, ignore_case=ignore_case)
        except ValueError as tar_error:
            raise ValueError(f"{seven_zip_error}; {tar_error}") from tar_error


def find_7z() -> str | None:
    for name in ("7z", "7za", "7zr"):
        path = shutil.which(name)
        if path is not None:
            return path
    for path in (
        r"C:\Program Files\7-Zip\7z.exe",
        r"C:\Program Files (x86)\7-Zip\7z.exe",
    ):
        if Path(path).exists():
            return path
    return None


def read_files_with_7z(zip_path: str, *, ignore_case: bool) -> dict[str, ArchiveEntry]:
    seven_zip = find_7z()
    if seven_zip is None:
        raise ValueError("no 7z executable found for fallback listing")

    proc = subprocess.run(
        [seven_zip, "l", "-slt", zip_path],
        capture_output=True,
        text=True,
        errors="replace",
    )
    files = parse_7z_slt(proc.stdout, zip_path=zip_path, ignore_case=ignore_case)
    if not files:
        size = Path(zip_path).stat().st_size if Path(zip_path).exists() else None
        size_text = f" ({size} bytes)" if size is not None else ""
        raise ValueError(
            f"{zip_path!r} is not a readable zip file{size_text}; 7z fallback could not list it"
        )

    warning = proc.stderr.strip()
    if proc.returncode != 0:
        detail = f": {warning}" if warning else ""
        print(
            f"warning: used 7z fallback for {zip_path!r}, but 7z reported an error{detail}",
            file=sys.stderr,
        )
    else:
        print(f"warning: used 7z fallback for {zip_path!r}", file=sys.stderr)
    return files


def parse_7z_slt(output: str, *, zip_path: str, ignore_case: bool) -> dict[str, ArchiveEntry]:
    files: dict[str, ArchiveEntry] = {}
    record: dict[str, str] = {}
    in_listing = False

    def flush_record() -> None:
        if not record:
            return
        name = record.get("Path")
        size = record.get("Size")
        if name is None or size is None or record.get("Folder") == "+":
            return
        key = normalize_zip_name(name, ignore_case=ignore_case)
        if key in files:
            print(
                f"warning: duplicate normalized path in {zip_path!r}: {name!r}",
                file=sys.stderr,
            )
            return
        packed_size = record.get("Packed Size")
        files[key] = ArchiveEntry(
            file_size=int(size),
            compress_size=int(packed_size) if packed_size else None,
        )

    for line in output.splitlines():
        if line.startswith("----------"):
            in_listing = True
            continue
        if not in_listing:
            continue
        if not line:
            flush_record()
            record = {}
            continue
        if " = " not in line:
            continue
        key, value = line.split(" = ", 1)
        record[key] = value
    flush_record()
    return files


def read_files_with_tar(zip_path: str, *, ignore_case: bool) -> dict[str, ArchiveEntry]:
    tar = shutil.which("tar")
    if tar is None:
        size = Path(zip_path).stat().st_size if Path(zip_path).exists() else None
        size_text = f" ({size} bytes)" if size is not None else ""
        raise ValueError(
            f"{zip_path!r} is not a readable zip file{size_text}; no tar executable found "
            "for fallback listing"
        )

    files: dict[str, ArchiveEntry] = {}
    listing_re = re.compile(
        r"^(?P<mode>\S+)\s+\d+\s+\S+\s+\S+\s+(?P<size>\d+)\s+"
        r"\S+\s+\d+\s+\S+\s+(?P<name>.+)$"
    )
    proc = subprocess.run(
        [tar, "-tvf", zip_path],
        capture_output=True,
        text=True,
        errors="replace",
    )
    if not proc.stdout:
        size = Path(zip_path).stat().st_size if Path(zip_path).exists() else None
        size_text = f" ({size} bytes)" if size is not None else ""
        raise ValueError(
            f"{zip_path!r} is not a readable zip file{size_text}; tar fallback could not list it"
        )

    for line in proc.stdout.splitlines():
        match = listing_re.match(line)
        if not match:
            continue
        if match.group("mode").startswith("d"):
            continue
        key = normalize_zip_name(match.group("name"), ignore_case=ignore_case)
        if key in files:
            print(
                f"warning: duplicate normalized path in {zip_path!r}: {match.group('name')!r}",
                file=sys.stderr,
            )
            continue
        files[key] = ArchiveEntry(file_size=int(match.group("size")), compress_size=None)

    warning = proc.stderr.strip()
    if proc.returncode != 0:
        detail = f": {warning}" if warning else ""
        print(
            f"warning: used tar fallback for {zip_path!r}, but tar reported an error{detail}",
            file=sys.stderr,
        )
    else:
        print(f"warning: used tar fallback for {zip_path!r}", file=sys.stderr)
    return files


def format_bytes(num_bytes: int) -> str:
    units = ("B", "KiB", "MiB", "GiB", "TiB")
    value = float(num_bytes)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{num_bytes} {unit}"
            return f"{value:.2f} {unit}"
        value /= 1024
    raise AssertionError("unreachable")


def format_optional_bytes(num_bytes: int | None) -> str:
    if num_bytes is None:
        return "unavailable"
    return f"{num_bytes} bytes ({format_bytes(num_bytes)})"


def sum_compressed(files: dict[str, ArchiveEntry], names: set[str]) -> int | None:
    values = [files[name].compress_size for name in names]
    if any(value is None for value in values):
        return None
    return sum(value for value in values if value is not None)


def summarize(label: str, files: dict[str, ArchiveEntry], unique: set[str]) -> None:
    uncompressed = sum(files[name].file_size for name in unique)
    compressed = sum_compressed(files, unique)
    print(f"{label}:")
    print(f"  files only here: {len(unique)}")
    print(f"  uncompressed size: {uncompressed} bytes ({format_bytes(uncompressed)})")
    print(f"  compressed size in zip: {format_optional_bytes(compressed)}")


def summarize_common(
    label: str,
    files1: dict[str, ArchiveEntry],
    files2: dict[str, ArchiveEntry],
    common: set[str],
) -> None:
    uncompressed1 = sum(files1[name].file_size for name in common)
    compressed1 = sum_compressed(files1, common)
    uncompressed2 = sum(files2[name].file_size for name in common)
    compressed2 = sum_compressed(files2, common)
    print(f"{label}:")
    print(f"  files in common: {len(common)}")
    print(f"  uncompressed size in first zip: {uncompressed1} bytes ({format_bytes(uncompressed1)})")
    print(f"  compressed size in first zip: {format_optional_bytes(compressed1)}")
    print(f"  uncompressed size in second zip: {uncompressed2} bytes ({format_bytes(uncompressed2)})")
    print(f"  compressed size in second zip: {format_optional_bytes(compressed2)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "List how many files are present in each of two zip archives but not "
            "the other, plus the size of those files."
        )
    )
    parser.add_argument("zip1", help="first zip file")
    parser.add_argument("zip2", help="second zip file")
    parser.add_argument(
        "-i",
        "--ignore-case",
        action="store_true",
        help="compare internal zip paths case-insensitively",
    )
    parser.add_argument(
        "--no-external-fallback",
        action="store_true",
        help="do not use 7z or tar to list entries when Python cannot read a damaged zip",
    )
    args = parser.parse_args(argv)

    try:
        files1 = read_files(
            args.zip1,
            ignore_case=args.ignore_case,
            external_fallback=not args.no_external_fallback,
        )
        files2 = read_files(
            args.zip2,
            ignore_case=args.ignore_case,
            external_fallback=not args.no_external_fallback,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    names1 = set(files1)
    names2 = set(files2)

    summarize(args.zip1, files1, names1 - names2)
    summarize(args.zip2, files2, names2 - names1)
    summarize_common("common files", files1, files2, names1 & names2)
    print(f"total files in {args.zip1}: {len(names1)}")
    print(f"total files in {args.zip2}: {len(names2)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
