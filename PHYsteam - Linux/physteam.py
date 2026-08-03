"""physteam.py — PHYsteam (Linux)"""

import psutil, time, subprocess, os, sys, json, logging, re, threading, shutil

BASE_DIR         = os.path.dirname(os.path.abspath(__file__))
LOG_FILE         = os.path.join(BASE_DIR, "physteam.log")
CONFIG_FILE      = os.path.join(BASE_DIR, "physteam_config.json")
KNOWN_GAMES_FILE = os.path.join(BASE_DIR, "physteam_known_games.json")
GAME_SCRIPT_NAME          = "launch_game_linux.py"
POLL_INTERVAL             = 0.5
CAPACITY_CHANGE_THRESHOLD = 10 * 1024 * 1024
APP_NAME = "PHYsteam"


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

# ── Setup (terminal prompt, no tkinter needed) ────────────────────────────────
def show_setup_gui():
    def drives_list():
        out = []
        for p in psutil.disk_partitions():
            try:
                gb = psutil.disk_usage(p.mountpoint).total / (1024**3)
                out.append(f"{p.mountpoint}  ({gb:.1f} GB)")
            except Exception:
                out.append(f"{p.mountpoint}  (? GB)")
        return out

    print()
    print(f"  ╔══════════════════════════════════════╗")
    print(f"  ║          {APP_NAME} — Setup             ║")
    print(f"  ╚══════════════════════════════════════╝")
    print()

    drives = drives_list()
    options = ["Auto-detect last removable drive"] + drives

    print("  Which drive should be watched for game cartridge activity?")
    print()
    for i, opt in enumerate(options):
        print(f"    [{i}] {opt}")
    print()

    while True:
        try:
            choice = input(f"  Enter number (0–{len(options)-1}): ").strip()
            idx = int(choice)
            if 0 <= idx < len(options):
                break
            print(f"  Please enter a number between 0 and {len(options)-1}.")
        except (ValueError, EOFError):
            print("  Invalid input.")

    print()
    print("  Require game cartridge to play tracked games?")
    print("  When enabled: games previously launched via cartridge will be")
    print("  force-closed if started without the cartridge inserted.")
    print()
    while True:
        req = input("  Enable cartridge enforcement? (y/N): ").strip().lower()
        if req in ("y", "n", ""):
            require_card = req == "y"
            break
        print("  Please enter y or n.")

    print()
    if idx == 0:
        cfg = {"mode": "auto", "require_card": require_card}
    else:
        drive = options[idx].split("  ")[0]
        cfg = {"mode": "fixed", "drive": drive, "require_card": require_card}

    print(f"  Selected: {options[idx]}")
    print(f"  Cartridge enforcement: {'enabled' if require_card else 'disabled'}")
    print()
    confirm = input("  Confirm setup? (Y/n): ").strip().lower()
    if confirm in ("", "y"):
        return cfg
    print("  Setup cancelled.")
    return None

# ── Steam ──────────────────────────────────────────────────────────────────────
def find_steam_root():
    home = os.path.expanduser("~")
    candidates = [
        os.path.join(home, ".local/share/Steam"),
        os.path.join(home, ".steam/steam"),
        os.path.join(home, ".steam/root"),
        os.path.join(home, ".var/app/com.valvesoftware.Steam/data/Steam"),          # Flatpak
        os.path.join(home, ".var/app/com.valvesoftware.Steam/.local/share/Steam"),  # Flatpak alt
        os.path.join(home, "snap/steam/common/.local/share/Steam"),                 # Snap
    ]
    for p in candidates:
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
                sa = os.path.join(m.group(1), "steamapps")
                if os.path.isdir(sa) and sa not in libs: libs.append(sa)
        except Exception as e: log(f"VDF parse error: {e}")
    return libs

def find_install_path(app_id):
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

def read_app_id(script_path):
    try:
        txt = open(script_path).read()
        m = re.search(r'STEAM_APP_ID\s*=\s*["\\\']?(\d+)["\\\']?', txt)
        if m: return m.group(1)
    except Exception as e: log(f"Could not read STEAM_APP_ID: {e}")
    return None

def kill_game(app_id, install_path, tag=""):
    """
    Terminate a game's processes. Matches three ways so Proton/Wine games are
    caught too (their 'exe' often doesn't point inside the install folder):
      1. exe path starts with the install folder (native Linux games)
      2. install folder path appears anywhere in the full command line
         (Proton passes the real .exe path as an argument to wine)
      3. "appid=<id>" appears in the command line (Steam's own launch tag)
    """
    prefix = f"[{tag}] " if tag else ""
    low = (install_path or "").lower()
    app_tag = f"appid={app_id}".lower() if app_id else None
    killed = 0
    for proc in psutil.process_iter(["pid", "name", "exe", "cmdline"]):
        try:
            exe = (proc.info.get("exe") or "").lower()
            cmdline = " ".join(proc.info.get("cmdline") or []).lower()
            match = (low and exe.startswith(low)) or \
                    (low and low in cmdline) or \
                    (app_tag and app_tag in cmdline)
            if match:
                log(f"{prefix}Closing {proc.info['name']} (PID {proc.info['pid']}) for App {app_id}.")
                proc.terminate(); killed += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied): pass
    if killed:
        log(f"{prefix}Closed {killed} process(es) for App {app_id}.")
    else:
        log(f"{prefix}No processes found for App {app_id} ('{install_path}').")
    return killed

