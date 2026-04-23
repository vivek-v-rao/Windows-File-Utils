from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import PureWindowsPath
import re
from typing import Iterable


DIR_HEADER_RE = re.compile(r"^\s*Directory of\s+(.+?)\s*$", re.IGNORECASE)
FILE_SUMMARY_RE = re.compile(r"^\s*([\d,]+)\s+File\(s\)\s+([\d,]+)\s+bytes\s*$", re.IGNORECASE)
TOTAL_FILES_RE = re.compile(r"^\s*Total Files Listed:\s*$", re.IGNORECASE)
FILE_NOT_FOUND_RE = re.compile(r"^\s*File Not Found\s*$", re.IGNORECASE)
ENTRY_RE = re.compile(
    r"^(?P<date>\d{2}/\d{2}/\d{4})\s+"
    r"(?P<time>\d{2}:\d{2}\s+[AP]M)\s+"
    r"(?P<size_or_dir><[^>]+>|[\d,]+)\s+"
    r"(?P<name>.+)$"
)


@dataclass(frozen=True)
class DirectorySummary:
    directory: str
    file_count: int
    size_bytes: int


@dataclass(frozen=True)
class FileEntry:
    directory: str
    name: str
    path: str
    size: int
    ext: str
    modified: datetime | None


@dataclass(frozen=True)
class DirSParseResult:
    root_dir: str | None
    directory_summaries: list[DirectorySummary]
    files: list[FileEntry]


def parse_modified(date_str: str, time_str: str) -> datetime | None:
    try:
        return datetime.strptime(f"{date_str} {time_str}", "%m/%d/%Y %I:%M %p")
    except ValueError:
        return None


def parse_dir_s_lines(lines: Iterable[str]) -> DirSParseResult:
    root_dir = None
    current_dir = None
    in_total_section = False
    directory_summaries: list[DirectorySummary] = []
    files: list[FileEntry] = []

    for raw_line in lines:
        line = raw_line.rstrip("\r\n")

        m_dir = DIR_HEADER_RE.match(line)
        if m_dir:
            current_dir = str(PureWindowsPath(m_dir.group(1).strip()))
            if root_dir is None:
                root_dir = current_dir
            in_total_section = False
            continue

        if current_dir is None:
            continue

        if TOTAL_FILES_RE.match(line):
            in_total_section = True
            current_dir = None
            continue

        if in_total_section:
            continue

        if FILE_NOT_FOUND_RE.match(line):
            directory_summaries.append(
                DirectorySummary(directory=current_dir, file_count=0, size_bytes=0)
            )
            current_dir = None
            continue

        m_summary = FILE_SUMMARY_RE.match(line)
        if m_summary:
            directory_summaries.append(
                DirectorySummary(
                    directory=current_dir,
                    file_count=int(m_summary.group(1).replace(",", "")),
                    size_bytes=int(m_summary.group(2).replace(",", "")),
                )
            )
            current_dir = None
            continue

        m_entry = ENTRY_RE.match(line)
        if not m_entry:
            continue

        size_or_dir = m_entry.group("size_or_dir")
        name = m_entry.group("name").strip()
        if size_or_dir.startswith("<") or name in {".", ".."}:
            continue

        try:
            size = int(size_or_dir.replace(",", ""))
        except ValueError:
            continue

        full_path = str(PureWindowsPath(current_dir) / name)
        files.append(
            FileEntry(
                directory=current_dir,
                name=name,
                path=full_path,
                size=size,
                ext=PureWindowsPath(name).suffix.lower(),
                modified=parse_modified(m_entry.group("date"), m_entry.group("time")),
            )
        )

    return DirSParseResult(
        root_dir=root_dir,
        directory_summaries=directory_summaries,
        files=files,
    )


def parse_dir_s_text(text: str) -> DirSParseResult:
    return parse_dir_s_lines(text.splitlines())


def parse_dir_s_file(path: str) -> DirSParseResult:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return parse_dir_s_lines(f)
