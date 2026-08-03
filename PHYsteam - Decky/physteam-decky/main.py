"""main.py — PHYsteam as a Decky Loader plugin.

This is physteam.py's watcher logic, ported to run as an asyncio task inside
the Decky backend instead of as a standalone systemd/cron service. Decky
Loader itself starts at boot and keeps this process alive, so there is no
separate install/uninstall step for autostart anymore — that's what Decky
is for.

Config and "known games" (used for require_card enforcement) are stored via
Decky's SettingsManager instead of loose JSON files next to the script.
The interactive `--configure` console prompt is gone; the frontend panel
(src/index.tsx) calls the async methods below instead.
"""

import os, re, sys, time, shutil, signal, asyncio, subprocess, pwd

import decky_plugin
from settings import SettingsManager

LOG = decky_plugin.logger

POLL_INTERVAL = 0.5
CAPACITY_CHANGE_THRESHOLD = 10 * 1024 * 1024
LIBRARY_WAIT_TIMEOUT = 20
LIBRARY_WAIT_INTERVAL = 1

settings = SettingsManager(
    name="physteam",
    settings_directory=decky_plugin.DECKY_PLUGIN_SETTINGS_DIR,
)
settings.read()

DEFAULT_CONFIG = {"mode": "auto", "drive": None, "require_card": False, "register_library": False, "dry_run": False}


def get_config():
    return settings.getSetting("config", DEFAULT_CONFIG)


def save_config(cfg):
    settings.setSetting("config", cfg)
    LOG.info(f"Config saved: {cfg}")


def load_known_games():
    return settings.getSetting("known_games", {})


def save_known_games(d):
    settings.setSetting("known_games", d)


def register_game(app_id, path):
    k = load_known_games()
    if app_id not in k:
        k[app_id] = path
        save_known_games(k)
        LOG.info(f"Registered game App ID {app_id}: {path}")
    else:
        LOG.info(f"App ID {app_id} already registered.")


# ── Steam ────────────────────────────────────────────────────────────────────
def find_steam_root():
    home = os.path.expanduser("~")
    for p in [
        os.path.join(home, ".local", "share", "Steam"),
        os.path.join(home, ".steam", "steam"),
        os.path.join(home, ".steam", "root"),
        os.path.join(home, ".var", "app", "com.valvesoftware.Steam", "data", "Steam"),
        "/usr/share/steam",
    ]:
        if os.path.isdir(p):
            return p
    return None


def find_steam_libraries(steam_root):
    libs = []
    default = os.path.join(steam_root, "steamapps")
    if os.path.isdir(default):
        libs.append(default)
    vdf = os.path.join(default, "libraryfolders.vdf")
    if os.path.isfile(vdf):
        try:
            txt = open(vdf, encoding="utf-8").read()
            for m in re.finditer(r'"path"\s+"([^"]+)"', txt):
                sa = os.path.join(m.group(1).replace("\\\\", "\\"), "steamapps")
                if os.path.isdir(sa) and sa not in libs:
                    libs.append(sa)
        except Exception as e:
            LOG.info(f"VDF parse error: {e}")
    return libs


def find_install_path(app_id):
    # A non-numeric app_id is actually a game NAME — the launch script uses
    # this for games added to Steam as a "non-Steam game" shortcut, which
    # have no numeric App ID or appmanifest. Look it up in shortcuts.vdf
    # instead and use its target exe's folder as the "install path".
    if not app_id.strip().isdigit():
        shortcut = find_non_steam_shortcut(app_id)
        if not shortcut or not shortcut.get("exe"):
            LOG.info(f"No Steam library shortcut named '{app_id}'.")
            return None
        p = os.path.dirname(shortcut["exe"])
        LOG.info(f"Install path for '{app_id}' (non-Steam shortcut): {p}")
        return p

    root = find_steam_root()
    if not root:
        LOG.info("Steam not found.")
        return None
    for lib in find_steam_libraries(root):
        mf = os.path.join(lib, f"appmanifest_{app_id}.acf")
        if os.path.isfile(mf):
            try:
                txt = open(mf, encoding="utf-8").read()
                m = re.search(r'"installdir"\s+"([^"]+)"', txt)
                if m:
                    p = os.path.join(lib, "common", m.group(1))
                    LOG.info(f"Install path for {app_id}: {p}")
                    return p
            except Exception as e:
                LOG.info(f"Manifest error: {e}")
    LOG.info(f"No manifest for App ID {app_id}.")
    return None


