#!/usr/bin/env python3
"""launch_game_linux.py — dropped on the cartridge drive itself.

Your game's Steam App ID
Find it at: https://store.steampowered.com/app/XXXXXXX
                         ^^^^^^^
"""
import subprocess
import sys
import shutil

STEAM_APP_ID = "{APP_ID}"  # <--- REPLACE {APP_ID} WITH GAME STORE PAGE APP ID. Example: 105600
		    ^        <--- REPLACE {APP_ID} WITH EXACT NON STEAM GAME TITLE Example: "Pokemon: FireRed Version"

def launch_steam_game(app_id):
    uri = f"steam://rungameid/{app_id}"
    try:
        if shutil.which("steam"):
            subprocess.Popen(["steam", uri])
        elif shutil.which("xdg-open"):
            subprocess.Popen(["xdg-open", uri])
        else:
            print("Could not find 'steam' or 'xdg-open' on PATH.")
            sys.exit(1)
        print(f"Launching Steam game {app_id}...")
    except Exception as e:
        print(f"Error launching game: {e}")
        sys.exit(1)

if __name__ == "__main__":
    launch_steam_game(STEAM_APP_ID)