# ── Removable drive detection (Linux uses sysfs, not psutil opts) ──────────────
def _block_base_name(devnode):
    name = os.path.basename(devnode)
    m = re.match(r'^(nvme\d+n\d+|mmcblk\d+|sd[a-z]+|sr\d+|vd[a-z]+)', name)
    return m.group(1) if m else re.sub(r'\d+$', '', name)

def is_removable(devnode):
    try:
        base = _block_base_name(devnode)
        with open(f"/sys/block/{base}/removable") as f:
            return f.read().strip() == "1"
    except Exception:
        return False

def get_removable_drives():
    drives = set()
    for p in psutil.disk_partitions():
        try:
            if is_removable(p.device):
                drives.add(p.mountpoint)
        except Exception:
            pass
    return drives

def handle_insert(drive, require_card=False):
    # Only treat as a game cartridge if the drive has less than 8 MB used
    try:
        used = psutil.disk_usage(drive).used
        if used >= 8 * 1024 * 1024:
            log(f"Drive {drive} has {used} bytes used (>=8MB) — not a game cartridge, skipping.")
            return None
    except Exception as e:
        log(f"Could not read usage for {drive}: {e}")

    sp = os.path.join(drive, GAME_SCRIPT_NAME)
    if not os.path.isfile(sp): log(f"No {GAME_SCRIPT_NAME} on {drive}."); return None
    app_id = read_app_id(sp)
    ip = None
    if app_id:
        ip = find_install_path(app_id)
        if require_card and ip: register_game(app_id, ip)
    else:
        log("No STEAM_APP_ID — game won't close on removal.")
    log(f"Launching {sp} ...")
    try: subprocess.Popen([sys.executable, sp], cwd=drive); log("Launched.")
    except Exception as e: log(f"Launch error: {e}")
    if not app_id: return None
    return (app_id, ip)

def handle_remove(drive, app_id, ip):
    log(f"Cartridge removed from {drive}.")
    kill_game(app_id, ip, tag="REMOVE")

# ── Enforcer ───────────────────────────────────────────────────────────────────
cartridge_present = threading.Event()

def show_popup(message, title="PHYsteam"):
    """Show a desktop notification. Tries notify-send, then zenity, then logs only."""
    def _show():
        if shutil.which("notify-send"):
            try:
                subprocess.run(["notify-send", title, message]); return
            except Exception: pass
        if shutil.which("zenity"):
            try:
                subprocess.run(["zenity", "--info", f"--title={title}", f"--text={message}"]); return
            except Exception: pass
        log(f"[POPUP] {title}: {message}")
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
                killed = kill_game(app_id, ip, tag="ENFORCER")
                if killed:
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
                if drive == new_drives[-1]:
                    result = handle_insert(drive, require_card)
                    if result is not None: tracked[drive] = result
                    cartridge_present.set()
                else: log(f"Drive {drive} not last — ignoring.")
            for drive in known - cur:
                if drive in tracked:
                    app_id, ip = tracked.pop(drive)
                    handle_remove(drive, app_id, ip)
                else: log(f"Drive {drive} removed but not tracked.")
                if not tracked: cartridge_present.clear()
            known = cur
        except Exception as e: log(f"Auto mode error: {e}")

# ── Fixed mode ─────────────────────────────────────────────────────────────────
def get_free(drive):
    try: return psutil.disk_usage(drive).free
    except Exception: return None

def run_fixed(drive, require_card=False):
    log(f"PHYsteam FIXED mode ({drive}) | require_card={require_card}")
    last = get_free(drive); running = False; cur_app_id = None; cur_ip = None; cartridge_present.clear()
    while True:
        time.sleep(POLL_INTERVAL)
        try:
            cur = get_free(drive)
            if cur is None:
                if running: handle_remove(drive, cur_app_id, cur_ip); running = False; cur_app_id = None; cur_ip = None; cartridge_present.clear()
                last = None; continue
            if last is None:
                last = cur; result = handle_insert(drive, require_card)
                if result: cur_app_id, cur_ip = result; running = True; cartridge_present.set()
                continue
            if abs(cur - last) >= CAPACITY_CHANGE_THRESHOLD:
                if running: handle_remove(drive, cur_app_id, cur_ip); running = False; cur_app_id = None; cur_ip = None; cartridge_present.clear()
                time.sleep(1)
                result = handle_insert(drive, require_card)
                if result: cur_app_id, cur_ip = result; running = True; cartridge_present.set()
                last = cur
        except Exception as e: log(f"Fixed mode error: {e}")

# ── Main ───────────────────────────────────────────────────────────────────────
def main():
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
        # Started automatically (e.g. at login via systemd) with no config yet.
        # Never show the setup window here — only the installer should configure it.
        log("No config found and not in configure mode. Run install_physteam.sh to set up PHYsteam. Exiting.")
        sys.exit(0)

    req = cfg.get("require_card", False)
    log(f"PHYsteam starting | {cfg}")
    if req: threading.Thread(target=enforcer_thread, daemon=True).start()
    if cfg.get("mode") == "fixed":
        d = cfg.get("drive")
        if not d: log("No drive in config. Delete physteam_config.json to reconfigure."); sys.exit(1)
        run_fixed(d, req)
    else:
        run_auto(req)

if __name__ == "__main__":
    main()
