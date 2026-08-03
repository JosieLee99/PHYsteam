"""physteam.py — PHYsteam (Linux console edition)

Standard-library only: no pip installs required (no psutil, no tkinter).
Autostart is handled by install_physteam.sh (systemd --user service, with a
crontab @reboot fallback if systemd isn't available).
"""

import os, sys, time, json, logging, re, threading, subprocess, shutil, signal

BASE_DIR         = os.path.dirname(os.path.abspath(__file__))
LOG_FILE         = os.path.join(BASE_DIR, "physteam.log")
CONFIG_FILE      = os.path.join(BASE_DIR, "physteam_config.json")
KNOWN_GAMES_FILE = os.path.join(BASE_DIR, "physteam_known_games.json")
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

# ── Console setup ────────────────────────────────────────────────────────────
def show_setup_console():
    mounts = sorted(get_removable_drives())
    print(f"\n{APP_NAME} \u2014 Setup")
    print("-" * 30)
    print("0) No specific drive \u2014 auto-detect last removable")
    for i, m in enumerate(mounts, start=1):
        try:
            total = shutil.disk_usage(m).total / (1024 ** 3)
            print(f"{i}) {m}  ({total:.1f} GB)")
        except Exception:
            print(f"{i}) {m}")
    if not mounts:
        print("(No removable drives detected right now \u2014 that's fine, auto-detect")
        print(" mode will still work once you plug one in.)")

    choice = input("\nSelect an option [0]: ").strip() or "0"
    try:
        idx = int(choice)
    except ValueError:
        idx = 0

    if idx <= 0 or idx > len(mounts):
        cfg = {"mode": "auto"}
    else:
        cfg = {"mode": "fixed", "drive": mounts[idx - 1]}

    req = input("Require game cartridge to keep playing tracked games? (y/N): ").strip().lower()
    cfg["require_card"] = req in ("y", "yes")

    print(f"\nConfig: {cfg}")
    return cfg

# ── Steam ──────────────────────────────────────────────────────────────────────
def find_steam_root():
    home = os.path.expanduser("~")
    for p in [
        os.path.join(home, ".local", "share", "Steam"),
        os.path.join(home, ".steam", "steam"),
        os.path.join(home, ".steam", "root"),
        os.path.join(home, ".var", "app", "com.valvesoftware.Steam", "data", "Steam"),
        "/usr/share/steam",
    ]:
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

    drive_path = library_path.rstrip("/")
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

LIBRARY_WAIT_TIMEOUT  = 20   # seconds to wait for Steam to recognize a new library
LIBRARY_WAIT_INTERVAL = 1    # seconds between polls

def wait_for_library_registration(library_path, app_id=None, timeout=LIBRARY_WAIT_TIMEOUT,
                                   poll_interval=LIBRARY_WAIT_INTERVAL):
    """Poll libraryfolders.vdf until Steam has actually scanned the newly
    registered library in. If app_id is given, waits for that specific App ID
    to appear in the library's 'apps' block (the strongest signal Steam has
    indexed it); otherwise waits for the 'apps' block to be non-empty at all.
    Returns True if detected within the timeout, False if it timed out
    (caller should proceed anyway — Steam may still pick it up later)."""
    steam_root = find_steam_root()
    if not steam_root:
        return False
    vdf_path = os.path.join(steam_root, "steamapps", "libraryfolders.vdf")

    drive_path = library_path.rstrip("/")
    escaped_path = drive_path.replace("\\", "\\\\")

    deadline = time.time() + timeout
    while True:
        try:
            with open(vdf_path, encoding="utf-8") as f:
                text = f.read()
        except Exception:
            text = ""

        for m in re.finditer(r'"path"\s+"([^"]+)"', text):
            if m.group(1) not in (escaped_path, drive_path):
                continue
            apps_match = re.search(r'"apps"\s*\{([^}]*)\}', text[m.end():m.end() + 4000])
            if apps_match:
                apps_block = apps_match.group(1)
                if app_id and f'"{app_id}"' in apps_block:
                    return True
                if not app_id and apps_block.strip():
                    return True

        if time.time() >= deadline:
            return False
        time.sleep(poll_interval)

