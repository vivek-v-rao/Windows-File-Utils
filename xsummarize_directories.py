#!/usr/bin/env python3
"""Summarize Windows dir output by directory with pandas."""

import argparse
import pandas as pd
from windows_dir_parser import parse_dir_s_file
from windows_fs_report import common_base_path, relative_to_base


def dir_summary_df(infile):
    """Return DataFrame summarizing Windows dir output by directory."""
    rows = [
        {
            "#files": summary.file_count,
            "#bytes": summary.size_bytes,
            "directory": summary.directory,
        }
        for summary in parse_dir_s_file(infile).directory_summaries
    ]
    return pd.DataFrame(rows, columns=["#files", "#bytes", "directory"])


def make_relative_to_base(df):
    """Return dataframe with directories relative to common base, and base."""
    base = common_base_path(df["directory"].tolist())
    df_rel = df.copy()

    if not base:
        return df_rel, ""

    df_rel["directory"] = relative_to_base(df_rel["directory"].tolist(), base)
    return df_rel, base


def print_df_left_align_directory(df):
    """Print DataFrame with left-aligned directory column."""
    width = max(len("directory"), df["directory"].astype(str).str.len().max())
    df_print = df.copy()
    df_print["directory"] = df_print["directory"].astype(str).str.ljust(width)
    print(df_print.to_string(index=False, justify="right"))


def main():
    parser = argparse.ArgumentParser(
        description="Summarize Windows dir output by directory."
    )
    parser.add_argument("infile", help="Text file produced by Windows dir")
    parser.add_argument(
        "--sort",
        choices=["directory", "#files", "#bytes"],
        default="directory",
    )
    parser.add_argument(
        "--ascending",
        action="store_true",
        help="Sort ascending instead of descending for numeric fields",
    )
    parser.add_argument(
        "--files-desc",
        action="store_true",
        help="Sort by #files in descending order",
    )
    parser.add_argument(
        "--relative-common-base",
        action="store_true",
        help="Print common base and show directories relative to it",
    )
    parser.add_argument("--csv", help="Optional CSV output file")
    args = parser.parse_args()

    df = dir_summary_df(args.infile)

    if df.empty:
        print("No directory summaries found.")
        return

    if args.files_desc:
        df = df.sort_values("#files", ascending=False)
    elif args.sort == "directory":
        df = df.sort_values("directory", ascending=True)
    else:
        df = df.sort_values(args.sort, ascending=args.ascending)

    base = ""
    df_print = df

    if args.relative_common_base:
        df_print, base = make_relative_to_base(df)
        if base:
            print(f"base: {base}")
            print()

    print_df_left_align_directory(df_print)

    print()
    print(f"directories: {len(df)}")
    print(f"total files: {df['#files'].sum():,}")
    print(f"total bytes: {df['#bytes'].sum():,}")

    if args.csv:
        df_out = df_print if args.relative_common_base else df
        df_out.to_csv(args.csv, index=False)


if __name__ == "__main__":
    main()
