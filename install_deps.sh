#!/bin/bash
# Installs the system libraries Chromium (Playwright) needs.
# Works on Ubuntu 20.04 / 22.04 / 24.04 (and Debian-based distros like Kali).
# Usage: sudo bash install_deps.sh [path/to/venv]
set -e

if [ "$EUID" -ne 0 ]; then
    echo "[!] Run as root: sudo bash install_deps.sh"
    exit 1
fi

AGENT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="${1:-$AGENT_DIR/venv}"

# Chromium runtime libraries. On Ubuntu 24.04 some were renamed with a
# "t64" suffix (e.g. libasound2 -> libasound2t64), handled below.
PACKAGES=(
    libasound2 libatk1.0-0 libatk-bridge2.0-0 libatspi2.0-0 libcups2
    libglib2.0-0 libgtk-3-0 libnss3 libnspr4 libdbus-1-3 libdrm2 libgbm1
    libpango-1.0-0 libcairo2 libx11-6 libxcb1 libxcomposite1 libxdamage1
    libxext6 libxfixes3 libxkbcommon0 libxrandr2 fonts-liberation
)

has_candidate() {
    apt-cache policy "$1" 2>/dev/null | grep -q "Candidate: [^(]"
}

apt_fallback() {
    echo "[*] Installing Chromium libraries via apt..."
    apt-get update -q
    local resolved=()
    for pkg in "${PACKAGES[@]}"; do
        if has_candidate "${pkg}t64"; then
            resolved+=("${pkg}t64")
        elif has_candidate "$pkg"; then
            resolved+=("$pkg")
        else
            echo "[!] Package not found, skipping: $pkg"
        fi
    done
    DEBIAN_FRONTEND=noninteractive apt-get install -y "${resolved[@]}"
}

# Playwright knows the exact package list for officially supported distros;
# on anything else (older Ubuntu, Kali, WSL) fall back to our own list.
if [ -x "$VENV/bin/playwright" ] && "$VENV/bin/playwright" install-deps chromium; then
    echo "[+] Dependencies installed by Playwright"
else
    echo "[*] 'playwright install-deps' unavailable or failed, using apt fallback"
    apt_fallback
    echo "[+] Dependencies installed via apt"
fi
