#!/bin/bash
# install_physteam.sh — Sets up PHYsteam to run automatically on Linux login.
# Run this as your normal user — do NOT use sudo.

if [ "$EUID" -eq 0 ]; then
    echo "Please run this WITHOUT sudo — PHYsteam runs as your regular user, not root."
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PHYSTEAM="$SCRIPT_DIR/physteam.py"

echo
echo "  PHYsteam Installer"
echo "  -------------------"
echo

# ── Check python3 ────────────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 not found. Install it with your package manager, e.g.:"
    echo "  sudo apt install python3       (Debian/Ubuntu)"
    echo "  sudo dnf install python3       (Fedora)"
    echo "  sudo pacman -S python          (Arch)"
    exit 1
fi
PYTHON_BIN="$(command -v python3)"

# ── Check physteam.py exists ──────────────────────────────────────────────────
if [ ! -f "$PHYSTEAM" ]; then
    echo "ERROR: physteam.py not found in $SCRIPT_DIR"
    echo "Make sure install_physteam.sh and physteam.py are in the same folder."
    exit 1
fi

# ── Check / install psutil ────────────────────────────────────────────────────
if ! python3 -c "import psutil" &>/dev/null; then
    echo "psutil not found. Installing now..."
    pip3 install --user psutil 2>/dev/null || pip3 install --user --break-system-packages psutil
    if ! python3 -c "import psutil" &>/dev/null; then
        echo "ERROR: Failed to install psutil via pip."
        echo "Try installing it from your package manager instead:"
        echo "  sudo apt install python3-psutil"
        exit 1
    fi
fi

# ── Run interactive setup (this opens the picker window) ────────────────────
echo
echo "Opening PHYsteam setup window..."
"$PYTHON_BIN" "$PHYSTEAM" --configure

if [ ! -f "$SCRIPT_DIR/physteam_config.json" ]; then
    echo
    echo "Setup was cancelled — no config was saved. Installation stopped."
    exit 1
fi

# ── Create systemd user service ──────────────────────────────────────────────
SERVICE_DIR="$HOME/.config/systemd/user"
SERVICE_FILE="$SERVICE_DIR/physteam.service"
mkdir -p "$SERVICE_DIR"

# Get current D-Bus address so the service can talk to the desktop (needed for xdg-open)
DBUS_ADDR="${DBUS_SESSION_BUS_ADDRESS:-}"

cat > "$SERVICE_FILE" << SERVICEEOF
[Unit]
Description=PHYsteam Game Cartridge Watcher
After=graphical-session.target plasma-kwin_wayland.service
Wants=graphical-session.target

[Service]
Type=simple
ExecStart=$PYTHON_BIN $PHYSTEAM
Environment="DBUS_SESSION_BUS_ADDRESS=$DBUS_ADDR"
Environment="DISPLAY=:0"
Environment="XDG_RUNTIME_DIR=/run/user/%i"
Restart=on-failure
RestartSec=5

[Install]
WantedBy=graphical-session.target
SERVICEEOF

echo
echo "Registering PHYsteam to start at login..."
systemctl --user daemon-reload
systemctl --user enable physteam.service
systemctl --user restart physteam.service

echo
echo "  Success! PHYsteam is installed and running."
echo
echo "  Script  : $PHYSTEAM"
echo "  Log     : $SCRIPT_DIR/physteam.log"
echo "  Status  : systemctl --user status physteam.service"
echo
echo "  Insert your game cartridge to test it!"
