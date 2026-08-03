import subprocess
import sys

# Your game's Steam App ID
# Find it at: https://store.steampowered.com/app/XXXXXXX
#						 ^^^^^^^
STEAM_APP_ID = "{APP_ID}"  # <--- REPLACE {APP_ID} WITH GAME STORE PAGE APP ID. Example: 105600
		    ^        <--- REPLACE {APP_ID} WITH EXACT NON STEAM GAME TITLE Example: "Pokemon: FireRed Version"

def launch_steam_game(app_id):
    try:
        subprocess.Popen(f"start steam://rungameid/{app_id}", shell=True)
        print(f"Launching Steam game {app_id}...")
    except Exception as e:
        print(f"Error launching game: {e}")
        sys.exit(1)

if __name__ == "__main__":
    launch_steam_game(STEAM_APP_ID)
