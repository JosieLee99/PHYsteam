"""install_physteam.py — builds into Install_PHYsteam.exe (requires admin via UAC)"""

import os
import subprocess
import sys

TASK_NAME = "PHYsteam"

def base_dir():
    # Works whether running as a script or as a frozen PyInstaller exe
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def pause():
    input("\nPress Enter to exit...")

def main():
    script_dir = base_dir()
    watcher_exe = os.path.join(script_dir, "PHYsteam_Engine.exe")

    if not os.path.exists(watcher_exe):
        print(f"ERROR: PHYsteam_Engine.exe not found in {script_dir}")
        print("Make sure Install_PHYsteam.exe and PHYsteam_Engine.exe are in the same folder.")
        pause()
        sys.exit(1)

    # Remove any existing task first (ignore errors if it doesn't exist)
    subprocess.run(
        ["schtasks", "/delete", "/tn", TASK_NAME, "/f"],
        capture_output=True
    )

    result = subprocess.run(
        [
            "schtasks", "/create",
            "/tn", TASK_NAME,
            "/tr", f'"{watcher_exe}"',
            "/sc", "ONLOGON",
            "/rl", "HIGHEST",
            "/f"
        ],
        capture_output=True, text=True
    )

    if result.returncode == 0:
        print()
        print(" Success! PHYsteam will now start automatically at login.")
        print()
        print(f" PHYsteam executable: {watcher_exe}")
        print(f" Log file           : {os.path.join(script_dir, 'physteam.log')}")
        print()
        print(" Starting PHYsteam setup...")
        subprocess.Popen([watcher_exe, "--configure"])
        print(" Done! Insert your game cartridge to test it.")
    else:
        print("ERROR: Failed to create the scheduled task.")
        print(result.stderr)

    pause()

if __name__ == "__main__":
    main()
