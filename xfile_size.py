import argparse
import fnmatch
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd


WILDCARD_CHARS = "*?[]"


def normalize_extensions(extensions: list[str] | None) -> set[str] | None:
    """Normalize extension values to lowercase suffixes like '.exe'."""
    if not extensions:
        return None

    normalized = set()
    for ext in extensions:
        value = ext.strip().lower()
        if not value:
            continue
        if not value.startswith("."):
            value = f".{value}"
        normalized.add(value)

    return normalized or None


def matches_glob_patterns(path: Path, root: Path, patterns: list[str] | None) -> bool:
    """Return True when a file matches at least one supplied glob pattern."""
    if not patterns:
        return True

    relative_path = str(path.relative_to(root))
    file_name = path.name
    for pattern in patterns:
        if fnmatch.fnmatch(file_name, pattern) or fnmatch.fnmatch(relative_path, pattern):
            return True
    return False


def describe_filters(extensions: list[str] | None, globs: list[str] | None) -> str:
    parts = []
    normalized_extensions = normalize_extensions(extensions)
    if normalized_extensions:
        parts.append(f"extensions {sorted(normalized_extensions)}")
    if globs:
        parts.append(f"globs {globs}")
    if not parts:
        return ""
    return " matching " + " and ".join(parts)


def has_wildcards(value: str) -> bool:
    return any(char in value for char in WILDCARD_CHARS)


def split_directory_and_globs(directory: str, globs: list[str] | None) -> tuple[str, list[str] | None]:
    """Allow directory specs like C:\\fortran\\*.exe by splitting out the glob part."""
    if not has_wildcards(directory):
        return directory, globs

    path = Path(directory)
    parts = path.parts
    wildcard_index = next((index for index, part in enumerate(parts) if has_wildcards(part)), None)
    if wildcard_index is None:
        return directory, globs

    base_parts = parts[:wildcard_index]
    glob_parts = parts[wildcard_index:]

    if not base_parts:
        base_directory = "."
    else:
        base_directory = str(Path(*base_parts))

    merged_globs = list(globs or [])
    merged_globs.append(str(Path(*glob_parts)))
    return base_directory, merged_globs


def collect_file_sizes(
    directory: str,
    extensions: list[str] | None = None,
    globs: list[str] | None = None,
) -> pd.DataFrame:
    """Collect file sizes recursively under a directory."""
    root = Path(directory).resolve()
    if not root.exists():
        raise ValueError(f"Directory does not exist: {directory}")
    if not root.is_dir():
        raise ValueError(f"Not a directory: {directory}")

    allowed_extensions = normalize_extensions(extensions)
    rows = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if allowed_extensions and path.suffix.lower() not in allowed_extensions:
            continue
        if not matches_glob_patterns(path, root, globs):
            continue
        try:
            size_bytes = path.stat().st_size
        except OSError:
            continue
        mtime = datetime.fromtimestamp(path.stat().st_mtime)
        rows.append(
            {
                "size_bytes": size_bytes,
                "file_time": mtime.strftime("%m/%d/%Y  %I:%M %p"),
                "file_path": str(path),
            }
        )

    if not rows:
        return pd.DataFrame(columns=["size_bytes", "file_time", "file_path"])

    return pd.DataFrame(rows)


def summarize_by_directory(df: pd.DataFrame) -> pd.DataFrame:
    """Summarize file counts and bytes by containing directory."""
    summary_df = df.copy()
    summary_df["directory"] = summary_df["file_path"].map(lambda path: str(Path(path).parent))
    summary_df = (
        summary_df.groupby("directory", as_index=False)
        .agg(
            file_count=("file_path", "count"),
            total_size_bytes=("size_bytes", "sum"),
        )
        .sort_values(["total_size_bytes", "directory"], ascending=[True, True])
        .reset_index(drop=True)
    )
    return summary_df


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")

    parser = argparse.ArgumentParser(
        description=(
            "List files in a directory tree sorted by size ascending. "
            "Prints size_bytes and full file_path. "
            "For compatibility, --dir may also include wildcard segments such as "
            "C:\\fortran\\*.exe."
        )
    )
    parser.add_argument(
        "--dir",
        "--directory",
        dest="directory",
        required=True,
        help=(
            "Base directory to scan recursively. "
            "Compatibility shortcut: wildcard paths like C:\\fortran\\*.exe are accepted."
        ),
    )
    parser.add_argument(
        "--ext",
        "--extension",
        dest="extensions",
        nargs="+",
        help="Optional file extension filter, for example: --ext exe or --ext .exe .dll",
    )
    parser.add_argument(
        "--glob",
        dest="globs",
        nargs="+",
        help='Optional filename/path glob filter, for example: --glob "*.exe" "bin\\*.dll"',
    )
    parser.add_argument(
        "--min-size-bytes",
        type=int,
        default=0,
        help="Only show files with size >= this value in bytes.",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Show one row per directory with file_count and total_size_bytes.",
    )
    args = parser.parse_args()

    if args.min_size_bytes < 0:
        parser.error("--min-size-bytes must be >= 0.")

    scan_directory, globs = split_directory_and_globs(args.directory, args.globs)

    df = collect_file_sizes(scan_directory, args.extensions, globs)
    if df.empty:
        print(
            f"No files found under: {Path(scan_directory).resolve()}"
            f"{describe_filters(args.extensions, globs)}"
        )
        return

    df = df[df["size_bytes"] >= args.min_size_bytes]
    df = df.sort_values("size_bytes", ascending=True).reset_index(drop=True)

    if df.empty:
        print(
            f"No files found meeting min size {args.min_size_bytes} bytes under: "
            f"{Path(scan_directory).resolve()}{describe_filters(args.extensions, globs)}"
        )
        return

    if args.summary:
        summary_df = summarize_by_directory(df)
        print(f"{'file_count':>10} {'total_size_bytes':>17} directory")
        for _, row in summary_df.iterrows():
            print(
                f"{int(row['file_count']):10d} "
                f"{int(row['total_size_bytes']):17d} "
                f"{row['directory']}"
            )
        return

    print(f"{'size_bytes':>15} {'file_time':20} file_path")
    for _, row in df.iterrows():
        print(f"{int(row['size_bytes']):15d} {row['file_time']:20} {row['file_path']}")


if __name__ == "__main__":
    main()
