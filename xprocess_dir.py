"""Find matching files via Windows ``dir /s`` output and print their locations.

Given a filename or glob, this script runs ``dir /s`` and reports each match
with its date, time, size, and containing directory. It can also sort the
instances of each matched file by size in descending order.
"""

import subprocess
import re
import glob
from sys import argv, exit

def parse_dir_output(file_name, sort_instances=False):
    """Reformats Windows CMD 'dir /s' command output for a file into a table
    showing date, time, size, and directory.
    If sort_instances is True, entries are sorted by file size (descending)."""
    # Run the dir /s command
    result = subprocess.run(
        ['dir', '/s', file_name], capture_output=True, text=True, shell=True
    )
    output = result.stdout

    # Patterns for directory header and file entries
    dir_pattern = re.compile(r'Directory of (.*?)\s*$')
    file_pattern = re.compile(
        rf"(\d{{2}}/\d{{2}}/\d{{4}})\s+(\d{{2}}:\d{{2}}\s+[AP]M)\s+([\d,]+)\s+{re.escape(file_name)}"
    )

    current_dir = ''
    instances = []

    for line in output.splitlines():
        line = line.strip()
        # Directory header
        m_dir = dir_pattern.match(line)
        if m_dir:
            current_dir = m_dir.group(1).strip()
            continue

        # File entry
        m_file = file_pattern.match(line)
        if m_file:
            date, time, size_str = m_file.groups()
            size = int(size_str.replace(',', ''))
            instances.append((date, time, size, current_dir))

    # Sort instances by size if requested
    if sort_instances:
        instances.sort(key=lambda x: x[2], reverse=True)

    # Output
    if instances:
        print(f"\nfile: {file_name}")
        for date, time, size, directory in instances:
            print(f"{date} {time} {size:>12}   {directory}")
    else:
        print(f"file: {file_name} not found")


if __name__ == '__main__':
    if len(argv) < 2:
        exit("usage: python xprocess_dir.py <file_or_glob> [--sort-instances]")

    pattern = argv[1]
    sort_instances = False
    # Optional flag to sort each file's instances by size
    if len(argv) > 2 and argv[2] in ('-s', '--sort-instances'):
        sort_instances = True

    # Expand glob if needed
    if any(c in pattern for c in ('*', '?', '[')):
        files = glob.glob(pattern)
        if not files:
            exit(f"No files match pattern: {pattern}")
        files = sorted(files)
    else:
        files = [pattern]

    # Process each file
    for fname in files:
        parse_dir_output(fname, sort_instances)
