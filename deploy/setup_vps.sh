#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Funding Rate Bot — VPS Setup Script
# Tested on Ubuntu 22.04 / Debian 12 (works on any $4/month VPS)
#
# Usage:
#   1. SSH into your VPS
#   2. Upload this repo (or git clone it)
#   3. cd GET-IT-DONE && bash deploy/setup_vps.sh
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

BOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/funding_rate_bot"
SERVICE_NAME="funding-bot"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
PYTHON_BIN="python3"
VENV_DIR="${BOT_DIR}/venv"

echo "──────────────────────────────────────────"
echo "  Funding Rate Bot — VPS Setup"
echo "  Bot directory: ${BOT_DIR}"
echo "──────────────────────────────────────────"

# ── 1. System packages ────────────────────────────────────────────────────────
echo "[1/5] Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq python3 python3-pip python3-venv curl git

# ── 2. Python venv ────────────────────────────────────────────────────────────
echo "[2/5] Creating Python virtual environment..."
${PYTHON_BIN} -m venv "${VENV_DIR}"
source "${VENV_DIR}/bin/activate"
pip install --quiet --upgrade pip
pip install --quiet -r "${BOT_DIR}/requirements.txt"
echo "  Dependencies installed."

# ── 3. .env file check ────────────────────────────────────────────────────────
echo "[3/5] Checking .env configuration..."
if [[ ! -f "${BOT_DIR}/.env" ]]; then
    cp "${BOT_DIR}/.env.example" "${BOT_DIR}/.env"
    echo ""
    echo "  ⚠️  No .env file found — created from .env.example"
    echo "  ⚠️  Edit ${BOT_DIR}/.env before starting the bot!"
    echo "      At minimum, leave PAPER_MODE=true for now."
    echo ""
else
    echo "  .env found at ${BOT_DIR}/.env"
fi

# ── 4. systemd service ────────────────────────────────────────────────────────
echo "[4/5] Installing systemd service..."

sudo tee "${SERVICE_FILE}" > /dev/null <<EOF
[Unit]
Description=Funding Rate Arbitrage Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${USER}
WorkingDirectory=${BOT_DIR}
ExecStart=${VENV_DIR}/bin/python bot.py --no-dashboard
Restart=always
RestartSec=30
StandardOutput=append:${BOT_DIR}/funding_bot.log
StandardError=append:${BOT_DIR}/funding_bot.log
Environment=PYTHONUNBUFFERED=1

# Safety: kill cleanly on SIGTERM
KillSignal=SIGTERM
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable "${SERVICE_NAME}"
echo "  systemd service installed and enabled."

# ── 5. Instructions ───────────────────────────────────────────────────────────
echo ""
echo "[5/5] Setup complete!"
echo ""
echo "──────────────────────────────────────────"
echo "  NEXT STEPS"
echo "──────────────────────────────────────────"
echo ""
echo "  1. Edit your config (if you haven't):"
echo "     nano ${BOT_DIR}/.env"
echo ""
echo "  2. Start the bot:"
echo "     sudo systemctl start ${SERVICE_NAME}"
echo ""
echo "  3. Check it's running:"
echo "     sudo systemctl status ${SERVICE_NAME}"
echo ""
echo "  4. Watch live logs:"
echo "     tail -f ${BOT_DIR}/funding_bot.log"
echo ""
echo "  5. Check performance any time:"
echo "     cd ${BOT_DIR} && ${VENV_DIR}/bin/python report.py"
echo ""
echo "  6. Stop the bot:"
echo "     sudo systemctl stop ${SERVICE_NAME}"
echo ""
echo "  The bot will auto-restart if it crashes, and"
echo "  start automatically on VPS reboot."
echo "──────────────────────────────────────────"
