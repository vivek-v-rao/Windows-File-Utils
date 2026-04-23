from pathlib import Path
from sys import argv
from util import dir_size, format_size

def main():
    """ List sizes of subdirectories in a given or current directory,
    showing only those above a specified size. """
    current_dir = Path.cwd() if len(argv) < 2 else Path(argv[1]).resolve()
    print(f"Scanning directories in {current_dir}\n")
    
    size_min = 100.0  # Only show directories larger than this size in MB
    size_min_bytes = size_min * 1024**2 # Convert MB to bytes for comparison
    
    # Store directory sizes
    dir_sizes = {}
    
    # Get immediate subdirectories
    try:
        subdirs = [d for d in current_dir.iterdir() if d.is_dir()]
        
        if not subdirs:
            print("No subdirectories found in the current directory.")
            return
            
        # Calculate size for each subdirectory
        for subdir in subdirs:
            size = dir_size(subdir)
            if size >= 0:  # Only include directories that could be accessed
                dir_sizes[subdir.name] = size
        
        # Filter directories by minimum size and sort by size (largest first)
        filtered_dirs = {name: size for name, size in dir_sizes.items() if size >= size_min_bytes}
        sorted_dirs = sorted(filtered_dirs.items(), key=lambda x: x[1], reverse=True)
        
        if not sorted_dirs:
            print(f"No subdirectories found larger than {size_min} MB.")
            return
            
        # Print results
        print(f"Subdirectory Sizes (larger than {size_min} MB, largest to smallest):")
        print("-" * 50)
        for dir_name, size in sorted_dirs:
            print(f"{dir_name:<30} {format_size(size):>15}")
        # Print total size
        total_size = sum(filtered_dirs.values())
        print("-" * 50)
        print(f"Total size of all shown subdirectories: {format_size(total_size)}")
        
    except Exception as e:
        print(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()