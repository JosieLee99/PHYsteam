#!/usr/bin/env bash
# uninstall_physteam.sh
# Closes PHYsteam and removes it from startup.
set -e

echo ""
echo " PHYsteam Uninstaller"
echo " ----------------------------"
echo ""

read -r -p "This will stop PHYsteam and remove it from startup. Continue? (y/N): " CONFIRM
if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 0
fi

# ── Kill any running physteam.py processes ─────────────────────────────
echo ""
echo " Stopping PHYsteam..."
if command -v pkill >/dev/null 2>&1; then
    pkill -f "physteam.py" 2>/dev/null && echo " Stopped." || echo " No running PHYsteam process found."
else
    for pid in $(ps -eo pid,args | grep "[p]hysteam_linux.py" | awk '{print $1}'); do
        kill "$pid" 2>/dev/null || true
    done
    echo " Stopped (if it was running)."
fi

# ── Remove systemd user service, if present ───────────────────────────────────
if command -v systemctl >/dev/null 2>&1 && systemctl --user list-unit-files 2>/dev/null | grep -q "^physteam.service"; then
    echo ""
    echo " Removing systemd user service..."
    systemctl --user disable --now physteam.service >/dev/null 2>&1 || true
    rm -f "$HOME/.config/systemd/user/physteam.service"
    systemctl --user daemon-reload
    echo " Removed."
fi

# ── Remove crontab entry, if present ──────────────────────────────────────────
if command -v crontab >/dev/null 2>&1 && crontab -l 2>/dev/null | grep -q "physteam.py"; then
    echo ""
    echo " Removing crontab entry..."
    ( crontab -l 2>/dev/null | grep -v "physteam.py" ) | crontab -
    echo " Removed."
fi

echo ""
echo " Uninstall complete! PHYsteam has been removed from your system."
echo ""
read -n 1 -s -r -p " Press any key to close..."
echo ""
