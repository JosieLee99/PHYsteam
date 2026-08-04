"""physteam.py — PHYsteam"""

import psutil, time, subprocess, os, sys, json, logging, re, threading, base64, tempfile, ctypes, shutil

BASE_DIR         = os.path.dirname(os.path.abspath(__file__))
LOG_FILE         = os.path.join(BASE_DIR, "physteam.log")
CONFIG_FILE      = os.path.join(BASE_DIR, "physteam_config.json")
KNOWN_GAMES_FILE = os.path.join(BASE_DIR, "physteam_known_games.json")
POLL_INTERVAL             = 0.5
APP_NAME = "PHYsteam"

ICON_B64 = 'AAABAAEAEBAAAAAAIADfAwAAFgAAAIlQTkcNChoKAAAADUlIRFIAAAAQAAAAEAgGAAAAH/P/YQAAAQhpQ0NQSUNDIFByb2ZpbGUAAHicY2BgPMEABCwGDAy5eSVFQe5OChGRUQrsDxgYgRAMEpOLCxhwA6Cqb9cgai/r4lGHC3CmpBYnA+kPQKxSBLQcaKQIkC2SDmFrgNhJELYNiF1eUlACZAeA2EUhQc5AdgqQrZGOxE5CYicXFIHU9wDZNrk5pckIdzPwpOaFBgNpDiCWYShmCGJwZ3AC+R+iJH8RA4PFVwYG5gkIsaSZDAzbWxkYJG4hxFQWMDDwtzAwbDuPEEOESUFiUSJYiAWImdLSGBg+LWdg4I1kYBC+wMDAFQ0LCBxuUwC7zZ0hHwjTGXIYUoEingx5DMkMekCWEYMBgyGDGQCm1j8/R2zgUAAAApJJREFUeJytk81rFWcUxn/v+87MHe/3XHJvTDAxMSjGLkIrNaVqdSWixS5LV91U0IWIIoiuREr/gP4LpdCqabWIReq226qIiVoLQsSa+JWUe9+ZuXfeOV3cECJm6Vk/58dzOM+jAGHNaONTLLUohFW0CQDIXY80WcZ2Fsldb60ctRZQLA9Sro9gvALIW1xQCpeltJfmse2FtQAlIFSjMSrRKIockRzoM/I8X5EKSmmU9mgvzfPfmyeAwgOhWG5RiUaJbRsbJ6uegsCnVCquwvrndKlGo2Q9i20v4mkTUIk2k8SWbVvHmd41hTGGLHPMPXjMX7fvo7XB8wxp2sXzDNZ2qNQ3k8RLUK4Oy8jEZ1KoTMqZs9+JiEiaJmLjWERErl67KcNjn0qt9aEcPX5Ofvr5mhz8/GtpDH0s1fom0cGGGoKglCJOEpxzfHPsPKXyJFdmbvDFkQMMD7UoFTfw1ZeH2b9vmkMH9+OcoxDW8YwO+jcrUEpjjKHRqDOxZZSBZgOAPbt3MjE+wr69n/DDj79w9bdbGKNR2ofm0JRs2rJXwtoOOXn6ooiIWGvFuUzSNJWZX3+XV6/fyPz8Uzlx6oI0Nu6UaONHMjy2W5pDU+I5111NQ+YczjkufPs9f9z6kzzPmZ17zPSuKT6YnODSzE2CwMcYjYjgXBevmyxTqjQREQoFH2MMz/5d4PadWVqtAQYHB5id+4e79x5SXnlpnuco7dFNltG285JeLyEMQx79/YRLl6/zfOEVUVTD9z2yzBGGAZVyCRFBREBpXJZiOy/75ovlFlFrO7FtE8cJxVKRwPf74ndG0CZg6cVDbHtx/Sg7l60sq7cW14vy+yjTenVuEoQ1zEqdnevSTZaxnRfv1Pl/2HdGDhKG844AAAAASUVORK5CYII='

