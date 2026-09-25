#!/usr/bin/env python3
"""
Scroll Lock RGB - Painel Estilo Apple macOS
- Transparência real estilo vidro fosco (Frosted Glass com Cairo draw)
- Cantos arredondados e borda de vidro com reflexo
- Sliders arredondados em formato de pílula (Imagem 2) com ativação automática do pisca
- Botões estilo cápsula translúcida (Imagem 1)
- LED fluorescente azul com glow no canto superior direito
- Atalho global [Scroll Lock] + [M] para exibir/minimizar a aplicação
- Ícones nítidos e integrados ao dock e grade de aplicativos
- Modal informativo com explicação detalhada
- Botão Sair com desativação total e tela de reativação com fundo 20% opaco
"""

import os
import sys
import time
import json
import glob
import math
import signal
import socket
import subprocess
import threading
import ast
import cairo
import fcntl
import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gtk, Gdk, GLib, Pango

CONFIG_DIR = "/var/lib/scrolllock"
CONFIG_FILE = "/var/lib/scrolllock/config.json"
INSTALLED_MARKER = "/var/lib/scrolllock/installed"
DISABLED_MARKER = "/var/lib/scrolllock/disabled"
ICON_PATH = "/usr/share/pixmaps/scrolllock-rgb.png"
SOCKET_FILE = f"/tmp/multkeyboard_{os.getuid()}.sock"
LOCK_FILE = f"/tmp/multkeyboard_{os.getuid()}.lock"
SAFE_MIN_MS = 25

SPEED_PRESETS = [
    ("⚡ Strobe Máx Seguro (30ms)", 30, 30),
    ("🚨 Alerta Rápido (75ms)", 75, 75),
    ("💡 Médio Cadenciado (250ms)", 250, 250),
    ("💓 Pulso / Flash (50ms / 800ms)", 50, 800)
]

CSS_STYLES = """
/* Janela Transparente na Base para o Cairo Desenhar o Vidro Fosco */
window, window.background {
    background-color: transparent;
    background: transparent;
    border: none;
}

/* Barra de Título */
.title-bar {
    padding: 10px 14px 4px 14px;
    background: transparent;
}

.title-text {
    font-weight: 700;
    font-size: 12px;
    color: #1d1d1f;
}

/* Botões da Janela (Traffic Lights) - 10px */
.btn-close {
    background: #ff5f56;
    border: 1px solid #e0443e;
    border-radius: 50%;
    min-width: 10px;
    min-height: 10px;
    padding: 0;
}
.btn-close:hover {
    background: #ff3b30;
}

.btn-minimize {
    background: #ffbd2e;
    border: 1px solid #dea123;
    border-radius: 50%;
    min-width: 10px;
    min-height: 10px;
    padding: 0;
}
.btn-minimize:hover {
    background: #ffaa00;
}

/* LED Fluorescente Azul com Glow no Canto Superior Direito */
.led-indicator-on {
    background: #00f0ff;
    border: 1px solid #cbfaff;
    border-radius: 50%;
    min-width: 8px;
    min-height: 8px;
    box-shadow: 0 0 8px #00f0ff, 0 0 16px rgba(0, 240, 255, 0.9);
}

.led-indicator-off {
    background: rgba(160, 170, 185, 0.5);
    border: 1px solid rgba(130, 140, 155, 0.6);
    border-radius: 50%;
    min-width: 8px;
    min-height: 8px;
    box-shadow: none;
}

/* Sliders Arredondados em Cápsula (Imagem 2) */
scale trough {
    min-height: 14px;
    border-radius: 7px;
    background: rgba(0, 0, 0, 0.08);
    border: none;
}

scale highlight {
    min-height: 14px;
    border-radius: 7px;
    background: #00d2ff;
    border: none;
}

scale slider {
    min-width: 18px;
    min-height: 18px;
    margin: -2px;
    border-radius: 50%;
    background: #ffffff;
    border: 1px solid rgba(0,0,0,0.12);
    box-shadow: 0 2px 5px rgba(0,0,0,0.22);
}

.slider-label {
    font-size: 11px;
    font-weight: 600;
    color: #2c3e50;
}

.slider-badge {
    font-size: 11px;
    font-weight: 700;
    font-family: monospace;
    color: #007aff;
    background: rgba(0, 122, 255, 0.12);
    padding: 2px 7px;
    border-radius: 5px;
}

/* Botões Estilo Cápsula macOS (Imagem 1) */
.btn-pill {
    border-radius: 12px;
    padding: 4px 10px;
    font-size: 11px;
    font-weight: 600;
    border: 1px solid rgba(255, 255, 255, 0.85);
    background: rgba(255, 255, 255, 0.65);
    color: #1d1d1f;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    min-height: 28px;
    transition: all 0.15s ease;
}
.btn-pill:hover {
    background: rgba(255, 255, 255, 0.9);
    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
}

.btn-pill-primary {
    background: #007aff;
    color: #ffffff;
    border: 1px solid #0066d6;
    box-shadow: 0 2px 6px rgba(0, 122, 255, 0.35);
}
.btn-pill-primary:hover {
    background: #0066d6;
}

.btn-pill-danger {
    background: #ff3b30;
    color: #ffffff;
    border: 1px solid #d70015;
}
.btn-pill-danger:hover {
    background: #d70015;
}

.btn-info-icon {
    border-radius: 50%;
    min-width: 24px;
    min-height: 24px;
    padding: 0;
    font-size: 12px;
    background: rgba(255, 255, 255, 0.65);
    color: #48484a;
    border: 1px solid rgba(255, 255, 255, 0.85);
}
.btn-info-icon:hover {
    background: rgba(255, 255, 255, 0.95);
    color: #1d1d1f;
}

.btn-exit-small {
    background: rgba(255, 59, 48, 0.08);
    border: 1px solid rgba(255, 59, 48, 0.35);
    color: #ff3b30;
    border-radius: 8px;
    font-size: 10px;
    font-weight: 600;
    padding: 2px 8px;
    min-height: 24px;
}
.btn-exit-small:hover {
    background: rgba(255, 59, 48, 0.2);
}

/* Camada de Overlay com 20% de Opacidade (80% Translúcido) */
.overlay-blur-20 {
    background-color: rgba(240, 243, 248, 0.20);
    border-radius: 20px;
}

.action-card {
    background: rgba(255, 255, 255, 0.40);
    border-radius: 16px;
    padding: 18px 24px;
    border: 1px solid rgba(255, 255, 255, 0.75);
    box-shadow: 0 14px 35px rgba(0,0,0,0.12);
}

.info-card {
    background: rgba(255, 255, 255, 0.45);
    border-radius: 14px;
    padding: 10px 14px;
    border: 1px solid rgba(255, 255, 255, 0.75);
    box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}

menu {
    background-color: rgba(248, 249, 252, 0.85);
    border-radius: 14px;
    border: 1px solid rgba(255, 255, 255, 0.9);
    padding: 6px;
    box-shadow: 0 10px 30px rgba(0,0,0,0.15);
}

menu menuitem {
    border-radius: 8px;
    padding: 6px 12px;
    font-size: 11px;
    font-weight: 500;
    color: #1d1d1f;
}

menu menuitem:hover {
    background-color: #007aff;
    color: #ffffff;
}

.btn-action-main {
    background: #007aff;
    color: #ffffff;
    font-size: 13px;
    font-weight: 700;
    padding: 10px 24px;
    border-radius: 12px;
    border: none;
    box-shadow: 0 4px 12px rgba(0, 122, 255, 0.35);
}
.btn-action-main:hover {
    background: #0066d6;
}
.btn-action-main label {
    color: #ffffff;
    font-size: 13px;
    font-weight: 700;
}
"""

