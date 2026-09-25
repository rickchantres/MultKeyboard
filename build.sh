#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

BUILD_DIR="/tmp/multkeyboard_build"
mkdir -p "$BUILD_DIR"

echo "==> Gerando headers embutidos..."
xxd -i painel_led_desktop.py > "$BUILD_DIR/embedded_gui.h"
xxd -i scrolllock-daemon.py > "$BUILD_DIR/embedded_daemon.h"
xxd -i scrolllock-rgb.png > "$BUILD_DIR/embedded_icon.h"

echo "==> Compilando instalador C..."
gcc -O2 -Wall src/installer_main.c -I"$BUILD_DIR" -o MultKeyboard-Instalador
strip MultKeyboard-Instalador
chmod +x MultKeyboard-Instalador

echo "==> Sucesso! Executável gerado: MultKeyboard-Instalador ($(du -h MultKeyboard-Instalador | cut -f1))"
