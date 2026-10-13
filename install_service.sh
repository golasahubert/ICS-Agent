#!/bin/bash
# Installs the ICS Agent as an hourly systemd timer.
# Usage: sudo bash install_service.sh
set -e

if [ "$EUID" -ne 0 ]; then
    echo "[!] Run as root: sudo bash install_service.sh"
    exit 1
fi

AGENT_DIR="$(cd "$(dirname "$0")" && pwd)"
RUN_USER="${SUDO_USER:-root}"

echo "[*] Agent dir: $AGENT_DIR, user: $RUN_USER"

if [ ! -f "$AGENT_DIR/agent.env" ]; then
    echo "[!] Missing agent.env - copy agent.env.example to agent.env and fill it in first."
    exit 1
fi
chmod 600 "$AGENT_DIR/agent.env"
chown "$RUN_USER" "$AGENT_DIR/agent.env"

make_venv() {
    rm -rf "$AGENT_DIR/venv"
    sudo -u "$RUN_USER" python3 -m venv "$AGENT_DIR/venv" >/dev/null 2>&1
}

echo "[*] Python: $(python3 --version)"
if [ ! -x "$AGENT_DIR/venv/bin/pip" ]; then
    echo "[*] Creating venv..."
    if ! make_venv; then
        echo "[*] Installing python3-venv..."
        apt-get update -q && apt-get install -y python3-venv
        make_venv || { echo "[!] Could not create venv"; exit 1; }
    fi
fi

echo "[*] Installing dependencies..."
sudo -u "$RUN_USER" bash -c "
    cd '$AGENT_DIR'
    venv/bin/pip install --upgrade pip
    venv/bin/pip install --upgrade -r requirements.txt
    venv/bin/playwright install chromium
"
bash "$AGENT_DIR/install_deps.sh" "$AGENT_DIR/venv"

echo "[*] Installing systemd units..."
for unit in ics-agent.service ics-agent.timer; do
    sed -e "s|@AGENT_DIR@|$AGENT_DIR|g" -e "s|@RUN_USER@|$RUN_USER|g" \
        "$AGENT_DIR/systemd/$unit" > "/etc/systemd/system/$unit"
done

systemctl daemon-reload
systemctl enable --now ics-agent.timer

echo "[+] Done. Next run:"
systemctl list-timers ics-agent.timer --no-pager