def add_steam_library(library_path):
    steamapps_dir = os.path.join(library_path, "steamapps")
    if not os.path.isdir(steamapps_dir):
        return False

    steam_root = find_steam_root()
    if not steam_root:
        LOG.info("Steam not found — can't register library.")
        return False

    vdf_path = os.path.join(steam_root, "steamapps", "libraryfolders.vdf")
    if not os.path.isfile(vdf_path):
        LOG.info("libraryfolders.vdf not found — can't register library.")
        return False

    try:
        with open(vdf_path, encoding="utf-8") as f:
            text = f.read()
    except Exception as e:
        LOG.info(f"Could not read libraryfolders.vdf: {e}")
        return False

    drive_path = library_path.rstrip("/")
    escaped_path = drive_path.replace("\\", "\\\\")

    registered = set(re.findall(r'"path"\s+"([^"]+)"', text))
    if escaped_path in registered or drive_path in registered:
        LOG.info(f"{drive_path} is already registered as a Steam library.")
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
        LOG.info("Could not parse libraryfolders.vdf structure — skipping registration.")
        return False
    new_text = text[:close_idx] + entry + text[close_idx:]

    # Safety check: never write a result whose braces don't balance, and
    # never write a result that's shorter than what we started with. This
    # file is read live by the Steam client, so a bad write here can take
    # down Steam itself, not just this plugin.
    if new_text.count("{") != new_text.count("}") or len(new_text) < len(text):
        LOG.info("Refusing to write libraryfolders.vdf — the spliced result "
                  "failed a sanity check. Steam library was left untouched.")
        return False

    backup_path = vdf_path + ".physteam.bak"
    try:
        if not os.path.exists(backup_path):
            shutil.copy2(vdf_path, backup_path)
            LOG.info(f"Backed up libraryfolders.vdf to {backup_path} before editing.")
    except Exception as e:
        LOG.info(f"Could not create backup, refusing to edit libraryfolders.vdf: {e}")
        return False

    try:
        with open(vdf_path, "w", encoding="utf-8") as f:
            f.write(new_text)
        LOG.info(f"Registered {drive_path} as Steam library #{next_index}.")
        return True
    except Exception as e:
        LOG.info(f"Could not write libraryfolders.vdf: {e}")
        return False


async def wait_for_library_registration(library_path, app_id=None,
                                         timeout=LIBRARY_WAIT_TIMEOUT,
                                         poll_interval=LIBRARY_WAIT_INTERVAL):
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
        await asyncio.sleep(poll_interval)


def read_app_id(script_path):
    """Returns the raw contents of STEAM_APP_ID from the launch script: either
    a numeric Steam App ID (e.g. "105600") or a game name (e.g. "My Cool
    Game") for games added to Steam as a non-Steam shortcut."""
    try:
        txt = open(script_path).read()
        m = re.search(r'STEAM_APP_ID\s*=\s*"([^"]+)"', txt)
        if m:
            return m.group(1)
        m = re.search(r"STEAM_APP_ID\s*=\s*'([^']+)'", txt)
        if m:
            return m.group(1)
    except Exception as e:
        LOG.info(f"Could not read STEAM_APP_ID: {e}")
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
        LOG.info("Steam not found — can't search for non-Steam shortcuts.")
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
            LOG.info(f"Could not parse {vdf_path}: {e}")
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

    # Prefer an exact (case-insensitive) name match; fall back to substring.
    for m in matches:
        if m["name"].strip().lower() == target:
            return m
    for m in matches:
        if target in m["name"].strip().lower():
            return m
    return None