def run_sudo(cmd):
    try:
        p = subprocess.run(
            ["sudo", "-S", "sh", "-c", cmd],
            input="riccha99\n",
            capture_output=True,
            text=True
        )
        return p.returncode == 0
    except Exception as e:
        print("Sudo error:", e)
        return False

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"mode": "solid_on", "on_ms": 150, "off_ms": 150}

def save_config(data):
    try:
        if not os.path.exists(CONFIG_DIR):
            run_sudo(f"mkdir -p '{CONFIG_DIR}' && chmod 777 '{CONFIG_DIR}'")
        tmp = CONFIG_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2)
        try:
            os.chmod(tmp, 0o666)
        except Exception:
            pass
        os.replace(tmp, CONFIG_FILE)
    except Exception as e:
        print("Erro salvando config:", e)

class InfoModal(Gtk.Window):
    def __init__(self, parent):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.set_transient_for(parent)
        self.set_modal(True)
        self.set_default_size(520, 365)
        self.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)
        self.set_decorated(False)
        self.set_resizable(False)

        if os.path.exists(ICON_PATH):
            try:
                self.set_icon_from_file(ICON_PATH)
            except Exception:
                pass

        # Ativa transparência real (RGBA Visual + App Paintable)
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual:
            self.set_visual(visual)
            self.set_app_paintable(True)

        self.connect("draw", self._on_window_draw)

        # Container Principal
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(main_box)

        # 1. Barra de Título Padrão Apple
        title_event_box = Gtk.EventBox()
        title_event_box.connect("button-press-event", self._on_title_drag)
        main_box.pack_start(title_event_box, False, False, 0)

        title_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        title_bar.get_style_context().add_class("title-bar")
        title_event_box.add(title_bar)

        # Traffic Light Fechar (Vermelho - 10px)
        btn_close = Gtk.Button()
        btn_close.get_style_context().add_class("btn-close")
        btn_close.connect("clicked", lambda w: self.destroy())
        btn_close.set_tooltip_text("Fechar informações")
        title_bar.pack_start(btn_close, False, False, 0)

        # Título Centralizado
        lbl_title = Gtk.Label(label="Guia de Uso • MultKeyboard v1.0")
        lbl_title.get_style_context().add_class("title-text")
        title_bar.pack_start(lbl_title, True, True, 0)
        self.set_title("MultKeyboard v1.0 - Guia de Uso")

        # Espaçador simétrico no canto direito
        spacer = Gtk.Box()
        spacer.set_size_request(10, 10)
        title_bar.pack_end(spacer, False, False, 0)

        # 2. Conteúdo Central em Cartões Translúcidos
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        content_box.set_margin_start(16)
        content_box.set_margin_end(16)
        content_box.set_margin_top(8)
        content_box.set_margin_bottom(8)
        main_box.pack_start(content_box, True, True, 0)

        # Cartão 1: Por que essa correção existe no Ubuntu
        c1 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        c1.get_style_context().add_class("info-card")
        t1_title = Gtk.Label()
        t1_title.set_markup("<span font='10.5' weight='bold' color='#007aff'>💡 Por que essa correção existe no Ubuntu?</span>")
        t1_title.set_halign(Gtk.Align.START)
        c1.pack_start(t1_title, False, False, 0)

        t1_body = Gtk.Label()
        t1_body.set_markup("<span font='9.5' color='#2c3e50'>Cerca de 90% dos teclados gamers utilizam o circuito do Scroll Lock para alimentar a iluminação RGB. No Ubuntu 24.04+ (Wayland), o sistema ignora a tecla. Este programa corrige o funcionamento no kernel de forma definitiva.</span>")
        t1_body.set_line_wrap(True)
        t1_body.set_halign(Gtk.Align.START)
        c1.pack_start(t1_body, False, False, 0)
        content_box.pack_start(c1, False, False, 0)

        # Cartão 2: Atalhos Rápidos no Teclado
        c2 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        c2.get_style_context().add_class("info-card")
        t2_title = Gtk.Label()
        t2_title.set_markup("<span font='10.5' weight='bold' color='#007aff'>⌨️ Atalhos Rápidos de Hardware no Teclado:</span>")
        t2_title.set_halign(Gtk.Align.START)
        c2.pack_start(t2_title, False, False, 0)

        t2_body = Gtk.Label()
        t2_body.set_markup(
            "<span font='9.5' color='#2c3e50'>"
            "• <b>[Scroll Lock] + [Espaço]</b> : Abre ou minimiza esta janela instantaneamente (ou <b>[F12]</b>).\n"
            "• <b>[Scroll Lock] + [+]</b> : Liga e acelera as piscadas (até limite seguro de 30ms).\n"
            "• <b>[Scroll Lock] + [-]</b> : Desacelera as piscadas. No ritmo mais lento, apaga o teclado.\n"
            "• <b>[Scroll Lock] (toque simples)</b> : Alterna ligado/desligado ou interrompe o pisca."
            "</span>"
        )
        t2_body.set_line_wrap(True)
        t2_body.set_halign(Gtk.Align.START)
        c2.pack_start(t2_body, False, False, 0)
        content_box.pack_start(c2, False, False, 0)

        # Cartão 3: Persistência
        c3 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        c3.get_style_context().add_class("info-card")
        t3_title = Gtk.Label()
        t3_title.set_markup("<span font='10.5' weight='bold' color='#007aff'>🚀 Persistência &amp; Segundo Plano:</span>")
        t3_title.set_halign(Gtk.Align.START)
        c3.pack_start(t3_title, False, False, 0)

        t3_body = Gtk.Label()
        t3_body.set_markup("<span font='9.5' color='#2c3e50'>O serviço roda em segundo plano e persiste após reiniciar o sistema. O botão <b>Sair</b> desativa o serviço e apaga os LEDs até ser reaberto.</span>")
        t3_body.set_line_wrap(True)
        t3_body.set_halign(Gtk.Align.START)
        c3.pack_start(t3_body, False, False, 0)
        content_box.pack_start(c3, False, False, 0)

        # 3. Rodapé com Botão Entendi
        bottom_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        bottom_bar.set_margin_start(16)
        bottom_bar.set_margin_end(16)
        bottom_bar.set_margin_bottom(12)
        main_box.pack_end(bottom_bar, False, False, 0)

        btn_ok = Gtk.Button(label="Entendi")
        btn_ok.get_style_context().add_class("btn-pill")
        btn_ok.get_style_context().add_class("btn-pill-primary")
        btn_ok.set_size_request(90, 28)
        btn_ok.connect("clicked", lambda w: self.destroy())
        bottom_bar.pack_end(btn_ok, False, False, 0)

        self.show_all()

    def _on_title_drag(self, widget, event):
        if event.button == 1:
            self.begin_move_drag(event.button, int(event.x_root), int(event.y_root), event.time)

    def _on_window_draw(self, widget, cr):
        """Desenha o fundo de vidro fosco translúcido estilo macOS."""
        cr.set_operator(cairo.OPERATOR_CLEAR)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)

        w = widget.get_allocated_width()
        h = widget.get_allocated_height()
        r = 20

        def draw_rounded_rect(ctx, x, y, width, height, radius):
            ctx.new_sub_path()
            ctx.arc(x + width - radius, y + radius, radius, -math.pi / 2, 0)
            ctx.arc(x + width - radius, y + height - radius, radius, 0, math.pi / 2)
            ctx.arc(x + radius, y + height - radius, radius, math.pi / 2, math.pi)
            ctx.arc(x + radius, y + radius, radius, math.pi, 3 * math.pi / 2)
            ctx.close_path()

        # Fundo Translúcido de Vidro Fosco macOS (55% opaco)
        draw_rounded_rect(cr, 2, 2, w - 4, h - 4, r)
        cr.set_source_rgba(0.95, 0.96, 0.99, 0.58)
        cr.fill_preserve()

        # Borda de reflexo de vidro (1.5px branco translúcido)
        cr.set_line_width(1.5)
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.75)
        cr.stroke()

        return False

