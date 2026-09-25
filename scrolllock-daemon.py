#!/usr/bin/env python3
"""
Scroll Lock Master Daemon with RGB Gaming Keyboard Hotkeys:
- Persists state in /var/lib/scrolllock/config.json across reboots.
- Hotkey combos:
    * Hold [Scroll Lock] + press [+]:
        - If OFF -> turns ON and starts blinking.
        - If already blinking -> accelerates blink speed (down to 30ms).
    * Hold [Scroll Lock] + press [-]:
        - If blinking -> decelerates blink speed (up to 1000ms).
        - If at minimum speed (slowest) -> pressing [-] again turns LED OFF.
    * Tap [Scroll Lock] alone (without +/-):
        - If blinking -> stops blinking and turns OFF.
        - If solid ON -> turns OFF.
        - If solid OFF -> turns ON.
- Full hotplug and sysfs trigger:none management.
"""

import os
import sys
import glob
import time
import json
import struct
import select
import logging
import threading
import signal
import socket
import subprocess

CONFIG_FILE = "/var/lib/scrolllock/config.json"
SAFE_MIN_MS = 25

# Speed steps in ms (slowest to fastest)
SPEED_STEPS = [1000, 750, 500, 350, 250, 180, 120, 80, 50, 30]

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

EV_KEY = 0x01
EV_LED = 0x11
KEY_SCROLLLOCK = 70
KEY_MINUS = 12
KEY_EQUAL = 13       # '+' on standard layout
KEY_KPMINUS = 74     # Numeric keypad '-'
KEY_KPPLUS = 78      # Numeric keypad '+'
KEY_SPACE = 57       # Barra de Espaço (recomendado - zero conflitos com busca no Desktop/DING)
KEY_F12 = 88         # F12 (atalho alternativo)
KEY_M = 50           # 'M' mantido como opção adicional

PLUS_KEYS = {KEY_EQUAL, KEY_KPPLUS}
MINUS_KEYS = {KEY_MINUS, KEY_KPMINUS}
GUI_TOGGLE_KEYS = {KEY_SPACE, KEY_F12}

LED_SCROLLL = 0x02
EVENT_FORMAT = "qqHHi"
EVENT_SIZE = struct.calcsize(EVENT_FORMAT)

config_lock = threading.Lock()
current_config = {
    "mode": "solid_on",   # 'blink', 'solid_on', 'solid_off'
    "on_ms": 150,
    "off_ms": 150,
    "last_mtime": 0
}

def load_config():
    global current_config
    if os.path.exists(CONFIG_FILE):
        try:
            mtime = os.path.getmtime(CONFIG_FILE)
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
            with config_lock:
                current_config["mode"] = data.get("mode", "solid_on")
                current_config["on_ms"] = max(SAFE_MIN_MS, int(data.get("on_ms", 150)))
                current_config["off_ms"] = max(SAFE_MIN_MS, int(data.get("off_ms", 150)))
                current_config["last_mtime"] = mtime
            logging.info(f"Loaded config: mode={current_config['mode']}, on={current_config['on_ms']}ms, off={current_config['off_ms']}ms")
            return
        except Exception as e:
            logging.warning(f"Error loading {CONFIG_FILE}: {e}")

    save_config("solid_on", 150, 150)

def save_config(mode, on_ms, off_ms):
    global current_config
    data = {
        "mode": mode,
        "on_ms": max(SAFE_MIN_MS, int(on_ms)),
        "off_ms": max(SAFE_MIN_MS, int(off_ms))
    }
    try:
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        tmp = CONFIG_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2)
        try:
            os.chmod(tmp, 0o666)
        except Exception:
            pass
        os.replace(tmp, CONFIG_FILE)
        with config_lock:
            current_config["mode"] = data["mode"]
            current_config["on_ms"] = data["on_ms"]
            current_config["off_ms"] = data["off_ms"]
            current_config["last_mtime"] = os.path.getmtime(CONFIG_FILE)
    except Exception as e:
        logging.warning(f"Error saving {CONFIG_FILE}: {e}")

def discover_leds():
    leds = []
    for led_dir in glob.glob("/sys/class/leds/*::scrolllock"):
        events = glob.glob(os.path.join(led_dir, "device", "event*"))
        ev_path = f"/dev/input/{os.path.basename(events[0])}" if events else None
        leds.append({
            "dir": led_dir,
            "trigger": os.path.join(led_dir, "trigger"),
            "brightness": os.path.join(led_dir, "brightness"),
            "event": ev_path
        })
    return leds

def set_led_hardware(leds, val):
    for led in leds:
        trig = led.get("trigger")
        if trig and os.path.exists(trig):
            try:
                with open(trig, "w") as f:
                    f.write("none\n")
            except Exception:
                pass

        br = led.get("brightness")
        if br and os.path.exists(br):
            try:
                with open(br, "w") as f:
                    f.write(f"{val}\n")
            except Exception:
                pass

        ev = led.get("event")
        if ev and os.path.exists(ev):
            try:
                fd = os.open(ev, os.O_WRONLY | os.O_NONBLOCK)
                packet = struct.pack(EVENT_FORMAT, 0, 0, EV_LED, LED_SCROLLL, val)
                os.write(fd, packet)
                os.close(fd)
            except Exception:
                pass