ICON_PNG_B64 = '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'

ICON_TITLE_B64 = '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'

def extract_icon():
    try:
        tmp = tempfile.NamedTemporaryFile(suffix=".ico", delete=False)
        tmp.write(base64.b64decode(ICON_B64)); tmp.close()
        return tmp.name
    except Exception:
        return None

logging.basicConfig(filename=LOG_FILE, level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
def log(msg): logging.info(msg); print(msg)

def load_config():
    try:
        with open(CONFIG_FILE) as f: return json.load(f)
    except Exception: return None

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f: json.dump(cfg, f, indent=2)
    log(f"Config saved: {cfg}")

def load_known_games():
    try:
        with open(KNOWN_GAMES_FILE) as f: return json.load(f)
    except Exception: return {}

def save_known_games(d):
    with open(KNOWN_GAMES_FILE, "w") as f: json.dump(d, f, indent=2)

def register_game(app_id, path):
    k = load_known_games()
    if app_id not in k:
        k[app_id] = path; save_known_games(k)
        log(f"Registered game App ID {app_id}: {path}")
    else:
        log(f"App ID {app_id} already registered.")

# ── GUI ────────────────────────────────────────────────────────────────────────
def show_setup_gui():
    import tkinter as tk
    from tkinter import ttk
    result = {}

    root = tk.Tk()
    root.title(f"{APP_NAME} \u2014 Setup")
    root.resizable(False, False)
    root.geometry("460x295")
    root.update_idletasks()
    root.geometry(f"460x295+{(root.winfo_screenwidth()-460)//2}+{(root.winfo_screenheight()-295)//2}")

    ico = extract_icon()
    # Use iconphoto for sharper title bar icon (better than iconbitmap on modern Windows)
    try:
        title_photo = tk.PhotoImage(data=ICON_TITLE_B64)
        root.iconphoto(True, title_photo)
    except Exception:
        if ico:
            try: root.iconbitmap(ico)
            except Exception: pass

    # ── Header with icon + title ──────────────────────────────────────────────
    hdr = tk.Frame(root, bg="#1b2838"); hdr.pack(fill="x")
    hdr_inner = tk.Frame(hdr, bg="#1b2838"); hdr_inner.pack(pady=(10, 0))

    # Display icon in header using embedded PNG (no Pillow needed)
    try:
        photo = tk.PhotoImage(data=ICON_PNG_B64)
        icon_lbl = tk.Label(hdr_inner, image=photo, bg="#1b2838")
        icon_lbl.image = photo  # keep reference
        icon_lbl.pack(side="left", padx=(0, 8))
    except Exception:
        pass

    tk.Label(hdr_inner, text=APP_NAME, font=("Segoe UI", 15, "bold"),
             bg="#1b2838", fg="#66c0f4").pack(side="left")
    tk.Label(hdr, text="Setup", font=("Segoe UI", 9),
             bg="#1b2838", fg="#c7d5e0").pack(pady=(2, 8))

    tk.Frame(root, height=8).pack()
    tk.Label(root, text="PHYsteam will watch every drive on this PC for game cartridge activity.",
             font=("Segoe UI", 9), wraplength=420, justify="center").pack(pady=(4,12))

    req_var = tk.BooleanVar(value=False)
    cbf = tk.Frame(root); cbf.pack(pady=(0,4))
    ttk.Checkbutton(cbf, text="Require game cartridge to play tracked games",
                    variable=req_var).pack(side="left")
    tk.Label(root,
             text="When checked: games previously launched via game cartridge\n"
                  "will be force-closed if started without the cartridge inserted.",
             font=("Segoe UI", 8), fg="gray", justify="center",
             wraplength=420).pack(pady=(0,14))

    def confirm():
        result["cfg"] = {"mode": "auto", "require_card": req_var.get()}
        root.destroy()

    bf = tk.Frame(root); bf.pack()
    tk.Button(bf, text="Confirm", width=12, command=confirm,
              bg="#4c6b8a", fg="white", relief="flat", padx=6, pady=4).pack(side="left", padx=6)
    tk.Button(bf, text="Cancel", width=12, command=root.destroy,
              relief="flat", padx=6, pady=4).pack(side="left", padx=6)
    root.mainloop()
    return result.get("cfg")

# ── Steam ──────────────────────────────────────────────────────────────────────
def find_steam_root():
    for p in [os.path.expandvars(r"%ProgramFiles(x86)%\\Steam"),
              os.path.expandvars(r"%ProgramFiles%\\Steam"), r"C:\\Steam"]:
        if os.path.isdir(p): return p
    return None

def find_steam_libraries(steam_root):
    libs = []
    default = os.path.join(steam_root, "steamapps")
    if os.path.isdir(default): libs.append(default)
    vdf = os.path.join(default, "libraryfolders.vdf")
    if os.path.isfile(vdf):
        try:
            txt = open(vdf, encoding="utf-8").read()
            for m in re.finditer(r'"path"\s+"([^"]+)"', txt):
                sa = os.path.join(m.group(1).replace("\\\\", "\\"), "steamapps")
                if os.path.isdir(sa) and sa not in libs: libs.append(sa)
        except Exception as e: log(f"VDF parse error: {e}")
    return libs

def find_install_path(app_id):
    app_id = app_id.strip()
    if app_id.isdigit():
        return find_steam_app_install_path(app_id)
    return find_non_steam_install_path(app_id)

def find_steam_app_install_path(app_id):
    root = find_steam_root()
    if not root: log("Steam not found."); return None
    for lib in find_steam_libraries(root):
        mf = os.path.join(lib, f"appmanifest_{app_id}.acf")
        if os.path.isfile(mf):
            try:
                txt = open(mf, encoding="utf-8").read()
                m = re.search(r'"installdir"\s+"([^"]+)"', txt)
                if m:
                    p = os.path.join(lib, "common", m.group(1))
                    log(f"Install path for {app_id}: {p}"); return p
            except Exception as e: log(f"Manifest error: {e}")
    log(f"No manifest for App ID {app_id}."); return None

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
        log("Steam not found."); return None
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
            log(f"Could not parse {vdf_path}: {e}"); continue

        shortcuts = None
        for k, v in root.items():
            if k.lower() == "shortcuts" and isinstance(v, dict):
                shortcuts = v; break
        if not shortcuts:
            continue

        for entry in shortcuts.values():
            if not isinstance(entry, dict):
                continue
            app_name = exe = start_dir = None
            for k, v in entry.items():
                kl = k.lower()
                if kl == "appname": app_name = v
                elif kl == "exe": exe = v
                elif kl == "startdir": start_dir = v
            if app_name and exe:
                matches.append({
                    "name": app_name,
                    "exe": exe.strip().strip('"'),
                    "start_dir": (start_dir.strip().strip('"') if start_dir else None),
                })

    if not matches:
        return None
    for m in matches:
        if m["name"].strip().lower() == target:
            return m
    for m in matches:
        if target in m["name"].strip().lower():
            return m
    return None

def find_non_steam_install_path(app_id):
    """For a non-Steam shortcut (emulator, etc), 'install path' is the
    folder the target exe lives in -- that's what kill_by_path matches
    running processes against."""
    shortcut = find_non_steam_shortcut(app_id)
    if not shortcut:
        log(f"No Steam shortcut found named '{app_id}'."); return None
    p = shortcut.get("start_dir") or os.path.dirname(shortcut["exe"])
    if p: log(f"Install path for shortcut '{app_id}': {p}")
    return p

def add_steam_library(library_path):
    """If library_path already has a Steam library (a 'steamapps' folder) in it,
    register that path in Steam's libraryfolders.vdf so Steam picks it up."""
    steamapps_dir = os.path.join(library_path, "steamapps")
    if not os.path.isdir(steamapps_dir):
        return False

    steam_root = find_steam_root()
    if not steam_root:
        log("Steam not found — can't register library.")
        return False

    vdf_path = os.path.join(steam_root, "steamapps", "libraryfolders.vdf")
    if not os.path.isfile(vdf_path):
        log("libraryfolders.vdf not found — can't register library.")
        return False

    try:
        with open(vdf_path, encoding="utf-8") as f:
            text = f.read()
    except Exception as e:
        log(f"Could not read libraryfolders.vdf: {e}")
        return False

    drive_path = library_path.rstrip("\\/")
    escaped_path = drive_path.replace("\\", "\\\\")

    registered = set(re.findall(r'"path"\s+"([^"]+)"', text))
    if escaped_path in registered or drive_path in registered:
        log(f"{drive_path} is already registered as a Steam library.")
        return True

    indices = [int(i) for i in re.findall(r'"(\d+)"\s*\r?\n\s*\{', text)]
    next_index = (max(indices) + 1) if indices else 0

    entry = (
        f'\t"{next_index}"\n'
        f'\t{{\n'
        f'\t\t"path"\t\t"{escaped_path}"\n'
        f'\t\t"label"\t\t""\n'
        f'\t\t"contentid"\t\t"0"\n'
        f'\t\t"totalsize"\t\t"0"\n'
        f'\t\t"update_clean_bytes_tally"\t\t"0"\n'
        f'\t\t"time_last_update_corruption"\t\t"0"\n'
        f'\t\t"apps"\n'
        f'\t\t{{\n'
        f'\t\t}}\n'
        f'\t}}\n'
    )

    close_idx = text.rstrip().rfind("}")
    if close_idx == -1:
        log("Could not parse libraryfolders.vdf structure — skipping registration.")
        return False
    new_text = text[:close_idx] + entry + text[close_idx:]

    try:
        with open(vdf_path, "w", encoding="utf-8") as f:
            f.write(new_text)
        log(f"Registered {drive_path} as Steam library #{next_index}.")
        return True
    except Exception as e:
        log(f"Could not write libraryfolders.vdf: {e}")
        return False

def read_app_id(script_path):
    # Preferred: a plain-text game_id.txt next to the launcher. This is what
    # lets a single compiled launch_game.exe be reused across cartridges —
    # you can't regex an App ID out of compiled exe bytes, but a companion
    # text file works the same way for a .py launcher or a compiled one.
    id_file = os.path.join(os.path.dirname(script_path), "game_id.txt")
    if os.path.isfile(id_file):
        try:
            val = open(id_file, encoding="utf-8").read().strip()
            if val: return val
        except Exception as e: log(f"Could not read game_id.txt: {e}")

    # Fallback: regex the STEAM_APP_ID out of the launcher's own source,
    # for old-style cartridges that still ship launch_game_windows.py as
    # a plain, uncompiled script.
    try:
        txt = open(script_path, errors="ignore").read()
        m = re.search(r'STEAM_APP_ID\s*=\s*["\'\']?(\d+)["\'\']?', txt)
        if m: return m.group(1)
    except Exception as e: log(f"Could not read STEAM_APP_ID: {e}")
    return None

def kill_by_path(install_path):
    low = install_path.lower(); killed = 0
    for proc in psutil.process_iter(["pid", "name", "exe"]):
        try:
            if (proc.info.get("exe") or "").lower().startswith(low):
                log(f"Closing {proc.info['name']} PID {proc.info['pid']}")
                proc.terminate(); killed += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied): pass
    log(f"Closed {killed} process(es)." if killed else f"No processes found under '{install_path}'.")