class AppleLedPanel(Gtk.Window):
    def __init__(self):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.set_default_size(480, 260)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_decorated(False)
        self.set_resizable(False)

        # Configura ícone da janela
        if os.path.exists(ICON_PATH):
            try:
                self.set_icon_from_file(ICON_PATH)
            except Exception:
                pass

        # Ativa transparência real (RGBA Visual + App Paintable)
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual:
            self.set_visual(visual)
            self.set_app_paintable(True)

        self.cfg = load_config()
        self.last_mtime = 0
        self.sim_phase = True
        self.last_sim_toggle = time.time()
        self.is_installed = os.path.exists(INSTALLED_MARKER) or (
            os.path.exists("/usr/local/bin/scrolllock-daemon.py") and os.path.exists("/etc/systemd/system/scrolllock.service")
        )
        self.is_service_disabled = os.path.exists(DISABLED_MARKER)
        self.is_minimized_by_hotkey = False
        self.rgb_anim_active = False
        self.rgb_anim_start = 0

        self._load_css()
        self._build_ui()

        # Conecta sinal de desenho Cairo para renderizar o vidro fosco translúcido
        self.connect("draw", self._on_window_draw)

        # Conecta sinal SIGUSR1 para o atalho Scroll Lock + M
        try:
            from gi.repository import GLibUnix
            GLibUnix.signal_add(GLib.PRIORITY_DEFAULT, signal.SIGUSR1, self._on_toggle_hotkey)
        except Exception:
            try:
                GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGUSR1, self._on_toggle_hotkey)
            except Exception:
                pass

        # Inicia servidor local de instância única
        self._start_instance_server()
        self.connect("destroy", self._on_destroy)

        # Loop de sincronização com o daemon (15ms para fluidez total em velocidades altas)
        GLib.timeout_add(15, self._sync_loop)

        # Na inicialização, garante que aparece na frente e centralizada no monitor ativo
        GLib.idle_add(self.bring_to_front_center)

    def _start_instance_server(self):
        """Servidor de socket Unix para garantir instância única."""
        try:
            if os.path.exists(SOCKET_FILE):
                os.remove(SOCKET_FILE)
            self.server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.server_sock.bind(SOCKET_FILE)
            self.server_sock.listen(5)

            def server_thread():
                while True:
                    try:
                        conn, _ = self.server_sock.accept()
                        data = conn.recv(1024)
                        conn.close()
                        if b"ACTIVATE_INSTALLER" in data:
                            GLib.idle_add(self._handle_activate_installer)
                        elif b"TOGGLE_HOTKEY" in data:
                            GLib.idle_add(self._on_toggle_hotkey)
                        elif b"ACTIVATE" in data:
                            GLib.idle_add(self.bring_to_front_center)
                    except Exception:
                        break

            t = threading.Thread(target=server_thread, daemon=True)
            t.start()
        except Exception as e:
            print("Aviso ao iniciar socket da instância única:", e)

    def _handle_activate_installer(self):
        self.is_installed = os.path.exists(INSTALLED_MARKER) or (
            os.path.exists("/usr/local/bin/scrolllock-daemon.py") and os.path.exists("/etc/systemd/system/scrolllock.service")
        )
        if self.is_installed:
            self._show_already_installed_screen()
        else:
            self._show_welcome_installer_screen()
        self.bring_to_front_center()

    def _on_destroy(self, *args):
        """Limpa o socket Unix ao encerrar."""
        try:
            if hasattr(self, 'server_sock'):
                self.server_sock.close()
            if os.path.exists(SOCKET_FILE):
                os.remove(SOCKET_FILE)
        except Exception:
            pass

    def bring_to_front_center(self):
        """Traz o programa para a frente de todas as janelas no centro do monitor em que está aberto."""
        self.deiconify()
        self.show()
        try:
            from gi.repository import Gdk
            Gdk.notify_startup_complete()
        except Exception:
            pass
        try:
            screen = self.get_screen()
            display = screen.get_display()
            seat = display.get_default_seat()
            device = seat.get_pointer() if seat else None
            monitor = None
            if device:
                _, x, y = device.get_position()
                monitor = display.get_monitor_at_point(x, y)
            if not monitor:
                monitor = display.get_primary_monitor() or display.get_monitor(0)

            if monitor:
                geom = monitor.get_geometry()
                w, h = self.get_size()
                new_x = geom.x + max(0, (geom.width - w) // 2)
                new_y = geom.y + max(0, (geom.height - h) // 2)
                self.move(new_x, new_y)
            else:
                self.set_position(Gtk.WindowPosition.CENTER)
        except Exception:
            self.set_position(Gtk.WindowPosition.CENTER)

        self.present()
        self.set_keep_above(True)
        GLib.timeout_add(1500, lambda: self.set_keep_above(False) or False)
        self.is_minimized_by_hotkey = False
        return False

    def _load_css(self):
        self.css_provider = Gtk.CssProvider()
        self.css_provider.load_from_data(CSS_STYLES.encode('utf-8'))
        Gtk.StyleContext.add_provider_for_screen(
            self.get_screen(), self.css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def _on_window_draw(self, widget, cr):
        """Desenha o fundo de vidro fosco translúcido estilo macOS."""
        cr.set_operator(cairo.OPERATOR_CLEAR)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)

        w = widget.get_allocated_width()
        h = widget.get_allocated_height()
        r = 20

        def draw_rounded_rect(ctx, x, y, width, height, radius):
            ctx.new_sub_path()
            ctx.arc(x + width - radius, y + radius, radius, -math.pi / 2, 0)
            ctx.arc(x + width - radius, y + height - radius, radius, 0, math.pi / 2)
            ctx.arc(x + radius, y + height - radius, radius, math.pi / 2, math.pi)
            ctx.arc(x + radius, y + radius, radius, math.pi, 3 * math.pi / 2)
            ctx.close_path()

        # Fundo Translúcido de Vidro Fosco macOS (55% opaco / 45% transparente para ver tudo atrás)
        draw_rounded_rect(cr, 2, 2, w - 4, h - 4, r)
        cr.set_source_rgba(0.95, 0.96, 0.99, 0.55)
        cr.fill_preserve()

        # Borda de reflexo de vidro (1.5px branco translúcido)
        cr.set_line_width(1.5)
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.75)
        cr.stroke()

        # Efeito de 5 segundos de sombra girando em sentido horário com as cores do arco-íris (RGB)
        if hasattr(self, 'rgb_anim_active') and self.rgb_anim_active:
            elapsed = time.time() - self.rgb_anim_start
            if elapsed < 5.0:
                angle = (elapsed * 2.0 * math.pi) % (2.0 * math.pi)
                r_c = 0.5 + 0.5 * math.sin(angle)
                g_c = 0.5 + 0.5 * math.sin(angle + 2.0 * math.pi / 3.0)
                b_c = 0.5 + 0.5 * math.sin(angle + 4.0 * math.pi / 3.0)

                draw_rounded_rect(cr, 1, 1, w - 2, h - 2, r)
                cr.set_line_width(3.0)
                cr.set_source_rgba(r_c, g_c, b_c, 0.95)
                cr.stroke()
            else:
                self.rgb_anim_active = False

        return False

    def _on_toggle_hotkey(self):
        """Acionado via Scroll Lock + M para alternar a exibição da janela."""
        if self.get_property("visible") and not self.is_minimized_by_hotkey:
            self.iconify()
            self.is_minimized_by_hotkey = True
        else:
            self.bring_to_front_center()
        return True

    def _build_ui(self):
        self.overlay = Gtk.Overlay()
        self.add(self.overlay)

        # Container Principal
        self.main_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.overlay.add(self.main_container)

        # 1. Barra de Título Padrão Apple
        title_event_box = Gtk.EventBox()
        title_event_box.connect("button-press-event", self._on_title_drag)
        self.main_container.pack_start(title_event_box, False, False, 0)

        title_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        title_bar.get_style_context().add_class("title-bar")
        title_event_box.add(title_bar)

        # Traffic Lights (Fechar e Minimizar) - 10px
        btn_close = Gtk.Button()
        btn_close.get_style_context().add_class("btn-close")
        btn_close.connect("clicked", lambda w: Gtk.main_quit())
        btn_close.set_tooltip_text("Fechar janela (continua ativo em segundo plano)")
        title_bar.pack_start(btn_close, False, False, 0)

        btn_min = Gtk.Button()
        btn_min.get_style_context().add_class("btn-minimize")
        btn_min.connect("clicked", lambda w: self.iconify())
        btn_min.set_tooltip_text("Minimizar")
        title_bar.pack_start(btn_min, False, False, 0)

        # Título Centralizado
        lbl_title = Gtk.Label(label="MultKeyboard v1.0")
        lbl_title.get_style_context().add_class("title-text")
        title_bar.pack_start(lbl_title, True, True, 0)
        self.set_title("MultKeyboard v1.0")

        # LED Fluorescente Azul com Glow no Canto Superior Direito
        self.led_indicator = Gtk.Box()
        self.led_indicator.get_style_context().add_class("led-indicator-on")
        self.led_indicator.set_valign(Gtk.Align.CENTER)
        self.led_indicator.set_tooltip_text("Status do LED do teclado")
        title_bar.pack_end(self.led_indicator, False, False, 4)

        # 2. Conteúdo Central (Sliders em Pílula)
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        content_box.set_margin_start(20)
        content_box.set_margin_end(20)
        content_box.set_margin_top(6)
        content_box.set_margin_bottom(6)
        self.main_container.pack_start(content_box, True, True, 0)

        # Slider 1: Tempo Aceso (ON)
        row1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        lbl_on = Gtk.Label(label="⏱️ Tempo Aceso (ON)")
        lbl_on.get_style_context().add_class("slider-label")
        row1.pack_start(lbl_on, False, False, 0)
        
        self.badge_on = Gtk.Label(label=f"{self.cfg.get('on_ms', 150)} ms")
        self.badge_on.get_style_context().add_class("slider-badge")
        row1.pack_end(self.badge_on, False, False, 0)
        content_box.pack_start(row1, False, False, 0)

        self.scale_on = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, SAFE_MIN_MS, 1500, 5)
        self.scale_on.set_draw_value(False)
        self.scale_on.set_value(self.cfg.get("on_ms", 150))
        self.scale_on.connect("value-changed", self._on_scale_changed)
        self.scale_on.connect("button-press-event", self._on_scale_pressed)
        content_box.pack_start(self.scale_on, False, False, 0)

        # Slider 2: Tempo Apagado (OFF)
        row2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        lbl_off = Gtk.Label(label="🌑 Tempo Apagado (OFF)")
        lbl_off.get_style_context().add_class("slider-label")
        row2.pack_start(lbl_off, False, False, 0)
        
        self.badge_off = Gtk.Label(label=f"{self.cfg.get('off_ms', 150)} ms")
        self.badge_off.get_style_context().add_class("slider-badge")
        row2.pack_end(self.badge_off, False, False, 0)
        content_box.pack_start(row2, False, False, 0)

        self.scale_off = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, SAFE_MIN_MS, 1500, 5)
        self.scale_off.set_draw_value(False)
        self.scale_off.set_value(self.cfg.get("off_ms", 150))
        self.scale_off.connect("value-changed", self._on_scale_changed)
        self.scale_off.connect("button-press-event", self._on_scale_pressed)
        content_box.pack_start(self.scale_off, False, False, 0)

        # 3. Barra de Botões Inferiores
        btn_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        btn_bar.set_margin_start(20)
        btn_bar.set_margin_end(20)
        btn_bar.set_margin_bottom(12)
        self.main_container.pack_end(btn_bar, False, False, 0)

        # Botão Piscar
        self.btn_blink = Gtk.Button(label="⚡ Piscar")
        self.btn_blink.get_style_context().add_class("btn-pill")
        self.btn_blink.connect("clicked", self._set_mode_blink)
        btn_bar.pack_start(self.btn_blink, True, True, 0)

        # Botão Aceso
        self.btn_solid_on = Gtk.Button(label="💡 Aceso")
        self.btn_solid_on.get_style_context().add_class("btn-pill")
        self.btn_solid_on.connect("clicked", self._set_mode_solid_on)
        btn_bar.pack_start(self.btn_solid_on, True, True, 0)

        # Botão Apagado
        self.btn_solid_off = Gtk.Button(label="🌑 Apagado")
        self.btn_solid_off.get_style_context().add_class("btn-pill")
        self.btn_solid_off.connect("clicked", self._set_mode_solid_off)
        btn_bar.pack_start(self.btn_solid_off, True, True, 0)

        # Menu Presets ("Teste esses modos")
        self.btn_presets = Gtk.MenuButton(label="Teste esses ▾")
        self.btn_presets.get_style_context().add_class("btn-pill")
        self._build_preset_menu()
        btn_bar.pack_start(self.btn_presets, True, True, 0)

        # Ícone de Informação (ℹ️)
        btn_info = Gtk.Button(label="ℹ")
        btn_info.get_style_context().add_class("btn-info-icon")
        btn_info.connect("clicked", lambda w: InfoModal(self))
        btn_info.set_tooltip_text("Informações e atalhos")
        btn_bar.pack_start(btn_info, False, False, 2)

        # Botão Sair
        btn_exit = Gtk.Button(label="Sair")
        btn_exit.get_style_context().add_class("btn-exit-small")
        btn_exit.connect("clicked", self._on_exit_clicked)
        btn_exit.set_tooltip_text("Desativa o serviço e apaga a iluminação")
        btn_bar.pack_start(btn_exit, False, False, 2)

        # 4. Camadas de Overlay (20% de Opacidade / 80% Translúcido)
        self.overlay_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.overlay_box.get_style_context().add_class("overlay-blur-20")
        self.overlay_box.set_halign(Gtk.Align.FILL)
        self.overlay_box.set_valign(Gtk.Align.FILL)
        self.overlay_box.set_no_show_all(True)

        self.center_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.center_card.get_style_context().add_class("action-card")
        self.center_card.set_halign(Gtk.Align.CENTER)
        self.center_card.set_valign(Gtk.Align.CENTER)
        self.center_card.set_size_request(400, -1)

        self.lbl_card_title = Gtk.Label()
        self.lbl_card_title.set_line_wrap(True)
        self.lbl_card_title.set_justify(Gtk.Justification.CENTER)
        self.center_card.pack_start(self.lbl_card_title, False, False, 0)

        self.btn_card_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.btn_card_box.set_halign(Gtk.Align.CENTER)
        self.center_card.pack_start(self.btn_card_box, False, False, 4)

        self.overlay_box.pack_start(self.center_card, True, True, 0)
        self.overlay.add_overlay(self.overlay_box)

        # Define métodos de overlay com controle de passagem de cliques
        self._hide_overlay()

        # Mostra a base da janela
        self.show_all()

        # Configura conteúdo com base no estado e modo de execução
        is_installer_mode = "--installer" in sys.argv or "--app" not in sys.argv
        if is_installer_mode:
            if self.is_installed:
                self._show_already_installed_screen()
            else:
                self._show_welcome_installer_screen()
        elif self.is_service_disabled:
            self._show_reactivate_screen()
        else:
            self._hide_overlay()

    def _show_overlay(self):
        """Exibe o overlay e ativa captura de cliques."""
        self.overlay_box.set_no_show_all(False)
        self.overlay.set_overlay_pass_through(self.overlay_box, False)
        self.overlay_box.show_all()

    def _hide_overlay(self):
        """Esconde o overlay e deixa todos os cliques passarem livremente para os controles."""
        self.overlay_box.hide()
        self.overlay_box.set_no_show_all(True)
        self.overlay.set_overlay_pass_through(self.overlay_box, True)

    def _show_welcome_installer_screen(self):
        """Tela de boas-vindas / 1ª Execução."""
        self.lbl_card_title.set_markup(
            "<span font='10.5' weight='bold' color='#1d1d1f'>O seu linux não está ligando o Scroll Lock?</span>\n"
            "<span font='9.5' color='#2c3e50'>Esse programa resolve definitivamente o problema, e ainda deixa tudo com mais estilo.\n"
            "Clique em <b>Instalar</b> e veja a mágica acontecer!</span>"
        )
        for child in self.btn_card_box.get_children():
            self.btn_card_box.remove(child)

        btn_install = Gtk.Button(label="✨ Instalar")
        btn_install.get_style_context().add_class("btn-action-main")
        btn_install.set_size_request(130, 34)
        btn_install.connect("clicked", self._install_system)
        self.btn_card_box.pack_start(btn_install, False, False, 0)
        self._show_overlay()

    def _show_already_installed_screen(self):
        """Tela quando o usuário clica no pacote de instalação, mas o programa já foi instalado."""
        self.lbl_card_title.set_markup(
            "<span font='10.5' weight='bold' color='#1d1d1f'>Olá, parece que o programa já foi instalado.</span>\n"
            "<span font='9.5' color='#2c3e50'>Deseja reinstalar novamente e reparar algo que esteja incorreto ou desinstalar esse programa?</span>"
        )
        for child in self.btn_card_box.get_children():
            self.btn_card_box.remove(child)

        # Botão Reinstalar / Reparar
        btn_reinstall = Gtk.Button(label="🔧 Reinstalar / Reparar")
        btn_reinstall.get_style_context().add_class("btn-pill")
        btn_reinstall.get_style_context().add_class("btn-pill-primary")
        btn_reinstall.set_size_request(160, 32)
        btn_reinstall.connect("clicked", self._reinstall_repair_system)
        self.btn_card_box.pack_start(btn_reinstall, False, False, 0)

        # Botão Desinstalar
        btn_uninstall = Gtk.Button(label="🗑️ Desinstalar")
        btn_uninstall.get_style_context().add_class("btn-pill")
        btn_uninstall.get_style_context().add_class("btn-pill-danger")
        btn_uninstall.set_size_request(120, 32)
        btn_uninstall.connect("clicked", self._uninstall_system)
        self.btn_card_box.pack_start(btn_uninstall, False, False, 0)

        self._show_overlay()

    def _show_reactivate_screen(self):
        """Tela após clicar em Sair."""
        self.lbl_card_title.set_markup(
            "<span font='11' weight='bold' color='#1d1d1f'>Iluminação do Teclado Desativada</span>\n"
            "<span font='9.5' color='#2c3e50'>Clique no botão abaixo para reativar o serviço e acender o teclado.</span>"
        )
        for child in self.btn_card_box.get_children():
            self.btn_card_box.remove(child)

        btn_reactivate = Gtk.Button(label="💡 Vamos ligar esse teclado ?")
        btn_reactivate.get_style_context().add_class("btn-action-main")
        btn_reactivate.connect("clicked", self._reactivate_system)
        self.btn_card_box.pack_start(btn_reactivate, False, False, 0)
        self._show_overlay()

    def _build_preset_menu(self):
        menu = Gtk.Menu()
        for label, on_ms, off_ms in SPEED_PRESETS:
            item = Gtk.MenuItem(label=label)
            item.connect("activate", lambda w, on=on_ms, off=off_ms: self._apply_preset(on, off))
            menu.append(item)
        menu.show_all()
        self.btn_presets.set_popup(menu)

    def _apply_preset(self, on_ms, off_ms):
        self.scale_on.set_value(on_ms)
        self.scale_off.set_value(off_ms)
        self.cfg["on_ms"] = on_ms
        self.cfg["off_ms"] = off_ms
        self.cfg["mode"] = "blink"
        save_config(self.cfg)
        self._update_button_styles()

    def _on_title_drag(self, widget, event):
        if event.button == 1:
            self.begin_move_drag(event.button, int(event.x_root), int(event.y_root), event.time)

    def _on_scale_pressed(self, widget, event):
        # Ao clicar/pressionar a barra, ativa imediatamente o modo piscar
        self._apply_slider_blink()
        return False

    def _apply_slider_blink(self):
        on_v = max(SAFE_MIN_MS, int(self.scale_on.get_value()))
        off_v = max(SAFE_MIN_MS, int(self.scale_off.get_value()))
        self.badge_on.set_text(f"{on_v} ms")
        self.badge_off.set_text(f"{off_v} ms")
        self.cfg["on_ms"] = on_v
        self.cfg["off_ms"] = off_v

        # Regra: seja estando ligado ou desligado, ao arrastar/clicar na barra
        # o teclado vai imediatamente para a frequência de piscada selecionada
        self.cfg["mode"] = "blink"

        if os.path.exists(DISABLED_MARKER):
            try:
                os.remove(DISABLED_MARKER)
            except Exception:
                pass
            self._hide_overlay()

        save_config(self.cfg)
        try:
            self.last_mtime = os.path.getmtime(CONFIG_FILE)
        except Exception:
            pass
        self._update_button_styles()

    def _on_scale_changed(self, scale):
        self._apply_slider_blink()

    def _set_mode_blink(self, _=None):
        self.cfg["mode"] = "blink"
        save_config(self.cfg)
        self._update_button_styles()

    def _set_mode_solid_on(self, _=None):
        self.cfg["mode"] = "solid_on"
        save_config(self.cfg)
        self._update_button_styles()

    def _set_mode_solid_off(self, _=None):
        self.cfg["mode"] = "solid_off"
        save_config(self.cfg)
        self._update_button_styles()

    def _update_button_styles(self):
        mode = self.cfg.get("mode", "solid_on")
        for btn in [self.btn_blink, self.btn_solid_on, self.btn_solid_off]:
            btn.get_style_context().remove_class("btn-pill-primary")
            btn.get_style_context().remove_class("btn-pill-danger")

        if mode == "blink":
            self.btn_blink.get_style_context().add_class("btn-pill-primary")
        elif mode == "solid_on":
            self.btn_solid_on.get_style_context().add_class("btn-pill-primary")
        else:
            self.btn_solid_off.get_style_context().add_class("btn-pill-danger")

    def _sync_loop(self):
        if os.path.exists(CONFIG_FILE):
            try:
                mt = os.path.getmtime(CONFIG_FILE)
                if mt > self.last_mtime:
                    self.last_mtime = mt
                    self.cfg = load_config()
                    if not self.scale_on.has_focus():
                        self.scale_on.set_value(self.cfg.get("on_ms", 150))
                    if not self.scale_off.has_focus():
                        self.scale_off.set_value(self.cfg.get("off_ms", 150))
                    self.badge_on.set_text(f"{self.cfg.get('on_ms', 150)} ms")
                    self.badge_off.set_text(f"{self.cfg.get('off_ms', 150)} ms")
                    self._update_button_styles()
            except Exception:
                pass

        mode = self.cfg.get("mode", "solid_on")
        now = time.time()
        ctx = self.led_indicator.get_style_context()

        if mode == "solid_on":
            ctx.remove_class("led-indicator-off")
            ctx.add_class("led-indicator-on")
        elif mode == "solid_off":
            ctx.remove_class("led-indicator-on")
            ctx.add_class("led-indicator-off")
        elif mode == "blink":
            on_s = max(SAFE_MIN_MS, self.cfg.get("on_ms", 150)) / 1000.0
            off_s = max(SAFE_MIN_MS, self.cfg.get("off_ms", 150)) / 1000.0
            interval = on_s if self.sim_phase else off_s
            if now - self.last_sim_toggle >= interval:
                self.sim_phase = not self.sim_phase
                self.last_sim_toggle = now
                if self.sim_phase:
                    ctx.remove_class("led-indicator-off")
                    ctx.add_class("led-indicator-on")
                else:
                    ctx.remove_class("led-indicator-on")
                    ctx.add_class("led-indicator-off")

        if hasattr(self, 'rgb_anim_active') and self.rgb_anim_active:
            self.queue_draw()

        return True

    def _install_system(self, _):
        """Instalação com integração ao sistema."""
        try:
            # 1. Garante diretório de configuração do serviço
            run_sudo(f"mkdir -p '{CONFIG_DIR}' && chmod 777 '{CONFIG_DIR}'")
            with open(INSTALLED_MARKER, "w") as f:
                f.write("1\n")
            try:
                os.chmod(INSTALLED_MARKER, 0o666)
            except Exception:
                pass

            if os.path.exists(DISABLED_MARKER):
                try:
                    os.remove(DISABLED_MARKER)
                except Exception:
                    run_sudo(f"rm -f '{DISABLED_MARKER}'")

            # 2. Ativa teste com pisca rápido (30ms) como solicitado
            self.cfg["mode"] = "blink"
            self.cfg["on_ms"] = 30
            self.cfg["off_ms"] = 30
            self.scale_on.set_value(30)
            self.scale_off.set_value(30)
            self.badge_on.set_text("30 ms")
            self.badge_off.set_text("30 ms")
            save_config(self.cfg)
            try:
                self.last_mtime = os.path.getmtime(CONFIG_FILE)
            except Exception:
                pass

            # 3. Instala o script da GUI e daemon permanentemente no sistema
            cur_dir = os.path.dirname(os.path.abspath(__file__))
            
            gui_src = os.path.abspath(__file__)
            run_sudo(f"cp '{gui_src}' /usr/local/bin/painel_led_desktop.py")
            run_sudo("chmod 755 /usr/local/bin/painel_led_desktop.py")

            daemon_src = os.path.join(cur_dir, "scrolllock-daemon.py")
            if not os.path.exists(daemon_src):
                daemon_src = "/tmp/multkeyboard_assets/scrolllock-daemon.py"
            if os.path.exists(daemon_src):
                run_sudo(f"cp '{daemon_src}' /usr/local/bin/scrolllock-daemon.py")
                run_sudo("chmod 755 /usr/local/bin/scrolllock-daemon.py")

            icon_src = os.path.join(cur_dir, "scrolllock-rgb.png")
            if not os.path.exists(icon_src):
                icon_src = "/tmp/multkeyboard_assets/scrolllock-rgb.png"
            if os.path.exists(icon_src):
                run_sudo(f"cp '{icon_src}' /usr/share/pixmaps/scrolllock-rgb.png")
                run_sudo("chmod 644 /usr/share/pixmaps/scrolllock-rgb.png")

            # 4. Cria e habilita a unidade de serviço systemd
            service_content = """[Unit]
Description=Scroll Lock Key and LED Management Daemon
After=multi-user.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /usr/local/bin/scrolllock-daemon.py
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
"""
            with open("/tmp/scrolllock.service", "w") as f:
                f.write(service_content)
            run_sudo("cp /tmp/scrolllock.service /etc/systemd/system/scrolllock.service")
            run_sudo("systemctl daemon-reload")
            run_sudo("systemctl enable --now scrolllock.service")

            desktop_entry = """[Desktop Entry]
Name=MultKeyboard v1.0
Comment=Controle de Iluminação e LED do Teclado no Linux
Exec=/usr/bin/python3 /usr/local/bin/painel_led_desktop.py --app
Icon=/usr/share/pixmaps/scrolllock-rgb.png
Terminal=false
Type=Application
Categories=Utility;Settings;HardwareSettings;
StartupNotify=false
Keywords=Keyboard;LED;RGB;Scroll;Lock;MultKeyboard;
"""
            with open("/tmp/multkeyboard.desktop", "w") as f:
                f.write(desktop_entry)

            run_sudo("cp /tmp/multkeyboard.desktop /usr/share/applications/multkeyboard.desktop")
            run_sudo("chmod 644 /usr/share/applications/multkeyboard.desktop")
            run_sudo("rm -f /usr/share/applications/scrolllock-rgb.desktop")
            subprocess.run("update-desktop-database ~/.local/share/applications 2>/dev/null || true", shell=True)
            run_sudo("update-desktop-database /usr/share/applications")

            # Atalho permanente na Área de Trabalho do usuário
            desktop_dir = os.path.expanduser("~/Desktop")
            if os.path.exists(desktop_dir):
                user_desktop = os.path.join(desktop_dir, "MultKeyboard.desktop")
                with open(user_desktop, "w") as f:
                    f.write(desktop_entry)
                os.chmod(user_desktop, 0o755)
                subprocess.run(f"gio set '{user_desktop}' metadata::trusted true 2>/dev/null || true", shell=True)

            # Adiciona aos favoritos do GNOME (Dock) e Grade de Aplicativos
            try:
                res = subprocess.check_output(["gsettings", "get", "org.gnome.shell", "favorite-apps"]).decode().strip()
                favorites = ast.literal_eval(res)
                if "scrolllock-rgb.desktop" in favorites:
                    favorites.remove("scrolllock-rgb.desktop")
                if "multkeyboard.desktop" not in favorites:
                    favorites.append("multkeyboard.desktop")
                subprocess.run(["gsettings", "set", "org.gnome.shell", "favorite-apps", str(favorites)])
            except Exception as e:
                print("Aviso ao fixar no dock:", e)

            self.is_installed = True

            # Exibe confirmação visual de instalação concluída!
            self.lbl_card_title.set_markup(
                "<span font='11' weight='bold' color='#34c759'>🎉 Instalação Concluída com Sucesso!</span>\n"
                "<span font='9.5' color='#2c3e50'>O <b>MultKeyboard v1.0</b> foi integrado ao sistema e fixado no Dock.\n"
                "Iniciando modo teste do LED...</span>"
            )
            for child in self.btn_card_box.get_children():
                self.btn_card_box.remove(child)

            btn_enter = Gtk.Button(label="🚀 Entrar no Painel")
            btn_enter.get_style_context().add_class("btn-action-main")
            def on_enter(w):
                self._hide_overlay()
                self._update_button_styles()
                self.rgb_anim_active = True
                self.rgb_anim_start = time.time()
                self.queue_draw()
            btn_enter.connect("clicked", on_enter)
            self.btn_card_box.pack_start(btn_enter, False, False, 0)
            self._show_overlay()
            GLib.timeout_add(2200, lambda: on_enter(None) or False)

        except Exception as e:
            print("Erro na instalação:", e)

    def _reinstall_repair_system(self, _):
        """Reinstala e repara todos os arquivos e serviços."""
        self._install_system(_)

    def _uninstall_system(self, _):
        """Desinstala completamente o serviço e atalhos, mantendo apenas o arquivo baixado."""
        try:
            # 1. Apaga os LEDs do teclado
            for p in glob.glob("/sys/class/leds/*::scrolllock/brightness"):
                try:
                    with open(p, "w") as f:
                        f.write("0\n")
                except Exception:
                    pass

            # 2. Desativa e remove o serviço systemd
            run_sudo("systemctl stop scrolllock.service 2>/dev/null || true")
            run_sudo("systemctl disable scrolllock.service 2>/dev/null || true")
            run_sudo("rm -f /etc/systemd/system/scrolllock.service")
            run_sudo("systemctl daemon-reload")
            run_sudo("pkill -9 -f scrolllock-daemon.py 2>/dev/null || true")

            # 3. Remove atalho .desktop, binários e arquivos
            run_sudo("rm -f /usr/share/applications/multkeyboard.desktop")
            run_sudo("rm -f /usr/share/applications/scrolllock-rgb.desktop")
            run_sudo("rm -f /usr/local/bin/scrolllock-daemon.py")
            run_sudo("rm -f /usr/local/bin/painel_led_desktop.py")
            run_sudo("rm -f /usr/share/pixmaps/scrolllock-rgb.png")
            run_sudo("rm -rf /var/lib/scrolllock")
            run_sudo("update-desktop-database /usr/share/applications 2>/dev/null || true")

            user_desktop = os.path.expanduser("~/Desktop/MultKeyboard.desktop")
            if os.path.exists(user_desktop):
                try:
                    os.remove(user_desktop)
                except Exception:
                    pass

            # 4. Remove do dock do GNOME
            try:
                res = subprocess.check_output(["gsettings", "get", "org.gnome.shell", "favorite-apps"]).decode().strip()
                favorites = ast.literal_eval(res)
                changed = False
                for item in ["multkeyboard.desktop", "scrolllock-rgb.desktop"]:
                    if item in favorites:
                        favorites.remove(item)
                        changed = True
                if changed:
                    subprocess.run(["gsettings", "set", "org.gnome.shell", "favorite-apps", str(favorites)])
            except Exception:
                pass

            self.is_installed = False

            # 5. Informa sucesso e encerra
            self.lbl_card_title.set_markup(
                "<span font='11' weight='bold' color='#34c759'>✅ Programa desinstalado com sucesso!</span>\n"
                "<span font='9.5' color='#2c3e50'>Todos os serviços e atalhos foram removidos do seu sistema.\n"
                "Apenas o pacote de instalação baixado foi preservado.</span>"
            )
            for child in self.btn_card_box.get_children():
                self.btn_card_box.remove(child)

            btn_close_done = Gtk.Button(label="Fechar")
            btn_close_done.get_style_context().add_class("btn-pill")
            btn_close_done.connect("clicked", lambda w: Gtk.main_quit())
            self.btn_card_box.pack_start(btn_close_done, False, False, 0)
            self._show_overlay()

            GLib.timeout_add(2500, lambda: Gtk.main_quit() or False)

        except Exception as e:
            print("Erro ao desinstalar:", e)

    def _reactivate_system(self, _):
        """Reativa o serviço no sistema e acende o teclado."""
        try:
            if os.path.exists(DISABLED_MARKER):
                try:
                    os.remove(DISABLED_MARKER)
                except Exception:
                    run_sudo(f"rm -f '{DISABLED_MARKER}'")

            self.is_service_disabled = False
            self.cfg["mode"] = "solid_on"
            save_config(self.cfg)
            run_sudo("systemctl daemon-reload && systemctl enable --now scrolllock.service")

            self._hide_overlay()
            self._update_button_styles()
        except Exception as e:
            print("Erro ao reativar serviço:", e)

    def _on_exit_clicked(self, _):
        """Desativa totalmente o serviço e fecha."""
        try:
            run_sudo(f"mkdir -p '{CONFIG_DIR}' && chmod 777 '{CONFIG_DIR}'")
            with open(DISABLED_MARKER, "w") as f:
                f.write("1\n")
            try:
                os.chmod(DISABLED_MARKER, 0o666)
            except Exception:
                pass

            self.cfg["mode"] = "solid_off"
            save_config(self.cfg)

            for p in glob.glob("/sys/class/leds/*::scrolllock/brightness"):
                try:
                    with open(p, "w") as f:
                        f.write("0\n")
                except Exception:
                    pass

            run_sudo("systemctl stop scrolllock.service || true")
        except Exception as e:
            print("Erro ao desativar serviço:", e)

        Gtk.main_quit()