def interruptible_sleep(duration):
    end_time = time.time() + duration
    while time.time() < end_time:
        time.sleep(0.01)
        try:
            if os.path.exists(CONFIG_FILE):
                mt = os.path.getmtime(CONFIG_FILE)
                if mt > current_config.get("last_mtime", 0):
                    load_config()
                    return True
        except Exception:
            pass
    return False

def led_blinker_worker():
    logging.info("LED Hardware Worker started.")
    leds = discover_leds()
    last_dev_check = time.time()

    current_led_state = 0
    phase_start_time = time.time()
    last_hardware_state = -1

    while True:
        try:
            now = time.time()
            if now - last_dev_check > 3.0:
                leds = discover_leds()
                last_dev_check = now

            if os.path.exists(CONFIG_FILE):
                try:
                    mt = os.path.getmtime(CONFIG_FILE)
                    if mt > current_config.get("last_mtime", 0):
                        load_config()
                except Exception:
                    pass

            with config_lock:
                mode = current_config["mode"]
                on_s = current_config["on_ms"] / 1000.0
                off_s = current_config["off_ms"] / 1000.0

            if mode == "solid_on":
                if last_hardware_state != 1:
                    set_led_hardware(leds, 1)
                    last_hardware_state = 1
                current_led_state = 1
                phase_start_time = now
                time.sleep(0.015)

            elif mode == "solid_off":
                if last_hardware_state != 0:
                    set_led_hardware(leds, 0)
                    last_hardware_state = 0
                current_led_state = 0
                phase_start_time = now
                time.sleep(0.015)

            elif mode == "blink":
                elapsed = now - phase_start_time
                target_duration = on_s if current_led_state == 1 else off_s

                # Se atingiu o tempo configurado (ou se o usuário acelerou o slider e o tempo expirou)
                if elapsed >= target_duration:
                    current_led_state = 0 if current_led_state == 1 else 1
                    phase_start_time = now
                    set_led_hardware(leds, current_led_state)
                    last_hardware_state = current_led_state
                else:
                    if last_hardware_state != current_led_state:
                        set_led_hardware(leds, current_led_state)
                        last_hardware_state = current_led_state

                # Ciclo de 3ms permite transição ultra-suave e resposta imediata ao arrastar
                time.sleep(0.003)

        except Exception as e:
            logging.error(f"Error in blinker worker: {e}")
            time.sleep(0.05)

def find_nearest_step_idx(current_ms):
    # Encontra o índice mais próximo em SPEED_STEPS (0 = mais lento, len-1 = mais rápido)
    best_idx = 0
    min_diff = abs(SPEED_STEPS[0] - current_ms)
    for idx, s in enumerate(SPEED_STEPS):
        diff = abs(s - current_ms)
        if diff < min_diff:
            min_diff = diff
            best_idx = idx
    return best_idx

