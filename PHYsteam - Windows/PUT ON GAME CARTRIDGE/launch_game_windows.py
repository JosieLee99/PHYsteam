import subprocess
import sys
import os
import shlex

# Your game's Steam App ID
# Find it at: https://store.steampowered.com/app/XXXXXXX
#						 ^^^^^^^
# OR, if this game was added to Steam as a "non-Steam game" shortcut (no
# numeric App ID exists), put the exact name of the shortcut as it appears
# in your Steam library instead, e.g.  STEAM_APP_ID = "My Cool Game"



STEAM_APP_ID = "{APP_ID}"  # <--- Used only if no game_id.txt sits next to this file.
                          #      REPLACE {APP_ID} WITH GAME STORE PAGE APP ID (e.g. 105600) OR a game name in quotes

def base_dir():
    # Works whether running as a plain script or as a compiled exe.
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def resolve_app_id():
    """Prefer a game_id.txt file sitting next to this script/exe -- that way
    the SAME compiled launch_game_windows.exe can be dropped on every
    cartridge; you only ever edit the text file, never rebuild the exe."""
    id_file = os.path.join(base_dir(), "game_id.txt")
    if os.path.isfile(id_file):
        try:
            val = open(id_file, encoding="utf-8").read().strip()
            if val:
                return val
        except Exception as e:
            print(f"Could not read game_id.txt ({e}), falling back to STEAM_APP_ID.")
    return STEAM_APP_ID

def is_numeric_app_id(app_id):
    return app_id.strip().isdigit()

# ── Steam library lookup (used when STEAM_APP_ID is a name, not a numeric ID) ──
def find_steam_root():
    try:
        import winreg
        for hive, subkey, value_name in [
            (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath"),
        ]:
            try:
                with winreg.OpenKey(hive, subkey) as key:
                    path, _ = winreg.QueryValueEx(key, value_name)
                    path = path.replace("/", "\\")
                    if os.path.isdir(path):
                        return path
            except OSError:
                continue
    except ImportError:
        pass
    for p in [os.path.expandvars(r"%ProgramFiles(x86)%\Steam"),
              os.path.expandvars(r"%ProgramFiles%\Steam"), r"C:\Steam"]:
        if os.path.isdir(p):
            return p
    return None

def parse_binary_vdf(data):
    """Minimal parser for Valve's binary VDF format (used by shortcuts.vdf)."""
    pos = 0
    n = len(data)

    def parse_object():
        nonlocal pos
        obj = {}
        while pos < n:
            type_byte = data[pos]; pos += 1
            if type_byte == 0x08:  # end of object
                break
            nul = data.index(b"\x00", pos)
            key = data[pos:nul].decode("utf-8", errors="replace")
            pos = nul + 1
            if type_byte == 0x00:  # nested object
                obj[key] = parse_object()
            elif type_byte == 0x01:  # string
                vnul = data.index(b"\x00", pos)
                obj[key] = data[pos:vnul].decode("utf-8", errors="replace")
                pos = vnul + 1
            elif type_byte == 0x02:  # int32
                obj[key] = int.from_bytes(data[pos:pos + 4], "little", signed=True)
                pos += 4
            else:  # unknown/corrupt entry — bail out of this object
                break
        return obj

    return parse_object()

def find_non_steam_shortcut(name):
    """Search every Steam user's shortcuts.vdf for a non-Steam game entry
    whose name matches. Returns {"name", "exe", "start_dir"} or None."""
    steam_root = find_steam_root()
    if not steam_root:
        print("Could not locate Steam installation.")
        return None
    userdata = os.path.join(steam_root, "userdata")
    if not os.path.isdir(userdata):
        return None

    target = name.strip().lower()
    matches = []
    for uid in os.listdir(userdata):
        vdf_path = os.path.join(userdata, uid, "config", "shortcuts.vdf")
        if not os.path.isfile(vdf_path):
            continue
        try:
            with open(vdf_path, "rb") as f:
                root = parse_binary_vdf(f.read())
        except Exception as e:
            print(f"Could not parse {vdf_path}: {e}")
            continue

        shortcuts = None
        for k, v in root.items():
            if k.lower() == "shortcuts" and isinstance(v, dict):
                shortcuts = v
                break
        if not shortcuts:
            continue

        for entry in shortcuts.values():
            if not isinstance(entry, dict):
                continue
            app_name = exe = start_dir = launch_options = None
            for k, v in entry.items():
                kl = k.lower()
                if kl == "appname": app_name = v
                elif kl == "exe": exe = v
                elif kl == "startdir": start_dir = v
                elif kl == "launchoptions": launch_options = v
            if app_name and exe:
                matches.append({
                    "name": app_name,
                    "exe": exe.strip().strip('"'),
                    "start_dir": (start_dir.strip().strip('"') if start_dir else None),
                    "launch_options": launch_options or "",
                })

    if not matches:
        return None

    # Prefer an exact (case-insensitive) name match; fall back to substring.
    for m in matches:
        if m["name"].strip().lower() == target:
            return m
    for m in matches:
        if target in m["name"].strip().lower():
            return m
    return None

def launch_steam_game(app_id):
    try:
        subprocess.Popen(f"start steam://rungameid/{app_id}", shell=True)
        print(f"Launching Steam game {app_id}...")
    except Exception as e:
        print(f"Error launching game: {e}")
        sys.exit(1)

def launch_by_target_path(exe_path, start_dir=None, launch_options=""):
    try:
        cwd = start_dir if start_dir and os.path.isdir(start_dir) else (os.path.dirname(exe_path) or None)
        try:
            # posix=False so backslashes in Windows paths (e.g. a ROM path
            # in the launch options) aren't treated as escape characters.
            extra_args = shlex.split(launch_options, posix=False) if launch_options else []
            # shlex.split(posix=False) keeps surrounding quotes on quoted
            # tokens -- strip them since subprocess doesn't need them.
            extra_args = [a[1:-1] if len(a) >= 2 and a[0] == a[-1] == '"' else a for a in extra_args]
        except ValueError as e:
            print(f"Could not parse launch options ({e}) — launching without them: {launch_options!r}")
            extra_args = []
        subprocess.Popen([exe_path] + extra_args, cwd=cwd)
        print(f"Launching '{exe_path}' {' '.join(extra_args)}...")
    except Exception as e:
        print(f"Error launching game: {e}")
        sys.exit(1)

if __name__ == "__main__":
    app_id = resolve_app_id().strip()
    if is_numeric_app_id(app_id):
        launch_steam_game(app_id)
    else:
        print(f"STEAM_APP_ID '{app_id}' isn't numeric — searching your Steam library for a game named '{app_id}'...")
        shortcut = find_non_steam_shortcut(app_id)
        if not shortcut:
            print(f"Could not find a Steam library entry named '{app_id}'.")
            sys.exit(1)
        print(f"Found '{shortcut['name']}' -> {shortcut['exe']}")
        launch_by_target_path(shortcut["exe"], shortcut.get("start_dir"), shortcut.get("launch_options", ""))