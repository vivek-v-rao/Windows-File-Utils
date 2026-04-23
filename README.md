# Windows-File-Utils

Small Python utilities for inspecting the Windows filesystem, summarizing `dir /s` output, and finding where disk space is going.

This repo is aimed at Windows users who already use Command Prompt or PowerShell and want lightweight scripts instead of a large GUI tool.

## Best Scripts

These are the strongest scripts in the repo and the ones most worth using first.

### `xfile_size.py`

Recursively scans a directory, filters by extension or glob, and reports file sizes. It can also summarize total bytes by directory.

Typical uses:

```powershell
python xfile_size.py --dir C:\python --glob "*.exe"
python xfile_size.py --dir C:\python --glob "*.exe" --summary
python xfile_size.py --dir C:\python\code --ext py --summary
```

Useful when you want to answer:

- Which matching files are largest?
- Which directories contain the most bytes for files matching a glob?
- How much space do all `.py`, `.exe`, or `.dll` files take under a tree?

### `xdisk_space.py`

Summarizes Windows `dir /s` output into a flat CSV with:

- `directory_name`
- `size_mb`
- `file_count`

It can either:

1. parse a text file created from `dir /s`, or
2. scan a directory directly

Examples:

```powershell
dir /s C:\python > temp.txt
python xdisk_space.py temp.txt
python xdisk_space.py temp.txt --max-depth 2
python xdisk_space.py --dir C:\python --max-depth 1
```

This is useful when you want a CSV you can open in Excel or sort further with pandas.

### `xsummarize_directories.py`

Parses Windows `dir` output and prints per-directory totals in a compact table.

Examples:

```powershell
dir /s *.exe > temp.txt
python xsummarize_directories.py temp.txt --sort "#bytes"
python xsummarize_directories.py temp.txt --sort "#files"
python xsummarize_directories.py temp.txt --csv summary.csv
```

This is a good fit when you already have a `dir /s` capture and just want a quick text summary by directory.

### `xanalyze_dir.py`

Analyzes `dir /s` output in more depth. It reports:

- largest directories
- largest files
- largest extensions
- cleanup candidates to review

Examples:

```powershell
dir /s C:\backtests > temp.txt
python xanalyze_dir.py temp.txt
python xanalyze_dir.py temp.txt --focus C:\backtests
python xanalyze_dir.py temp.txt --csv-prefix report
```

This is the most feature-rich script in the repo.

### `xcheckpath.py`

Checks the current `PATH` environment variable and lists directories that no longer exist.

Example:

```powershell
python xcheckpath.py
```

Useful for cleaning up broken Windows environment settings.

## Other Scripts

These are narrower or less polished than the ones above.

### `xprocess_dir.py`

Runs `dir /s` for a filename or glob and prints each matching instance with date, time, size, and containing directory.

Examples:

```powershell
python xprocess_dir.py myfile.txt
python xprocess_dir.py "*.dll"
python xprocess_dir.py "*.dll" --sort-instances
```

Good for locating where a file exists across a tree. Less useful than `xfile_size.py` when you need aggregated directory totals.

### `xdirectory_size.py`

Lists immediate subdirectories above a size threshold, largest first.

Example:

```powershell
python xdirectory_size.py C:\python
```

Good for a quick high-level directory scan, but not as flexible as `xfile_size.py` or `xdisk_space.py`.

### `xext_summary.py`

Recursively scans a directory and summarizes storage by file extension. It shows:

- extension
- file count
- total bytes
- human-readable size
- top directories for each extension

Examples:

```powershell
python xext_summary.py C:\python
python xext_summary.py C:\python --sort size-desc
python xext_summary.py C:\python --top 20 --top-dirs 3
python xext_summary.py C:\python --min-size-mb 0
```

This is useful when you want to know whether `.exe`, `.dll`, `.csv`, `.zip`, `.log`, or no-extension files dominate a tree.

## Shared Parser Modules

The repo also includes shared support modules used by the scripts:

- `windows_dir_parser.py`
- `windows_fs_report.py`

These hold common logic for parsing `dir /s` output and shared reporting helpers.

## Input Patterns

Several scripts work from Windows `dir /s` output. Typical pattern:

```powershell
dir /s C:\some\directory > temp.txt
```

Or for a glob:

```powershell
dir /s *.exe > temp.txt
```

Then feed `temp.txt` into:

- `xdisk_space.py`
- `xsummarize_directories.py`
- `xanalyze_dir.py`

## Requirements

Python 3 is required.

Some scripts also require `pandas`:

```powershell
python -m pip install pandas
```

## Suggested Starting Points

If you are new to the repo:

- Use `xfile_size.py` when you want to scan the live filesystem directly.
- Use `xsummarize_directories.py` when you already have `dir /s` output and want a fast summary.
- Use `xdisk_space.py` when you want CSV output.
- Use `xanalyze_dir.py` when you want the deepest report.
- Use `xext_summary.py` when the main question is "which file types are taking the space?"
