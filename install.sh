#!/usr/bin/env bash
# ==============================================================================
# MultKeyboard v1.0 - Instalador Automático One-Liner para Linux
# Repositório: https://github.com/rickchantres/MultKeyboard
# ==============================================================================
set -e

REPO="rickchantres/MultKeyboard"
INSTALL_DIR="/usr/local/bin"
SYSTEMD_DIR="/etc/systemd/system"
APPS_DIR="/usr/share/applications"
PIXMAPS_DIR="/usr/share/pixmaps"
CONFIG_DIR="/var/lib/scrolllock"

echo "=========================================================="
echo "    ⌨️  MultKeyboard v1.0 - RGB Keyboard Backlight Fix    "
echo "=========================================================="

# Checa dependências básicas
for cmd in python3 curl; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "❌ Erro: '$cmd' é necessário mas não foi encontrado no sistema."
        exit 1
    fi
done

# Checa sudo / root
if [ "$EUID" -ne 0 ]; then
    SUDO="sudo"
    echo "ℹ️  Permissões de administrador (sudo) serão solicitadas."
else
    SUDO=""
fi

TMP_DIR="$(mktemp -d /tmp/multkeyboard_install_XXXXXX)"
cleanup() {
    rm -rf "$TMP_DIR"
}
trap cleanup EXIT

echo "📥 Baixando arquivos da versão mais recente..."
BASE_URL="https://raw.githubusercontent.com/$REPO/main"

curl -fsSL "$BASE_URL/painel_led_desktop.py" -o "$TMP_DIR/painel_led_desktop.py"
curl -fsSL "$BASE_URL/scrolllock-daemon.py" -o "$TMP_DIR/scrolllock-daemon.py"
curl -fsSL "$BASE_URL/scrolllock-rgb.png" -o "$TMP_DIR/scrolllock-rgb.png"

echo "⚙️  Instalando arquivos do sistema..."
$SUDO mkdir -p "$INSTALL_DIR" "$PIXMAPS_DIR" "$APPS_DIR" "$CONFIG_DIR"

$SUDO cp "$TMP_DIR/painel_led_desktop.py" "$INSTALL_DIR/painel_led_desktop.py"
$SUDO chmod 755 "$INSTALL_DIR/painel_led_desktop.py"

$SUDO cp "$TMP_DIR/scrolllock-daemon.py" "$INSTALL_DIR/scrolllock-daemon.py"
$SUDO chmod 755 "$INSTALL_DIR/scrolllock-daemon.py"

$SUDO cp "$TMP_DIR/scrolllock-rgb.png" "$PIXMAPS_DIR/scrolllock-rgb.png"
$SUDO chmod 644 "$PIXMAPS_DIR/scrolllock-rgb.png"

# Arquivo de configuração persistente
if [ ! -f "$CONFIG_DIR/config.json" ]; then
    echo '{"mode": "solid_on", "on_ms": 150, "off_ms": 150}' | $SUDO tee "$CONFIG_DIR/config.json" > /dev/null
    $SUDO chmod 666 "$CONFIG_DIR/config.json"
fi

# Cria serviço systemd
echo "🔧 Configurando serviço em segundo plano (systemd)..."
cat << 'EOF' | $SUDO tee "$SYSTEMD_DIR/scrolllock.service" > /dev/null
[Unit]
Description=Scroll Lock Key and LED Management Daemon
After=multi-user.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /usr/local/bin/scrolllock-daemon.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

$SUDO systemctl daemon-reload
$SUDO systemctl enable scrolllock.service
$SUDO systemctl restart scrolllock.service

# Cria atalho Desktop / Menu Iniciar
echo "🖥️  Criando atalhos no menu e grade de aplicativos..."
cat << 'EOF' | $SUDO tee "$APPS_DIR/multkeyboard.desktop" > /dev/null
[Desktop Entry]
Name=MultKeyboard
Comment=Gerenciador e Iluminação RGB do Teclado
GenericName=RGB Keyboard Controller
Exec=/usr/bin/python3 /usr/local/bin/painel_led_desktop.py --app
Icon=/usr/share/pixmaps/scrolllock-rgb.png
Terminal=false
Type=Application
Categories=Utility;HardwareSettings;GTK;
StartupNotify=true
StartupWMClass=multkeyboard
Keywords=Keyboard;RGB;LED;ScrollLock;MultKeyboard;
EOF
$SUDO chmod 644 "$APPS_DIR/multkeyboard.desktop"

# Adiciona aos favoritos do GNOME (Dock) e Grade se disponível
if command -v gsettings >/dev/null 2>&1; then
    FAVS=$(gsettings get org.gnome.shell favorite-apps 2>/dev/null || echo "[]")
    if [[ "$FAVS" != *"multkeyboard.desktop"* ]]; then
        NEW_FAVS=$(echo "$FAVS" | sed "s/]/, 'multkeyboard.desktop']/")
        gsettings set org.gnome.shell favorite-apps "$NEW_FAVS" 2>/dev/null || true
    fi
fi

# Notifica conclusão de inicialização
touch /var/lib/scrolllock/.installed 2>/dev/null || true

echo ""
echo "=========================================================="
echo "    ✨ MultKeyboard instalado com sucesso!               "
echo "=========================================================="
echo "• Atalho Global: [Scroll Lock] + [Espaço] para abrir/ocultar a janela"
echo "• Controle de Pisca: [Scroll Lock] + [+] acelera / [-] desacelera"
echo "• Para abrir a interface agora: digite 'multkeyboard' ou busque no menu!"
echo ""