# ── Shared ─────────────────────────────────────────────────────────────────────
def get_removable_drives():
    # Use all=True so drive letters (like an empty DVD drive) are always visible,
    # then only count a drive as "present" once it actually has media mounted
    # (non-empty fstype). This avoids relying on psutil's all=False heuristics,
    # which don't reliably hide not-ready optical drives on every system.
    result = set()
    for p in psutil.disk_partitions(all=True):
        if ("removable" in p.opts or "cdrom" in p.opts) and p.fstype:
            result.add(p.device)
    return result

def find_interpreter():
    """Return a Python interpreter to run a .py cartridge launcher with.
    When physteam.py itself is run as a plain script, sys.executable is a
    real Python interpreter and works fine. But once physteam.py is frozen
    into PHYsteam_Engine.exe (PyInstaller), sys.executable points at the
    frozen exe itself, not at Python -- so it can no longer be used to run
    a .py file. In that case, look for an actual interpreter on PATH."""
    if not getattr(sys, "frozen", False):
        return sys.executable
    for name in ("pythonw", "pythonw3", "python", "python3"):
        found = shutil.which(name)
        if found: return found
    return None

def find_game_script(drive):
    """Return the path to this platform's launch_game script on the drive.
    If a launcher matching the current OS exists (launch_game_windows.py on
    Windows, launch_game_linux.py elsewhere), it's preferred; otherwise falls
    back to the first file starting with 'launch_game' found on the drive."""
    try:
        entries = sorted(os.listdir(drive))
    except Exception as e:
        log(f"Could not list files on {drive}: {e}")
        return None

    candidates = [n for n in entries
                  if os.path.isfile(os.path.join(drive, n)) and n.lower().startswith("launch_game")]
    if not candidates:
        return None

    preferred = "launch_game_windows" if sys.platform.startswith("win") else "launch_game_linux"
    for name in candidates:
        if os.path.splitext(name)[0].lower() == preferred:
            return os.path.join(drive, name)

    log(f"No launcher matching this platform ({preferred}) found on {drive} — "
        f"falling back to {candidates[0]}.")
    return os.path.join(drive, candidates[0])