def read_app_id(script_path):
    try:
        txt = open(script_path).read()
        m = re.search(r'STEAM_APP_ID\s*=\s*["\'\']?(\d+)["\'\']?', txt)
        if m: return m.group(1)
    except Exception as e: log(f"Could not read STEAM_APP_ID: {e}")
    return None

def kill_by_app_id(app_id):
    """Terminate the Steam-launched process for this App ID by finding the
    'reaper' process Steam uses to launch every game (its cmdline contains
    'AppId=<app_id>') and signalling it. Steam's reaper is specifically
    designed so that killing it takes the whole game process tree down with
    it — this works for native Linux games AND Proton/Wine games (where
    the actual running exe is wine64/the Proton wrapper, not anything under
    the game's own install folder, so path-based matching can't find it),
    and regardless of which Steam library the game is installed to."""
    marker = f"AppId={app_id}"
    killed = 0
    try:
        pids = [p for p in os.listdir("/proc") if p.isdigit()]
    except Exception as e:
        log(f"Could not list /proc: {e}")
        return False
    for pid in pids:
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as f:
                cmdline = f.read().replace(b"\x00", b" ").decode(errors="replace")
        except Exception:
            continue
        if marker in cmdline:
            try:
                os.kill(int(pid), signal.SIGTERM)
                log(f"Closing PID {pid} (Steam launcher for App ID {app_id})")
                killed += 1
            except Exception as e:
                log(f"Could not kill PID {pid}: {e}")
    if killed:
        log(f"Closed {killed} launcher process(es) for App ID {app_id}.")
    else:
        log(f"No running Steam launcher process found for App ID {app_id}.")
    return killed > 0

def kill_by_path(install_path):
    """Terminate any running process whose executable lives under install_path.
    Uses /proc directly — no psutil required. Kept as a fallback for cases
    where kill_by_app_id can't find a match (e.g. no App ID was readable)."""
    low = install_path.rstrip("/")
    killed = 0
    try:
        pids = [p for p in os.listdir("/proc") if p.isdigit()]
    except Exception as e:
        log(f"Could not list /proc: {e}")
        return
    for pid in pids:
        try:
            exe = os.readlink(f"/proc/{pid}/exe")
        except Exception:
            continue
        if exe.startswith(low):
            try:
                os.kill(int(pid), signal.SIGTERM)
                log(f"Closing PID {pid} ({exe})")
                killed += 1
            except Exception as e:
                log(f"Could not kill PID {pid}: {e}")
    log(f"Closed {killed} process(es)." if killed else f"No processes found under '{install_path}'.")

# ── Shared ─────────────────────────────────────────────────────────────────────
def _block_parent(devname):
    """Given a partition device name like 'sdb1', 'nvme0n1p1' or 'mmcblk0p1',
    return its parent block device name (e.g. 'sdb'). If devname is already a
    top-level (non-partitioned) block device, returns devname unchanged."""
    try:
        real = os.path.realpath(f"/sys/class/block/{devname}")
        parent_dir = os.path.dirname(real)
        parent_name = os.path.basename(parent_dir)
        if parent_name == "block":
            # devname sits directly under .../block/ — it IS the top-level device.
            return devname
        return parent_name
    except Exception:
        return devname

def _is_removable(block, mountpoint=None):
    """True if the mountpoint follows the standard udisks2 auto-mount
    convention (/media/<user>/... or /run/media/<user>/... — used by GNOME,
    KDE, and SteamOS), OR the kernel marks the device removable, OR it's
    attached via USB. The kernel 'removable' flag is unreliable — e.g. the
    Steam Deck's built-in SD card reader reports removable=0 — so the
    mountpoint convention is checked first and is usually the most trustworthy
    signal on modern desktop Linux."""
    if mountpoint and (mountpoint.startswith("/media/") or mountpoint.startswith("/run/media/")):
        return True
    try:
        with open(f"/sys/block/{block}/removable") as rf:
            if rf.read().strip() == "1":
                return True
    except Exception:
        pass
    try:
        if "/usb" in os.path.realpath(f"/sys/block/{block}"):
            return True
    except Exception:
        pass
    return False