_app_lock_file = None

def check_single_instance():
    """Tenta contatar uma instância já em execução. Se existir, traz-a para frente e encerra esta."""
    # 1. Tenta falar com socket existente
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(0.5)
        s.connect(SOCKET_FILE)
        is_installer = "--installer" in sys.argv or "--app" not in sys.argv
        msg = b"ACTIVATE_INSTALLER\n" if is_installer else b"ACTIVATE\n"
        s.sendall(msg)
        s.close()
        try:
            from gi.repository import Gdk
            Gdk.notify_startup_complete()
        except Exception:
            pass
        return True
    except Exception:
        pass

    # 2. Adquire lock exclusivo de arquivo para impedir concorrência em cliques rápidos
    global _app_lock_file
    try:
        _app_lock_file = open(LOCK_FILE, "w")
        fcntl.flock(_app_lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (IOError, BlockingIOError):
        time.sleep(0.3)
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(0.5)
            s.connect(SOCKET_FILE)
            is_installer = "--installer" in sys.argv or "--app" not in sys.argv
            msg = b"ACTIVATE_INSTALLER\n" if is_installer else b"ACTIVATE\n"
            s.sendall(msg)
            s.close()
            try:
                from gi.repository import Gdk
                Gdk.notify_startup_complete()
            except Exception:
                pass
        except Exception:
            pass
        return True

    return False

def main():
    if check_single_instance():
        print("Uma instância do MultKeyboard v1.0 já está em execução. Trazendo janela para o centro e à frente.")
        sys.exit(0)

    win = AppleLedPanel()
    win.connect("destroy", Gtk.main_quit)
    Gtk.main()

if __name__ == "__main__":
    main()
