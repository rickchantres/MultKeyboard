#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <errno.h>

#include "embedded_gui.h"
#include "embedded_daemon.h"
#include "embedded_icon.h"

static int write_embedded_file(const char *path, const unsigned char *data, unsigned int len, mode_t mode) {
    FILE *fp = fopen(path, "wb");
    if (!fp) {
        fprintf(stderr, "[MultKeyboard] Erro ao criar arquivo %s: %s\n", path, strerror(errno));
        return -1;
    }
    size_t written = fwrite(data, 1, len, fp);
    fclose(fp);
    chmod(path, mode);
    return (written == len) ? 0 : -1;
}

int main(int argc, char *argv[]) {
    const char *target_dir = "/tmp/multkeyboard_assets";
    mkdir(target_dir, 0755);

    char gui_path[256];
    char daemon_path[256];
    char icon_path[256];

    snprintf(gui_path, sizeof(gui_path), "%s/painel_led_desktop.py", target_dir);
    snprintf(daemon_path, sizeof(daemon_path), "%s/scrolllock-daemon.py", target_dir);
    snprintf(icon_path, sizeof(icon_path), "%s/scrolllock-rgb.png", target_dir);

    write_embedded_file(gui_path, painel_led_desktop_py, painel_led_desktop_py_len, 0755);
    write_embedded_file(daemon_path, scrolllock_daemon_py, scrolllock_daemon_py_len, 0755);
    write_embedded_file(icon_path, scrolllock_rgb_png, scrolllock_rgb_png_len, 0644);

    // Constrói lista de argumentos para o python3 passando explicitamente --installer
    int total_args = argc + 3;
    char **py_argv = (char **)malloc((total_args + 1) * sizeof(char *));
    if (!py_argv) {
        return 1;
    }

    py_argv[0] = "/usr/bin/python3";
    py_argv[1] = gui_path;
    py_argv[2] = "--installer";

    for (int i = 1; i < argc; i++) {
        py_argv[i + 2] = argv[i];
    }
    py_argv[argc + 2] = NULL;

    // Executa python3
    execv("/usr/bin/python3", py_argv);

    // Fallback se /usr/bin/python3 falhar
    execvp("python3", py_argv);

    // Se ambos falharem
    fprintf(stderr, "[MultKeyboard] Falha ao iniciar python3: %s\n", strerror(errno));
    system("zenity --error --title='MultKeyboard v1.0' --text='Não foi possível encontrar o Python 3 nativo no sistema.' 2>/dev/null");
    return 1;
}