def kill_by_app_id(app_id):
    marker = f"AppId={app_id}"
    killed = 0
    try:
        pids = [p for p in os.listdir("/proc") if p.isdigit()]
    except Exception as e:
        LOG.info(f"Could not list /proc: {e}")
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
                LOG.info(f"Closing PID {pid} (Steam launcher for App ID {app_id})")
                killed += 1
            except Exception as e:
                LOG.info(f"Could not kill PID {pid}: {e}")
    if killed:
        LOG.info(f"Closed {killed} launcher process(es) for App ID {app_id}.")
    else:
        LOG.info(f"No running Steam launcher process found for App ID {app_id}.")
    return killed > 0


def kill_by_path(install_path):
    low = install_path.rstrip("/")
    killed = 0
    try:
        pids = [p for p in os.listdir("/proc") if p.isdigit()]
    except Exception as e:
        LOG.info(f"Could not list /proc: {e}")
        return
    for pid in pids:
        try:
            exe = os.readlink(f"/proc/{pid}/exe")
        except Exception:
            continue
        if exe.startswith(low):
            try:
                os.kill(int(pid), signal.SIGTERM)
                LOG.info(f"Closing PID {pid} ({exe})")
                killed += 1
            except Exception as e:
                LOG.info(f"Could not kill PID {pid}: {e}")
    LOG.info(f"Closed {killed} process(es)." if killed else f"No processes found under '{install_path}'.")


# ── Drive detection ──────────────────────────────────────────────────────────
def _block_parent(devname):
    try:
        real = os.path.realpath(f"/sys/class/block/{devname}")
        parent_dir = os.path.dirname(real)
        parent_name = os.path.basename(parent_dir)
        if parent_name == "block":
            return devname
        return parent_name
    except Exception:
        return devname


def _is_removable(block, mountpoint=None):
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
    drives = set()
    try:
        with open("/proc/mounts") as f:
            lines = f.readlines()
    except Exception as e:
        LOG.info(f"Could not read /proc/mounts: {e}")
        return drives
    for line in lines:
        parts = line.split()
        if len(parts) < 2:
            continue
        dev, mountpoint = parts[0], parts[1].replace("\\040", " ")
        if not dev.startswith("/dev/"):
            continue
        block = _block_parent(os.path.basename(dev))
        if _is_removable(block, mountpoint):
            drives.add(mountpoint)
    return drives


def find_game_script(drive):
    try:
        entries = sorted(os.listdir(drive))
    except Exception as e:
        LOG.info(f"Could not list files on {drive}: {e}")
        return None
    candidates = [n for n in entries
                  if os.path.isfile(os.path.join(drive, n)) and n.lower().startswith("launch_game")]
    if not candidates:
        return None
    preferred = "launch_game_windows" if sys.platform.startswith("win") else "launch_game_linux"
    for name in candidates:
        if os.path.splitext(name)[0].lower() == preferred:
            return os.path.join(drive, name)
    LOG.info(f"No launcher matching this platform ({preferred}) found on {drive} — "
             f"falling back to {candidates[0]}.")
    return os.path.join(drive, candidates[0])


def find_library_root(drive):
    root = drive.rstrip("\\/")
    if os.path.isdir(os.path.join(root, "steamapps")):
        return root
    try:
        for name in sorted(os.listdir(root)):
            sub = os.path.join(root, name)
            if os.path.isdir(sub) and os.path.isdir(os.path.join(sub, "steamapps")):
                return sub
    except Exception as e:
        LOG.info(f"Could not scan {drive} for a Steam library: {e}")
    return None


def _mount_options(mountpoint):
    """Return the mount option set (e.g. {'rw','nosuid','nodev','noexec',...})
    for the filesystem mounted at mountpoint, by reading /proc/mounts."""
    try:
        with open("/proc/mounts") as f:
            lines = f.readlines()
    except Exception:
        return set()
    best = None
    for line in lines:
        parts = line.split()
        if len(parts) < 4:
            continue
        mp = parts[1].replace("\\040", " ")
        if mountpoint == mp or mountpoint.rstrip("/").startswith(mp.rstrip("/") + "/") or mp == mountpoint.rstrip("/"):
            if best is None or len(mp) > len(best[0]):
                best = (mp, parts[3])
    return set(best[1].split(",")) if best else set()


