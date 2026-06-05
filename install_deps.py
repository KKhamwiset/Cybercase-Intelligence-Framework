import os
import subprocess
import sys
from pathlib import Path


def install_requirements(directory):
    """Install requirements from a requirements.txt file in the specified directory."""
    req_file = Path(directory) / "requirements.txt"

    if not req_file.exists():
        print(f"[-] Skip: {req_file} not found.")
        return

    print(f"[*] Installing dependencies in {directory}...")
    try:
        # Use sys.executable to ensure we use the same python/pip environment
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", str(req_file)]
        )
        print(f"[+] Success: Dependencies installed for {directory}\n")
    except subprocess.CalledProcessError as e:
        print(f"[!] Error: Failed to install dependencies in {directory}: {e}\n")


def main():
    # Define the directories relative to the root
    project_root = Path(__file__).parent
    dirs_to_install = ["backend", "rag_service"]

    print(f"=== Cybercase Framework Dependency Installer ===\n")

    for d in dirs_to_install:
        dir_path = project_root / d
        if dir_path.is_dir():
            install_requirements(dir_path)
        else:
            print(f"[-] Skip: Directory {d} not found.")

    print("=== Installation Process Finished ===")


if __name__ == "__main__":
    main()