def keyboard_listener_worker():
    logging.info("Keyboard Hotkey Listener Worker started.")
    input_fds = {}
    last_scan = 0

    scrolllock_held = False
    combo_used = False

    while True:
        try:
            now = time.time()
            if now - last_scan > 3.0:
                for ev_path in glob.glob("/dev/input/event*"):
                    if ev_path not in input_fds:
                        try:
                            fd = os.open(ev_path, os.O_RDONLY | os.O_NONBLOCK)
                            input_fds[ev_path] = fd
                        except Exception:
                            pass
                last_scan = now

            fd_to_path = {fd: path for path, fd in input_fds.items()}
            if not fd_to_path:
                time.sleep(1.0)
                continue

            r, _, _ = select.select(list(fd_to_path.keys()), [], [], 2.0)

            for fd in r:
                path = fd_to_path.get(fd)
                try:
                    data = os.read(fd, EVENT_SIZE * 32)
                except (OSError, IOError):
                    if path in input_fds:
                        del input_fds[path]
                    try:
                        os.close(fd)
                    except Exception:
                        pass
                    continue

                for i in range(0, len(data) - EVENT_SIZE + 1, EVENT_SIZE):
                    chunk = data[i : i + EVENT_SIZE]
                    sec, usec, ev_type, ev_code, ev_val = struct.unpack(EVENT_FORMAT, chunk)

                    if ev_type != EV_KEY:
                        continue

                    # 1. SCROLL LOCK KEY DOWN
                    if ev_code == KEY_SCROLLLOCK:
                        if ev_val == 1:
                            scrolllock_held = True
                            combo_used = False
                        elif ev_val == 0:
                            # SCROLL LOCK KEY UP: se soltou sem pressionar + ou -, faz o toggle padrão!
                            if scrolllock_held and not combo_used:
                                with config_lock:
                                    cur_mode = current_config["mode"]
                                    on_ms = current_config["on_ms"]
                                    off_ms = current_config["off_ms"]

                                if cur_mode == "blink":
                                    new_mode = "solid_off"
                                    logging.info("Scroll Lock sozinho solto: Parou pisca -> desligado")
                                elif cur_mode == "solid_on":
                                    new_mode = "solid_off"
                                    logging.info("Scroll Lock sozinho solto: Alternou para DESLIGADO")
                                else:
                                    new_mode = "solid_on"
                                    logging.info("Scroll Lock sozinho solto: Alternou para LIGADO")

                                save_config(new_mode, on_ms, off_ms)
                                set_led_hardware(discover_leds(), 1 if new_mode == "solid_on" else 0)

                            scrolllock_held = False
                            combo_used = False

                    # 2. SE SCROLL LOCK ESTIVER PRESSIONADO E APERTAR [+]
                    elif scrolllock_held and ev_code in PLUS_KEYS and ev_val == 1:
                        combo_used = True
                        with config_lock:
                            cur_mode = current_config["mode"]
                            cur_ms = current_config["on_ms"]

                        idx = find_nearest_step_idx(cur_ms)

                        if cur_mode == "solid_off" or cur_mode == "solid_on":
                            # "se o scroll lock estiver desligado ele deve ligar ao apertar scroll lock e a tecla +, e começar a piscar"
                            new_mode = "blink"
                            new_ms = SPEED_STEPS[2] if cur_mode == "solid_off" else SPEED_STEPS[min(len(SPEED_STEPS)-1, idx+1)]
                            logging.info(f"Combo [ScrollLock + (+)]: Iniciando pisca a {new_ms}ms")
                        else:
                            # Já está piscando -> acelera (avança para índice maior / ms menor)
                            new_mode = "blink"
                            if idx < len(SPEED_STEPS) - 1:
                                idx += 1
                            new_ms = SPEED_STEPS[idx]
                            logging.info(f"Combo [ScrollLock + (+)]: Acelerando pisca para {new_ms}ms")

                        save_config(new_mode, new_ms, new_ms)

                    # 3. SE SCROLL LOCK ESTIVER PRESSIONADO E APERTAR [-]
                    elif scrolllock_held and ev_code in MINUS_KEYS and ev_val == 1:
                        combo_used = True
                        with config_lock:
                            cur_mode = current_config["mode"]
                            cur_ms = current_config["on_ms"]

                        idx = find_nearest_step_idx(cur_ms)

                        if cur_mode == "blink":
                            if idx > 0:
                                # Desacelera (avança para índice menor / ms maior)
                                idx -= 1
                                new_ms = SPEED_STEPS[idx]
                                new_mode = "blink"
                                logging.info(f"Combo [ScrollLock + (-)]: Desacelerando pisca para {new_ms}ms")
                                save_config(new_mode, new_ms, new_ms)
                            else:
                                # "ao apertar scroll lock com a tecla - novamente ele deve apagar"
                                new_mode = "solid_off"
                                logging.info("Combo [ScrollLock + (-)]: Chegou no limite mínimo -> APAGANDO")
                                save_config(new_mode, SPEED_STEPS[0], SPEED_STEPS[0])
                                set_led_hardware(discover_leds(), 0)
                        elif cur_mode == "solid_on":
                            new_mode = "solid_off"
                            logging.info("Combo [ScrollLock + (-)]: Apagando luz estática")
                            save_config(new_mode, cur_ms, cur_ms)
                            set_led_hardware(discover_leds(), 0)

                    # 4. SE SCROLL LOCK ESTIVER PRESSIONADO E APERTAR [ESPAÇO], [F12] OU [M]
                    elif scrolllock_held and (ev_code in GUI_TOGGLE_KEYS or ev_code == KEY_M) and ev_val == 1:
                        combo_used = True
                        key_name = "Espaço" if ev_code == KEY_SPACE else ("F12" if ev_code == KEY_F12 else "M")
                        logging.info(f"Combo [ScrollLock + {key_name}]: Alternando interface grafica...")
                        contacted = False
                        sock_path = "/tmp/multkeyboard_1000.sock"
                        try:
                            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                            s.settimeout(0.5)
                            s.connect(sock_path)
                            s.sendall(b"TOGGLE_HOTKEY\n")
                            s.close()
                            contacted = True
                            logging.info("Enviado TOGGLE_HOTKEY com sucesso para a janela existente.")
                        except Exception as err:
                            logging.info(f"Socket contact info: {err}")

                        if not contacted:
                            logging.info("Nenhuma janela aberta, iniciando aplicacao...")
                            subprocess.Popen(
                                "su rick -c 'env XDG_RUNTIME_DIR=/run/user/1000 DISPLAY=:0 WAYLAND_DISPLAY=wayland-0 /usr/bin/python3 /usr/local/bin/painel_led_desktop.py --app &'",
                                shell=True
                            )

        except Exception as e:
            logging.error(f"Error in keyboard listener: {e}")
            time.sleep(1.0)

def main():
    logging.info("Starting Scroll Lock Master Daemon with Combos...")
    load_config()

    t_led = threading.Thread(target=led_blinker_worker, daemon=True)
    t_led.start()

    t_kbd = threading.Thread(target=keyboard_listener_worker, daemon=True)
    t_kbd.start()

    while True:
        time.sleep(3600)

if __name__ == "__main__":
    main()
