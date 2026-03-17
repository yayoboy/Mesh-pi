#!/usr/bin/env bash
# install.sh — Set up Meshtastic Terminal UI on Raspberry Pi OS Lite (Bookworm+)
#
# Usage:
#   cd /home/pi/Mesh-pi
#   bash install.sh
#
# What it does:
#   1. Checks Python >= 3.9
#   2. Installs system packages (tkinter, venv, BLE/serial support)
#   3. Creates a virtual environment at .venv/
#   4. Installs Python dependencies into the venv
#   5. Grants serial port access to the pi user
#   6. Installs and enables the systemd service

set -euo pipefail

INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$INSTALL_DIR/.venv"
SERVICE_SRC="$INSTALL_DIR/meshtastic-ui.service"
SERVICE_DST="/etc/systemd/system/meshtastic-ui.service"

# ── Colour output ──────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}==>${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }

# ── 1. Python version check ────────────────────────────────────────────────
info "Checking Python version…"
PYTHON=$(command -v python3 || error "python3 not found")
PY_VER=$("$PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
"$PYTHON" -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" \
    || error "Python >= 3.9 required (found $PY_VER)"
info "Python $PY_VER — OK"

# ── 2. System packages ─────────────────────────────────────────────────────
info "Installing system packages…"
sudo apt-get update -qq
sudo apt-get install -y \
    python3-venv \
    python3-tk \
    libglib2.0-dev \
    python3-dbus \
    dbus \
    libdbus-1-dev
# python3-tk   — Tkinter (must be system package, not pip)
# libglib2.0-dev / python3-dbus — needed by bleak (BLE, pulled in by meshtastic)
# dbus — D-Bus daemon required by bleak on Linux

# ── 3. Virtual environment ─────────────────────────────────────────────────
info "Creating virtual environment at $VENV_DIR …"
# --system-site-packages lets the venv see system-installed tkinter
"$PYTHON" -m venv --system-site-packages "$VENV_DIR"
VENV_PYTHON="$VENV_DIR/bin/python3"
VENV_PIP="$VENV_DIR/bin/pip"

info "Upgrading pip inside venv…"
"$VENV_PIP" install --quiet --upgrade pip

# ── 4. Python dependencies ─────────────────────────────────────────────────
info "Installing Python dependencies…"
"$VENV_PIP" install --quiet -r "$INSTALL_DIR/requirements.txt"

# Verify meshtastic is importable
"$VENV_PYTHON" -c "import meshtastic; print(f'  meshtastic {meshtastic.version.package_version}')" \
    || warn "meshtastic import check failed — check output above"

# ── 5. Serial port access ──────────────────────────────────────────────────
info "Granting serial port access (dialout group)…"
sudo usermod -aG dialout "${SUDO_USER:-pi}"
warn "Serial group change takes effect on next login / reboot"

# ── 6. Systemd service ─────────────────────────────────────────────────────
info "Installing systemd service…"

# Patch the service file with the actual venv Python path and install dir
SERVICE_TMP=$(mktemp)
sed \
    -e "s|/home/pi/Mesh-pi/.venv/bin/python3|$VENV_PYTHON|g" \
    -e "s|/home/pi/Mesh-pi|$INSTALL_DIR|g" \
    -e "s|User=pi|User=${SUDO_USER:-pi}|g" \
    "$SERVICE_SRC" > "$SERVICE_TMP"

sudo cp "$SERVICE_TMP" "$SERVICE_DST"
rm -f "$SERVICE_TMP"

sudo systemctl daemon-reload
sudo systemctl enable meshtastic-ui.service

echo ""
info "Installation complete!"
echo ""
echo "  To start now:   sudo systemctl start meshtastic-ui"
echo "  To view logs:   journalctl -u meshtastic-ui -f"
echo "  To test UI:     $VENV_PYTHON $INSTALL_DIR/main.py"
echo ""
warn "Reboot recommended for group membership (dialout) to take effect."
