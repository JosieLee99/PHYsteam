"""build_launch_game_windows.py

Double-click this to build launch_game_windows.exe from
launch_game_windows.py in the same folder. Installs PyInstaller
automatically if it isn't already present -- no console commands needed.

Requires Python to be installed on this machine (this script IS what
does the compiling, so it can't bootstrap around needing Python itself --
but the resulting launch_game_windows.exe will NOT require Python on the
end user's machine).
"""

import importlib.util
import os
import shutil
import subprocess
import sys

SOURCE_NAME = "launch_game_windows.py"
OUTPUT_NAME = "launch_game_windows"


def base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def pause():
    input("\nPress Enter to exit...")


def is_store_stub(python_path):
    """The Windows Store 'app execution alias' python.exe is a tiny stub
    that does nothing useful when run non-interactively -- it's usually
    under a WindowsApps folder. If sys.executable resolves to this, pip
    installs silently fail without a real error."""
    return "windowsapps" in python_path.lower()


def find_real_python():
    """Prefer sys.executable, but fall back to searching PATH if it turns
    out to be the Windows Store stub."""
    candidates = [sys.executable]
    for name in ("python", "python3"):
        found = shutil.which(name)
        if found and found not in candidates:
            candidates.append(found)

    for path in candidates:
        if path and os.path.isfile(path) and not is_store_stub(path):
            return path
    return None


def pyinstaller_installed():
    return importlib.util.find_spec("PyInstaller") is not None


def install_pyinstaller(python_path):
    print("PyInstaller not found -- installing it now (this may take a minute)...")
    result = subprocess.run(
        [python_path, "-m", "pip", "install", "--upgrade", "pyinstaller"],
    )
    if result.returncode != 0:
        print()
        print(f"pip exited with code {result.returncode}. See output above for the actual error.")
    return result.returncode == 0


def main():
    print()
    print(" PHYsteam Launcher Builder")
    print(" ----------------------------")
    print()

    script_dir = base_dir()
    source_path = os.path.join(script_dir, SOURCE_NAME)

    if not os.path.isfile(source_path):
        print(f"ERROR: {SOURCE_NAME} not found in {script_dir}")
        print("Make sure this builder and launch_game_windows.py are in the same folder.")
        pause()
        sys.exit(1)

    if pyinstaller_installed():
        print("PyInstaller is already installed.")
        python_path = sys.executable
    else:
        python_path = find_real_python()
        if not python_path:
            print("ERROR: Could not find a working Python interpreter.")
            print("If you installed Python from the Microsoft Store, that version")
            print("can fail silently here -- please install Python from")
            print("https://python.org/downloads instead, then run this again.")
            pause()
            sys.exit(1)
        if not install_pyinstaller(python_path):
            print("ERROR: Failed to install PyInstaller. Check your internet connection")
            print("and try again.")
            pause()
            sys.exit(1)
        print("PyInstaller installed successfully.")

    print()
    print(f"Compiling {SOURCE_NAME} -> {OUTPUT_NAME}.exe ...")
    print("(this can take 20-60 seconds)")
    print()

    result = subprocess.run(
        [
            python_path, "-m", "PyInstaller",
            "--onefile",
            "--name", OUTPUT_NAME,
            "--distpath", script_dir,
            "--workpath", os.path.join(script_dir, "_build_temp"),
            "--specpath", os.path.join(script_dir, "_build_temp"),
            source_path,
        ],
        cwd=script_dir,
    )

    if result.returncode != 0:
        print()
        print("ERROR: Build failed. See the output above for details.")
        pause()
        sys.exit(1)

    exe_path = os.path.join(script_dir, f"{OUTPUT_NAME}.exe")
    print()
    print(" Success!")
    print(f" Built: {exe_path}")
    print()
    print(" You can now delete the _build_temp folder if it's still here --")
    print(" it's just leftover build files, not needed to run the exe.")
    print()
    print(" To make a new cartridge: copy this exe + a game_id.txt")
    print(" (containing just the Steam App ID) onto the drive. No need to")
    print(" rebuild this exe again for future games.")
    print()
    pause()


if __name__ == "__main__":
    main()
