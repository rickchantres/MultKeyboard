#!/usr/bin/env bash
# ==============================================================================
# MultKeyboard v1.0 - Desinstalador Limpo
# ==============================================================================
set -e

if [ "$EUID" -ne 0 ]; then
    SUDO="sudo"
else
    SUDO=""
fi

echo "🗑️ Desinstalando MultKeyboard..."

$SUDO systemctl stop scrolllock.service 2>/dev/null || true
$SUDO systemctl disable scrolllock.service 2>/dev/null || true
$SUDO rm -f /etc/systemd/system/scrolllock.service
$SUDO systemctl daemon-reload 2>/dev/null || true

$SUDO rm -f /usr/local/bin/painel_led_desktop.py
$SUDO rm -f /usr/local/bin/scrolllock-daemon.py
$SUDO rm -f /usr/share/pixmaps/scrolllock-rgb.png
$SUDO rm -f /usr/share/applications/multkeyboard.desktop
$SUDO rm -rf /var/lib/scrolllock
$SUDO rm -f /tmp/multkeyboard_*.sock /tmp/multkeyboard_*.lock /tmp/multkeyboard_assets

echo "✨ MultKeyboard foi completamente desinstalado do sistema."
