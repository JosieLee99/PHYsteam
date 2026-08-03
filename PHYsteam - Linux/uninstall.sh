#!/bin/bash
# uninstall.sh — Stops PHYsteam and removes it from systemd autostart.
# Run this as your normal user — do NOT use sudo.

if [ "$EUID" -eq 0 ]; then
    echo "Please run this WITHOUT sudo — PHYsteam runs as your regular user, not root."
    exit 1
fi

echo
echo "  PHYsteam Uninstaller"
echo "  ---------------------"
echo

read -p "This will stop PHYsteam and remove it from startup. Continue? (y/N): " CONFIRM
if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 0
fi

echo
echo "Stopping PHYsteam..."
systemctl --user stop physteam.service 2>/dev/null
systemctl --user disable physteam.service 2>/dev/null

# Kill any stray instance not managed by systemd
pkill -u "$USER" -f "physteam.py" 2>/dev/null
sleep 1

SERVICE_FILE="$HOME/.config/systemd/user/physteam.service"
if [ -f "$SERVICE_FILE" ]; then
    rm -f "$SERVICE_FILE"
    systemctl --user daemon-reload
    echo "Removed systemd service."
else
    echo "No systemd service found (already removed or never installed)."
fi

echo
echo "PHYsteam has been removed from your system."