def get_removable_drives():
    """Return the set of mountpoints backed by removable media. Reads
    /proc/mounts and /sys/block directly — no extra packages needed."""
    drives = set()
    try:
        with open("/proc/mounts") as f:
            lines = f.readlines()
    except Exception as e:
        log(f"Could not read /proc/mounts: {e}")
        return drives
    for line in lines:
        parts = line.split()
        if len(parts) < 2: continue
        dev, mountpoint = parts[0], parts[1].replace("\\040", " ")
        if not dev.startswith("/dev/"): continue
        block = _block_parent(os.path.basename(dev))
        if _is_removable(block, mountpoint):
            drives.add(mountpoint)
    return drives

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

def find_library_root(drive):
    """Search for a Steam library on this drive. Checks the drive root itself
    (a bare 'steamapps' folder), and one level of subfolders (covers wrapper
    folders like 'SteamLibrary', or however else it was named). Returns the
    library root path if found, else None."""
    root = drive.rstrip("\\/")
    if os.path.isdir(os.path.join(root, "steamapps")):
        return root
    try:
        for name in sorted(os.listdir(root)):
            sub = os.path.join(root, name)
            if os.path.isdir(sub) and os.path.isdir(os.path.join(sub, "steamapps")):
                return sub
    except Exception as e:
        log(f"Could not scan {drive} for a Steam library: {e}")
    return None

def handle_insert(drive, require_card=False):
    # If the drive has a Steam library on it anywhere (a 'steamapps' folder at
    # the root, or one level down in a wrapper folder), it's always treated
    # as a cartridge — the size check below is only used to sniff out "thin"
    # cartridges that don't carry their own library.
    library_root = find_library_root(drive)
    has_library = library_root is not None
    if not has_library:
        # Only treat as a game cartridge if the drive has less than 8 MB used
        try:
            used = shutil.disk_usage(drive).used
            if used >= 8 * 1024 * 1024:
                log(f"Drive {drive} has {used} bytes used (>=8MB) — not a game cartridge, skipping.")
                return None
        except Exception as e:
            log(f"Could not read usage for {drive}: {e}")

    sp = find_game_script(drive)
    if not sp: log(f"No file starting with 'launch_game' on {drive}."); return None
    app_id = read_app_id(sp)

    if has_library:
        add_steam_library(library_root)
        log(f"Drive {drive} has a Steam library at {library_root} — treating as a cartridge.")
        if app_id:
            log(f"Waiting for Steam to recognize App ID {app_id} in {library_root} "
                f"(up to {LIBRARY_WAIT_TIMEOUT}s)...")
            if wait_for_library_registration(library_root, app_id=app_id):
                log("Steam has recognized the library — proceeding.")
            else:
                log("Timed out waiting for Steam to recognize the library — launching anyway.")

    ip = None
    if app_id:
        ip = find_install_path(app_id)
        if require_card and ip: register_game(app_id, ip)
    else:
        log("No STEAM_APP_ID — game won't close on removal.")
    log(f"Launching {sp} ...")
    try: subprocess.Popen([sys.executable, sp], cwd=drive); log("Launched.")
    except Exception as e: log(f"Launch error: {e}")

    if not app_id and not ip:
        return None
    return {"app_id": app_id, "install_path": ip}

def handle_remove(drive, info):
    log(f"Cartridge removed from {drive}.")
    if not info:
        log("Nothing tracked for this drive — nothing to close.")
        return
    app_id = info.get("app_id")
    ip = info.get("install_path")
    closed = kill_by_app_id(app_id) if app_id else False
    if not closed and ip:
        # Fallback for the rare case a native game doesn't show the AppId
        # marker (or no App ID was readable in the first place).
        kill_by_path(ip)

# ── Enforcer ───────────────────────────────────────────────────────────────────
cartridge_present = threading.Event()

def show_alert(message, title="PHYsteam"):
    """Console alert, plus a desktop notification if notify-send happens to be
    available (optional — never required)."""
    log(f"[ALERT] {title}: {message}")
    if shutil.which("notify-send"):
        try: subprocess.Popen(["notify-send", title, message])
        except Exception: pass