def handle_insert(drive, require_card=False):
    # If the drive has a "SteamLibrary" folder containing a Steam library on it,
    # register that folder with Steam.
    library_root = os.path.join(drive, "SteamLibrary")
    has_library = os.path.isdir(os.path.join(library_root, "steamapps"))
    if has_library:
        add_steam_library(library_root)
        log(f"Drive {drive} has a Steam library at {library_root} — treating as a cartridge.")

    # Having the game's files on the drive is optional — any drive with a
    # launch_game script is treated as a cartridge, regardless of size.
    sp = find_game_script(drive)
    if not sp: log(f"No file starting with 'launch_game' on {drive}."); return None
    app_id = read_app_id(sp)
    ip = None
    if app_id:
        ip = find_install_path(app_id)
        if require_card and ip: register_game(app_id, ip)
    else:
        log("No STEAM_APP_ID — game won't close on removal.")
    log(f"Launching {sp} ...")
    try:
        if sp.lower().endswith(".exe"):
            subprocess.Popen([sp], cwd=drive)
        else:
            interp = find_interpreter()
            if not interp:
                log("Cartridge launcher is a .py script but no Python interpreter "
                    "was found on this machine, and PHYsteam is running as a "
                    "compiled exe (so it can't run it directly either). Either "
                    "install Python on this machine, or rebuild this cartridge's "
                    "launcher as an .exe (see launch_game_windows.py).")
                return None
            subprocess.Popen([interp, sp], cwd=drive)
        log("Launched.")
    except Exception as e: log(f"Launch error: {e}")
    return ip

