#!/usr/bin/env python3
"""
AI Local Desktop Compiler Script
================================
Automates the compilation of 'llamaLauncher' into a single, standalone executable (.exe)
using PyInstaller. Auto-installs missing build dependencies if required.

Usage:
    python buildLauncher.py
"""

import subprocess
import sys
import shutil
from pathlib import Path

def run_command(cmd_list, shell=False):
    """Utility to run system commands and handle errors."""
    try:
        subprocess.check_call(cmd_list, shell=shell)
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] Command failed with exit code {e.returncode}: {' '.join(cmd_list)}")
        return False

def main():
    print("=======================================================================")
    print("             AI LOCAL — DESKTOP LAUNCHER COMPILER")
    print("=======================================================================")
    
    # buildLauncher.py is inside llamaLauncher/
    # SCRIPT_DIR = PROJECT_ROOT/llamaLauncher
    # PROJECT_ROOT = SCRIPT_DIR.parent
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    
    # 1. Verify and install PyInstaller if missing
    try:
        import PyInstaller
        print("[INFO] PyInstaller is installed correctly.")
    except ImportError:
        print("[INFO] PyInstaller is missing. Installing build dependencies...")
        if not run_command([sys.executable, "-m", "pip", "install", "pyinstaller"]):
            print("[ERROR] Failed to install PyInstaller. Aborting build.")
            sys.exit(1)

    # 2. Verify pywebview is installed
    try:
        import webview
        print("[INFO] pywebview is installed correctly.")
    except ImportError:
        print("[INFO] pywebview is missing. Installing...")
        if not run_command([sys.executable, "-m", "pip", "install", "pywebview"]):
            print("[ERROR] Failed to install pywebview. Aborting build.")
            sys.exit(1)

    # 3. Clean previous build folders to prevent cache locks
    print("[INFO] Cleaning up previous build folders...")
    for folder in ["build", "dist"]:
        path = project_root / folder
        if path.exists():
            try:
                shutil.rmtree(path)
            except Exception as e:
                print(f"[WARN] Could not clean {folder} directory: {e}")

    # 4. Build PyInstaller Command
    # We bundle the entire app/frontend folder into the executable
    add_data_flag = "llamaLauncher/app/frontend;llamaLauncher/app/frontend"
    if sys.platform != "win32":
        # Unix uses ':' instead of ';'
        add_data_flag = "llamaLauncher/app/frontend:llamaLauncher/app/frontend"

    cmd = [
        "pyinstaller",
        "--onefile",
        "--noconsole",
        "--add-data", add_data_flag,
        "--name", "AI-Local-Launcher",
        str(script_dir / "app.py")
    ]

    print("\n[BUILDING] Running PyInstaller compiler...")
    print(f"Command: {' '.join(cmd)}")
    print("-----------------------------------------------------------------------")
    
    # Run compiler from project_root to ensure relative paths resolve perfectly
    success = run_command(cmd, shell=(sys.platform == "win32"))

    if success:
        exe_ext = ".exe" if sys.platform == "win32" else ""
        exe_path = project_root / "dist" / f"AI-Local-Launcher{exe_ext}"
        print("\n=======================================================================")
        print("                 [BUILD COMPLETED SUCCESSFULLY] !!!")
        print("=======================================================================")
        print(f"Standalone executable generated at: dist/AI-Local-Launcher{exe_ext}")
        print("-----------------------------------------------------------------------")
        print("Portability details:")
        print(" - This executable is completely standalone and does not require Python.")
        print(" - Place the .exe in the project root directory (next to 'models', 'bin'")
        print("   and 'logs' directories) to start the local inference server.")
        print("=======================================================================\n")
    else:
        print("\n[ERROR] Build compilation failed. Review error logs above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