def _resolve_launcher_command(sp, drive):
    """Decky's sys.executable points at the loader's own bundled binary
    (e.g. .../homebrew/services/PluginLoader), NOT a general-purpose Python
    interpreter — using it to run someone else's script spawns a second,
    unintended instance of the loader itself. Run the script via its own
    shebang instead; only fall back to a real interpreter if it can't be
    made executable, OR if the cartridge's filesystem is mounted noexec.

    That second case matters a lot here: udisks2 (the automounter behind
    both Desktop Mode and Game Mode's "insert a drive" handling) mounts
    most removable media with noexec by default. chmod +x against a
    FAT/exFAT drive under that mount usually reports success — the
    filesystem driver just doesn't error on it — but the kernel still
    refuses to exec() anything from that mountpoint, so a direct-exec
    attempt fails at Popen() time with a Permission-denied/Exec-format
    error that only shows up in the log, not on screen. Running the
    *interpreter* (which lives on the root filesystem) instead sidesteps
    that restriction, since only the script's bytes are read off the
    noexec-mounted drive, not executed as a binary."""
    noexec = "noexec" in _mount_options(drive)
    if noexec:
        LOG.info(f"{drive} is mounted noexec — can't exec {sp} directly off it; "
                 f"running it through an interpreter instead.")
    else:
        try:
            st = os.stat(sp)
            if not (st.st_mode & 0o111):
                os.chmod(sp, st.st_mode | 0o111)
            return [sp]
        except Exception as e:
            LOG.info(f"Could not make {sp} executable ({e}) — falling back to an interpreter.")

    ext = os.path.splitext(sp)[1].lower()
    if ext in (".sh", ".bash"):
        interp = shutil.which("bash") or shutil.which("sh")
    else:
        # Covers .py and any extensionless/unrecognized launcher — physteam's
        # own launch_game_* scripts are Python, so that's the sane default.
        interp = shutil.which("python3") or shutil.which("python")
    if interp:
        return [interp, sp]
    return None


async def _log_launch_result(proc, out_path, out_file):
    # The steam:// URI handoff should return almost instantly if it's
    # working — give it up to 10s, then report whatever happened.
    rc = None
    for _ in range(10):
        await asyncio.sleep(1)
        rc = proc.poll()
        if rc is not None:
            break
    try:
        out_file.flush()
        out_file.close()
    except Exception:
        pass
    try:
        with open(out_path) as f:
            output = f.read().strip()
    except Exception:
        output = "<could not read captured output>"
    status = "still running after 10s" if rc is None else f"exited with code {rc}"
    LOG.info(f"Cartridge launcher {status}. Output: {output or '<empty>'}")


def _find_session_env():
    """Decky's backend runs as root via a systemd service — it was never
    part of the actual graphical session (gamescope/Steam/Plasma, all
    running as the 'deck' user), so root's own os.environ has no
    DISPLAY/WAYLAND_DISPLAY/XDG_RUNTIME_DIR/DBUS_SESSION_BUS_ADDRESS in it
    at all. A GUI command (steam, xdg-open, konsole, ...) launched with
    root's environment doesn't error — it just has nothing to connect to,
    so it does nothing visible. Worse, steam://rungameid/... specifically
    needs to reach the *already-running* Steam client over its session-
    bound IPC pipe; launched detached from that session, it can't.

    Find a process that's actually part of that session and borrow both
    its environment and its UID, so we can launch as that user instead."""
    candidates = ("gamescope", "gamescope-session", "steam", "steamwebhelper", "plasmashell")
    found = None
    try:
        pids = [p for p in os.listdir("/proc") if p.isdigit()]
    except Exception as e:
        LOG.info(f"Could not list /proc while looking for the desktop session: {e}")
        return None
    for pid in pids:
        try:
            with open(f"/proc/{pid}/comm") as f:
                comm = f.read().strip()
        except Exception:
            continue
        if comm not in candidates:
            continue
        try:
            with open(f"/proc/{pid}/environ", "rb") as f:
                raw = f.read()
        except Exception:
            continue
        env = {}
        for item in raw.split(b"\x00"):
            if b"=" not in item:
                continue
            k, _, v = item.partition(b"=")
            env[k.decode(errors="replace")] = v.decode(errors="replace")
        if "WAYLAND_DISPLAY" not in env and "DISPLAY" not in env:
            continue
        try:
            uid = os.stat(f"/proc/{pid}").st_uid
        except Exception:
            continue
        found = (uid, env)
        if comm.startswith("gamescope"):
            break  # the compositor itself — best source, stop looking
    return found