def handle_remove(drive, ip):
    log(f"Cartridge removed from {drive}.")
    if ip: kill_by_path(ip)
    else: log("No install path — nothing to close.")

# ── Enforcer ───────────────────────────────────────────────────────────────────
cartridge_present = threading.Event()

def show_popup(message, title="PHYsteam"):
    """Show a Windows message box in its own thread so it never blocks the watcher."""
    def _show():
        try:
            MB_OK = 0x0
            MB_ICONINFORMATION = 0x40
            MB_TOPMOST = 0x40000
            ctypes.windll.user32.MessageBoxW(0, message, title, MB_OK | MB_ICONINFORMATION | MB_TOPMOST)
        except Exception as e:
            log(f"Popup error: {e}")
    threading.Thread(target=_show, daemon=True).start()

def enforcer_thread():
    log("PHYsteam enforcer active.")
    while True:
        time.sleep(POLL_INTERVAL)
        try:
            if cartridge_present.is_set(): continue
            known = load_known_games()
            if not known: continue
            for app_id, ip in known.items():
                if not ip:
                    ip = find_install_path(app_id)
                    if ip: known[app_id] = ip; save_known_games(known)
                    else: continue
                low = ip.lower()
                killed_any = False
                for proc in psutil.process_iter(["pid", "name", "exe"]):
                    try:
                        if (proc.info.get("exe") or "").lower().startswith(low):
                            log(f"[ENFORCER] '{proc.info['name']}' (App {app_id}) launched without card — terminating.")
                            proc.terminate()
                            killed_any = True
                    except (psutil.NoSuchProcess, psutil.AccessDenied): pass
                if killed_any:
                    show_popup("Please insert this games cartridge.")
        except Exception as e: log(f"Enforcer error: {e}")