def enforcer_thread():
    log("PHYsteam enforcer active.")
    while True:
        time.sleep(POLL_INTERVAL)
        try:
            if cartridge_present.is_set(): continue
            known = load_known_games()
            if not known: continue
            for app_id in list(known.keys()):
                if kill_by_app_id(app_id):
                    log(f"[ENFORCER] App {app_id} launched without card — terminated.")
                    show_alert("Please insert this game's cartridge.")
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
                info = handle_insert(drive, require_card)
                if info is not None: tracked[drive] = info
            if new_drives: cartridge_present.set()
            for drive in known - cur:
                if drive in tracked: handle_remove(drive, tracked.pop(drive))
                else: log(f"Drive {drive} removed but not tracked.")
                if not tracked: cartridge_present.clear()
            known = cur
        except Exception as e: log(f"Auto mode error: {e}")

# ── Fixed mode ─────────────────────────────────────────────────────────────────
def get_free(drive):
    try: return shutil.disk_usage(drive).free
    except Exception: return None

def run_fixed(drive, require_card=False):
    log(f"PHYsteam FIXED mode ({drive}) | require_card={require_card}")
    last = get_free(drive); running = False; info = None; cartridge_present.clear()
    while True:
        time.sleep(POLL_INTERVAL)
        try:
            cur = get_free(drive)
            if cur is None:
                if running and info: handle_remove(drive, info); running = False; info = None; cartridge_present.clear()
                last = None; continue
            if last is None:
                last = cur; new_info = handle_insert(drive, require_card)
                if new_info: info = new_info; running = True; cartridge_present.set()
                continue
            if abs(cur - last) >= CAPACITY_CHANGE_THRESHOLD:
                if running and info: handle_remove(drive, info); running = False; info = None; cartridge_present.clear()
                time.sleep(1)
                new_info = handle_insert(drive, require_card)
                if new_info: info = new_info; running = True; cartridge_present.set()
                last = cur
        except Exception as e: log(f"Fixed mode error: {e}")

def debug_list_drives():
    """Diagnostic: show every /dev/-backed mount and why it is or isn't
    being treated as a removable cartridge drive."""
    print("== PHYsteam drive-detection diagnostic ==")
    try:
        with open("/proc/mounts") as f:
            lines = f.readlines()
    except Exception as e:
        print(f"Could not read /proc/mounts: {e}")
        return
    any_dev = False
    for line in lines:
        parts = line.split()
        if len(parts) < 2: continue
        dev, mountpoint = parts[0], parts[1].replace("\\040", " ")
        if not dev.startswith("/dev/"): continue
        any_dev = True
        base = os.path.basename(dev)
        block = _block_parent(base)
        try:
            with open(f"/sys/block/{block}/removable") as rf:
                removable_flag = rf.read().strip()
        except Exception as e:
            removable_flag = f"<unreadable: {e}>"
        try:
            real = os.path.realpath(f"/sys/block/{block}")
            is_usb = "/usb" in real
        except Exception:
            real = "<unresolved>"
            is_usb = False
        print(f"- {dev} -> mounted at {mountpoint}")
        print(f"    block device            : {block}")
        print(f"    /sys/block/{block}/removable : {removable_flag}")
        print(f"    resolved sysfs path     : {real}")
        print(f"    looks USB-attached      : {is_usb}")
        print(f"    under /media or /run/media : {mountpoint.startswith('/media/') or mountpoint.startswith('/run/media/')}")
        print(f"    treated as removable    : {_is_removable(block, mountpoint)}")
    if not any_dev:
        print("No /dev/-backed mounts found in /proc/mounts at all — check how your")
        print("distro is auto-mounting removable media (e.g. gvfs-fuse mounts won't show up here).")
    print()
    print("Drives PHYsteam would currently watch:", get_removable_drives())

# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    if "--list-drives" in sys.argv:
        debug_list_drives()
        sys.exit(0)

    configure_requested = "--configure" in sys.argv
    cfg = load_config()

    if configure_requested:
        log("Configure requested — running PHYsteam setup.")
        new_cfg = show_setup_console()
        if new_cfg is None:
            if cfg is None:
                log("Setup cancelled and no existing config. Exiting.")
                sys.exit(0)
            log("Setup cancelled — keeping existing config.")
        else:
            cfg = new_cfg
            save_config(cfg)
    elif cfg is None:
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