async def handle_insert(drive, require_card=False, register_library=False, dry_run=False):
    library_root = find_library_root(drive)
    has_library = library_root is not None

    sp = find_game_script(drive)
    if not sp:
        # No launch script found — only now fall back to the disk-usage
        # heuristic, purely to explain in the log why we're skipping.
        if not has_library:
            try:
                used = shutil.disk_usage(drive).used
                if used >= 8 * 1024 * 1024:
                    LOG.info(f"Drive {drive} has {used} bytes used (>=8MB) and no "
                             f"launch_game script or Steam library — not a cartridge, skipping.")
                else:
                    LOG.info(f"No file starting with 'launch_game' on {drive}.")
            except Exception as e:
                LOG.info(f"Could not read usage for {drive}: {e}")
        else:
            LOG.info(f"Drive {drive} has a Steam library at {library_root} but no "
                     f"launch_game script — nothing to launch.")
        return None
    app_id = read_app_id(sp)

    if has_library:
        if register_library:
            add_steam_library(library_root)
        else:
            LOG.info(f"Drive {drive} has a Steam library at {library_root}, but "
                      f"'register_library' is off — not touching libraryfolders.vdf.")
        LOG.info(f"Drive {drive} has a Steam library at {library_root} — treating as a cartridge.")
        if app_id and register_library:
            LOG.info(f"Waiting for Steam to recognize App ID {app_id} in {library_root} "
                     f"(up to {LIBRARY_WAIT_TIMEOUT}s)...")
            if await wait_for_library_registration(library_root, app_id=app_id):
                LOG.info("Steam has recognized the library — proceeding.")
            else:
                LOG.info("Timed out waiting for Steam to recognize the library — launching anyway.")

    ip = None
    if app_id:
        ip = find_install_path(app_id)
        if require_card and ip:
            register_game(app_id, ip)
    else:
        LOG.info("No STEAM_APP_ID — game won't close on removal.")

    cmd = _resolve_launcher_command(sp, drive)
    if not cmd:
        LOG.info(f"Could not find a way to execute {sp} — no system python3 on "
                 f"PATH and could not make it executable.")
        return {"app_id": app_id, "install_path": ip} if (app_id or ip) else None

    LOG.info(f"Would launch: {' '.join(cmd)}  (cwd={drive}, app_id={app_id}, install_path={ip})")
    if dry_run:
        LOG.info("dry_run is on — not actually launching.")
        return None
    LOG.info(f"Launching {sp} ...")
    try:
        out_path = f"/tmp/physteam_launch_{os.path.basename(drive.rstrip('/'))}.log"
        out_file = open(out_path, "w")
        # Hand the launched script the environment of the actual desktop
        # session it needs to talk to (DISPLAY, WAYLAND_DISPLAY,
        # XDG_RUNTIME_DIR, DBUS_SESSION_BUS_ADDRESS) — and run it as that
        # session's user, not root, since Wayland/Steam's IPC both
        # generally require the connecting process to actually be that
        # user, not just have the right env vars set.
        session = _find_session_env()
        run_as_uid = run_as_gid = None
        if session:
            run_as_uid, launch_env = session
            try:
                run_as_gid = pwd.getpwuid(run_as_uid).pw_gid
            except Exception as e:
                LOG.info(f"Found session uid={run_as_uid} but couldn't resolve its "
                         f"primary group ({e}) — launching with uid only.")
            LOG.info(f"Found desktop session (uid={run_as_uid}) — launching as that "
                     f"user instead of root.")
        else:
            LOG.info("Could not find the desktop session's environment — launching "
                     "as root with a best-effort environment; GUI programs may fail "
                     "to display or reach the running Steam client.")
            launch_env = dict(os.environ)
            # PluginLoader is a PyInstaller-frozen binary: to run itself it
            # points LD_LIBRARY_PATH at its own bundled shared libraries. That
            # poisons any subprocess that also loads shared libs — e.g. bash,
            # which the "steam" launcher script runs under — with mismatched
            # library versions (symptom: "undefined symbol" errors from bash).
            # PyInstaller saves the pre-override value in LD_LIBRARY_PATH_ORIG
            # specifically so children can restore it; fall back to unsetting
            # it entirely if there was no original value.
            if "LD_LIBRARY_PATH_ORIG" in launch_env:
                launch_env["LD_LIBRARY_PATH"] = launch_env["LD_LIBRARY_PATH_ORIG"]
            else:
                launch_env.pop("LD_LIBRARY_PATH", None)
            launch_env.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")

        popen_kwargs = dict(cwd=drive, stdout=out_file, stderr=subprocess.STDOUT, env=launch_env)
        if run_as_uid is not None:
            popen_kwargs["user"] = run_as_uid
            if run_as_gid is not None:
                popen_kwargs["group"] = run_as_gid
        proc = subprocess.Popen(cmd, **popen_kwargs)
        LOG.info(f"Launched (pid={proc.pid}). Capturing its output to {out_path}.")
        asyncio.create_task(_log_launch_result(proc, out_path, out_file))
    except Exception as e:
        LOG.info(f"Launch error: {e}")

    if not app_id and not ip:
        return None
    return {"app_id": app_id, "install_path": ip}


