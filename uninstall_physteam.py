"""uninstall_physteam.py — builds into Uninstall_PHYsteam.exe (requires admin via UAC)"""

import subprocess
import sys
import time

TASK_NAME = "PHYsteam"

def pause():
    input("\nPress Enter to exit...")

def main():
    print()
    print(" PHYsteam Uninstaller")
    print(" ----------------------------")
    print()

    confirm = input("This will stop PHYsteam and remove it from startup. Continue? (Y/N): ").strip().lower()
    if confirm != "y":
        print("Cancelled.")
        pause()
        sys.exit(0)

    print()
    print(" Stopping PHYsteam...")
    subprocess.run(
        [
            "powershell", "-NoProfile", "-Command",
            "Get-CimInstance Win32_Process | "
            "Where-Object { $_.CommandLine -like '*physteam*' } | "
            "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
        ],
        capture_output=True
    )
    time.sleep(2)
    print(" Done.")

    print()
    print(" Removing from startup...")
    result = subprocess.run(
        ["schtasks", "/delete", "/tn", TASK_NAME, "/f"],
        capture_output=True
    )
    if result.returncode == 0:
        print(" Removed from Task Scheduler.")
    else:
        print(" No startup task found (already removed or never registered).")

    print()
    print(" Uninstall complete! PHYsteam has been removed from your system.")
    print()
    pause()

if __name__ == "__main__":
    main()
