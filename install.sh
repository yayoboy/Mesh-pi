#!/usr/bin/env bash
# install.sh — set up Meshtastic Terminal UI on Raspberry Pi OS Lite
set -e

INSTALL_DIR="/home/pi/Mesh-pi"
SERVICE_FILE="meshtastic-ui.service"

echo "==> Installing Python dependencies..."
pip3 install --break-system-packages -r requirements.txt

echo "==> Installing tkinter (system package)..."
sudo apt-get install -y python3-tk

echo "==> Enabling serial port..."
# Ensure the pi user can access serial without sudo
sudo usermod -aG dialout pi

echo "==> Installing systemd service..."
sudo cp "$SERVICE_FILE" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable meshtastic-ui.service

echo ""
echo "Done. Reboot or run:"
echo "  sudo systemctl start meshtastic-ui"