def handle_remove(drive, info):
    LOG.info(f"Cartridge removed from {drive}.")
    if not info:
        LOG.info("Nothing tracked for this drive — nothing to close.")
        return
    app_id = info.get("app_id")
    ip = info.get("install_path")
    closed = kill_by_app_id(app_id) if app_id else False
    if not closed and ip:
        kill_by_path(ip)


def get_free(drive):
    try:
        return shutil.disk_usage(drive).free
    except Exception:
        return None


def debug_list_drives():
    """Diagnostic: for every /dev/-backed mount, report why it is or isn't
    being treated as a removable cartridge drive. Returns a list of dicts
    instead of printing, so the frontend panel can display it."""
    results = []
    try:
        with open("/proc/mounts") as f:
            lines = f.readlines()
    except Exception as e:
        return [{"error": f"Could not read /proc/mounts: {e}"}]
    for line in lines:
        parts = line.split()
        if len(parts) < 2:
            continue
        dev, mountpoint = parts[0], parts[1].replace("\\040", " ")
        if not dev.startswith("/dev/"):
            continue
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
        results.append({
            "device": dev,
            "mountpoint": mountpoint,
            "block": block,
            "removable_flag": removable_flag,
            "is_usb": is_usb,
            "media_convention": mountpoint.startswith("/media/") or mountpoint.startswith("/run/media/"),
            "treated_as_removable": _is_removable(block, mountpoint),
        })
    return results


