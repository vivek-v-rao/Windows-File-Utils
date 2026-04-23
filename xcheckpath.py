import os

def check_path_directories():
    # Get the PATH environment variable
    path_var = os.getenv('PATH')
    
    if not path_var:
        print("PATH environment variable is not set.")
        return
    
    # Split the PATH into individual directories
    directories = path_var.split(os.pathsep)
    
    print("Checking PATH for non-existent directories...\n")
    
    # Check each directory
    non_existent_dirs = []
    for directory in directories:
        # Normalize the path (remove surrounding quotes if present)
        directory = directory.strip('"')
        
        # Check if the directory exists
        if not os.path.isdir(directory):
            non_existent_dirs.append(directory)
    
    # Print non-existent directories
    if non_existent_dirs:
        print("The following directories in your PATH do not exist:")
        for dir_path in non_existent_dirs:
            print(f"- {dir_path}")
    else:
        print("All directories in your PATH exist.")
    
    print("\nDone.")

if __name__ == "__main__":
    check_path_directories()