# ── Auto mode ──────────────────────────────────────────────────────────────────
def run_auto(require_card=False):
    log(f"PHYsteam AUTO mode | require_card={require_card}")
    known = get_removable_drives(); tracked = {}; cartridge_present.clear()
    while True:
        time.sleep(POLL_INTERVAL)
        try:
            cur = get_removable_drives()
            new_drives = sorted(cur - known)
            for drive in new_drives:
                ip = handle_insert(drive, require_card)
                if ip is not None: tracked[drive] = ip
            if new_drives: cartridge_present.set()
            for drive in known - cur:
                if drive in tracked: handle_remove(drive, tracked.pop(drive))
                else: log(f"Drive {drive} removed but not tracked.")
                if not tracked: cartridge_present.clear()
            known = cur
        except Exception as e: log(f"Auto mode error: {e}")

# ── Main ───────────────────────────────────────────────────────────────────────
def debug_drives():
    print("Insert/eject drives and watch this list. Press Ctrl+C to stop.\n")
    while True:
        print(f"--- {time.strftime('%H:%M:%S')} ---")
        print("[all=False, what get_removable_drives() actually sees]")
        for p in psutil.disk_partitions(all=False):
            print(f"device={p.device!r} fstype={p.fstype!r} opts={p.opts!r}")
        print("[all=True, full picture]")
        for p in psutil.disk_partitions(all=True):
            try:
                usage = psutil.disk_usage(p.mountpoint)
                size_info = f"total={usage.total} used={usage.used} free={usage.free}"
            except Exception as e:
                size_info = f"disk_usage() failed: {e}"
            print(f"device={p.device!r} mountpoint={p.mountpoint!r} "
                  f"fstype={p.fstype!r} opts={p.opts!r} | {size_info}")
        print()
        time.sleep(2)


def main():
    if "--debug-drives" in sys.argv:
        debug_drives()
        return

    configure_requested = "--configure" in sys.argv
    cfg = load_config()

    if configure_requested:
        log("Configure requested — showing PHYsteam setup.")
        new_cfg = show_setup_gui()
        if new_cfg is None:
            if cfg is None:
                log("Setup cancelled and no existing config. Exiting.")
                sys.exit(0)
            log("Setup cancelled — keeping existing config.")
        else:
            cfg = new_cfg
            save_config(cfg)
    elif cfg is None:
        # Started automatically (e.g. at login) with no config yet.
        # Never show the setup window here — only the installer should configure it.
        log("No config found and not in configure mode. Run install_physteam.bat to set up PHYsteam. Exiting.")
        sys.exit(0)

    req = cfg.get("require_card", False)
    log(f"PHYsteam starting | {cfg}")
    if req: threading.Thread(target=enforcer_thread, daemon=True).start()
    # PHYsteam always watches every drive on the system — no drive selection.
    run_auto(req)

if __name__ == "__main__":
    main()