class Plugin:
    # ── frontend-callable methods ────────────────────────────────────────────
    async def get_config(self):
        return get_config()

    async def save_config(self, cfg):
        save_config(cfg)
        # Apply immediately rather than requiring a plugin reload.
        old_task = getattr(self, "_watch_task", None)
        if old_task:
            old_task.cancel()
        self._watch_task = asyncio.create_task(self._watch_loop())
        return True

    async def list_removable_drives(self):
        return sorted(get_removable_drives())

    async def debug_list_drives(self):
        return debug_list_drives()

    async def get_known_games(self):
        return load_known_games()

    async def clear_known_games(self):
        save_known_games({})
        return True

    # ── lifecycle ─────────────────────────────────────────────────────────────
    async def _main(self):
        LOG.info("PHYsteam plugin starting.")
        self._running = True
        self._cartridge_present = False
        self._enforcer_task = asyncio.create_task(self._enforcer_loop())
        self._watch_task = asyncio.create_task(self._watch_loop())

    async def _unload(self):
        LOG.info("PHYsteam plugin unloading.")
        self._running = False
        for t in (getattr(self, "_enforcer_task", None), getattr(self, "_watch_task", None)):
            if t:
                t.cancel()

    async def _uninstall(self):
        # Nothing extra to clean up — Decky already removes the plugin
        # folder and its SettingsManager-managed settings directory.
        LOG.info("PHYsteam uninstalled.")

    # ── background loops (replace physteam.py's run_auto / run_fixed / enforcer_thread) ─
    async def _enforcer_loop(self):
        LOG.info("PHYsteam enforcer active.")
        while self._running:
            await asyncio.sleep(POLL_INTERVAL)
            try:
                if self._cartridge_present:
                    continue
                known = load_known_games()
                if not known:
                    continue
                for app_id in list(known.keys()):
                    if kill_by_app_id(app_id):
                        LOG.info(f"[ENFORCER] App {app_id} launched without card — terminated.")
                        if shutil.which("notify-send"):
                            try:
                                subprocess.Popen(["notify-send", "PHYsteam", "Please insert this game's cartridge."])
                            except Exception:
                                pass
            except Exception as e:
                LOG.info(f"Enforcer error: {e}")

    async def _watch_loop(self):
        cfg = get_config()
        LOG.info(f"PHYsteam watcher starting | {cfg}")
        mode = cfg.get("mode", "auto")
        require_card = cfg.get("require_card", False)
        register_library = cfg.get("register_library", False)
        dry_run = cfg.get("dry_run", False)

        if mode == "fixed":
            await self._run_fixed(cfg.get("drive"), require_card, register_library, dry_run)
        else:
            await self._run_auto(require_card, register_library, dry_run)

    async def _run_auto(self, require_card, register_library=False, dry_run=False):
        known = get_removable_drives()
        tracked = {}
        self._cartridge_present = False
        while self._running:
            await asyncio.sleep(POLL_INTERVAL)
            try:
                cur = get_removable_drives()
                new_drives = sorted(cur - known)
                for drive in new_drives:
                    info = await handle_insert(drive, require_card, register_library, dry_run)
                    if info is not None:
                        tracked[drive] = info
                if new_drives:
                    self._cartridge_present = True
                for drive in known - cur:
                    if drive in tracked:
                        handle_remove(drive, tracked.pop(drive))
                    else:
                        LOG.info(f"Drive {drive} removed but not tracked.")
                    if not tracked:
                        self._cartridge_present = False
                known = cur
            except Exception as e:
                LOG.info(f"Auto mode error: {e}")

    async def _run_fixed(self, drive, require_card, register_library=False, dry_run=False):
        if not drive:
            LOG.info("Fixed mode selected but no drive configured — falling back to auto.")
            await self._run_auto(require_card, register_library, dry_run)
            return
        last = get_free(drive)
        running = False
        info = None
        self._cartridge_present = False
        while self._running:
            await asyncio.sleep(POLL_INTERVAL)
            try:
                cur = get_free(drive)
                if cur is None:
                    if running and info:
                        handle_remove(drive, info)
                        running = False
                        info = None
                        self._cartridge_present = False
                    last = None
                    continue
                if last is None:
                    last = cur
                    new_info = await handle_insert(drive, require_card, register_library, dry_run)
                    if new_info:
                        info = new_info
                        running = True
                        self._cartridge_present = True
                    continue
                if abs(cur - last) >= CAPACITY_CHANGE_THRESHOLD:
                    if running and info:
                        handle_remove(drive, info)
                        running = False
                        info = None
                        self._cartridge_present = False
                    await asyncio.sleep(1)
                    new_info = await handle_insert(drive, require_card, register_library, dry_run)
                    if new_info:
                        info = new_info
                        running = True
                        self._cartridge_present = True
                    last = cur
            except Exception as e:
                LOG.info(f"Fixed mode error: {e}")
