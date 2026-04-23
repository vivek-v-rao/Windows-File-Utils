import argparse
import os
from pathlib import Path, PureWindowsPath

import pandas as pd
from windows_dir_parser import parse_dir_s_file
from windows_fs_report import bucket_relative_path


def finalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["size_mb"] = df["size_bytes"] / (1024 * 1024)
    df = df.drop(columns=["size_bytes"])
    df = df[["directory_name", "size_mb", "file_count"]]
    df = df.sort_values("size_mb", ascending=False).reset_index(drop=True)
    return df

def parse_dir_s_output_file(input_file: str, max_depth: int):
    parsed = parse_dir_s_file(input_file)
    root_dir = parsed.root_dir
    if root_dir is None:
        raise ValueError("No 'Directory of ...' lines found in input.")

    rows = []
    root_path = PureWindowsPath(root_dir)
    for summary in parsed.directory_summaries:
        current_path = PureWindowsPath(summary.directory)
        if max_depth > 0 and current_path == root_path:
            continue
        try:
            rel_dir = str(current_path.relative_to(root_path))
        except ValueError:
            continue
        directory_name = bucket_relative_path(rel_dir, max_depth)
        if not directory_name:
            continue
        rows.append(
            {
                "directory_name": directory_name,
                "size_bytes": summary.size_bytes,
                "file_count": summary.file_count,
            }
        )

    if not rows:
        raise ValueError(f"No subdirectory summaries found under root: {root_dir}")

    df = pd.DataFrame(rows)
    df = df.groupby("directory_name", as_index=False)[["size_bytes", "file_count"]].sum()
    return root_dir, finalize_dataframe(df)


def parse_dir_s_from_directory(directory: str, max_depth: int):
    root = Path(directory).resolve()
    if not root.exists():
        raise ValueError(f"Directory does not exist: {directory}")
    if not root.is_dir():
        raise ValueError(f"Not a directory: {directory}")

    totals = {}
    for walk_root, _, files in os.walk(root, topdown=True, followlinks=False):
        direct_count = 0
        direct_size = 0
        for name in files:
            file_path = Path(walk_root) / name
            try:
                direct_size += file_path.stat().st_size
                direct_count += 1
            except OSError:
                continue

        rel_path = Path(walk_root).relative_to(root)
        rel_str = "" if str(rel_path) == "." else str(PureWindowsPath(str(rel_path)))
        if max_depth > 0 and not rel_str:
            continue
        directory_name = bucket_relative_path(rel_str, max_depth)
        if not directory_name:
            continue
        if directory_name not in totals:
            totals[directory_name] = {"size_bytes": 0, "file_count": 0}
        totals[directory_name]["size_bytes"] += direct_size
        totals[directory_name]["file_count"] += direct_count

    if not totals:
        raise ValueError(f"No subdirectories found under root: {root}")

    rows = [
        {"directory_name": name, "size_bytes": v["size_bytes"], "file_count": v["file_count"]}
        for name, v in totals.items()
    ]
    df = pd.DataFrame(rows)
    df = finalize_dataframe(df)
    return str(root), df


def default_output_path(input_file: str) -> str:
    p = Path(input_file)
    return str(p.with_name(f"{p.stem}_disk_usage.csv"))


def default_output_path_from_directory(directory: str) -> str:
    p = Path(directory)
    name = p.name if p.name else "root"
    return str(Path.cwd() / f"{name}_disk_usage.csv")


def main():
    parser = argparse.ArgumentParser(
        description="Write a flat CSV summary (directory_name, size_mb, file_count)."
    )
    parser.add_argument(
        "input_file",
        nargs="?",
        help="Text file produced by: dir /s > files.txt",
    )
    parser.add_argument(
        "-d",
        "--dir",
        "--directory",
        dest="directory",
        help="Directory to scan directly using: dir /s /a <directory>",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Output CSV path (default: based on input file or directory name)",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=1,
        help="Directory depth to report (1=top-level, 2=include one subdirectory level).",
    )
    args = parser.parse_args()
    if args.max_depth < 0:
        parser.error("--max-depth must be >= 0.")

    has_input = bool(args.input_file)
    has_dir = bool(args.directory)
    if has_input == has_dir:
        parser.error("Specify exactly one source: either input_file or --directory.")

    if has_input:
        root_dir, df = parse_dir_s_output_file(args.input_file, max_depth=args.max_depth)
        output_file = args.output or default_output_path(args.input_file)
    else:
        root_dir, df = parse_dir_s_from_directory(args.directory, max_depth=args.max_depth)
        output_file = args.output or default_output_path_from_directory(args.directory)

    df.to_csv(output_file, index=False, float_format="%.2f")

    print(f"Root directory: {root_dir}")
    print(f"Wrote {len(df)} rows to: {output_file}")
    preview = df.head(10).copy()
    preview["size_mb"] = preview["size_mb"].map(lambda x: f"{x:.2f}")
    print(preview.to_string(index=False))


if __name__ == "__main__":
    main()
