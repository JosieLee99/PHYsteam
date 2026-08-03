#!/usr/bin/env bash
# install_physteam.sh
# Run this once to set up PHYsteam and register it to start at login.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WATCHER="$SCRIPT_DIR/physteam.py"

# ── Check python3 is installed ────────────────────────────────────────────────
if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: python3 not found. Install it with your distro's package manager"
    echo "(e.g. 'sudo apt install python3') and re-run this script."
    exit 1
fi
PYTHON_BIN="$(command -v python3)"

if [ ! -f "$WATCHER" ]; then
    echo "ERROR: physteam.py not found in $SCRIPT_DIR"
    echo "Make sure install_physteam.sh and physteam.py are in the same folder."
    exit 1
fi

chmod +x "$WATCHER" "$SCRIPT_DIR/launch_game_linux.py" 2>/dev/null || true

echo ""
echo " PHYsteam Setup"
echo " ----------------------------"
"$PYTHON_BIN" "$WATCHER" --configure
echo ""

# ── Register autostart ────────────────────────────────────────────────────────
if command -v systemctl >/dev/null 2>&1 && systemctl --user list-units >/dev/null 2>&1; then
    mkdir -p "$HOME/.config/systemd/user"
    UNIT_FILE="$HOME/.config/systemd/user/physteam.service"
    cat > "$UNIT_FILE" <<EOF
[Unit]
Description=PHYsteam cartridge watcher

[Service]
ExecStart=$PYTHON_BIN $WATCHER
Restart=on-failure
RestartSec=2

[Install]
WantedBy=default.target
EOF
    systemctl --user daemon-reload
    systemctl --user enable --now physteam.service

    # Let the service run even without an active graphical/login session, if supported.
    loginctl enable-linger "$USER" >/dev/null 2>&1 || true

    echo " Success! PHYsteam is installed as a systemd user service and running now."
    echo ""
    echo " Watcher script : $WATCHER"
    echo " Log file       : $SCRIPT_DIR/physteam.log"
    echo " Service status : systemctl --user status physteam.service"
    echo " Service logs   : journalctl --user -u physteam.service -f"
else
    echo " systemd (user services) not available on this system — using crontab @reboot instead."
    if ! command -v crontab >/dev/null 2>&1; then
        echo " ERROR: crontab not found either. Please start PHYsteam manually with:"
        echo "   $PYTHON_BIN $WATCHER"
        exit 1
    fi
    ( crontab -l 2>/dev/null | grep -v "physteam.py" ; echo "@reboot $PYTHON_BIN $WATCHER >> $SCRIPT_DIR/physteam.log 2>&1" ) | crontab -
    echo " Registered PHYsteam to start on next reboot via crontab."
    echo " Starting it now for this session..."
    nohup "$PYTHON_BIN" "$WATCHER" >> "$SCRIPT_DIR/physteam.log" 2>&1 &
    disown
    echo " Success! PHYsteam is running now (PID $!)."
    echo ""
    echo " Watcher script : $WATCHER"
    echo " Log file       : $SCRIPT_DIR/physteam.log"
fi

echo ""
echo " Done! Insert your game cartridge to test it."
echo ""
read -n 1 -s -r -p " Press any key to close..."
echo ""
