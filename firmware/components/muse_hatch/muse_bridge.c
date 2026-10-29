/*
 * StackChan <-> Muse bridge: start-up and the serial console (see muse_bridge.h).
 */

#include "muse_bridge.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "driver/usb_serial_jtag.h"
#include "driver/usb_serial_jtag_vfs.h"
#include "esp_attr.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#include "muse_chat.h"
#include "muse_settings.h"

static const char *TAG = "muse_bridge";

void muse_bridge_settings_load(void);   /* muse_hatch_shim.c */

#define LINE_MAX 1024              /* chat.py sends pieces well under this */
#define CHAT_MAX (64 * 1024)       /* a typed message, assembled from "chat+=" lines */
#define RESULT_MAX 3072            /* a brief or answer, as muse_ask.c keeps them */

void muse_bridge_ask_start(void);       /* muse_ask.c */

static char *s_chat;
static size_t s_chat_len;

static void chat_line(char *piece, bool last, bool whole)
{
    size_t n = muse_hatch_unescape(piece);
    if (!s_chat) {
        s_chat = heap_caps_malloc(CHAT_MAX, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
        s_chat_len = 0;
    }
    const char *err = !whole ? "LINE TOO LONG" : !s_chat ? "OUT OF MEMORY" : s_chat_len + n >= CHAT_MAX ? "TOO LONG" : NULL;
    if (err) {
        free(s_chat);
        s_chat = NULL;
        muse_hatch_console("error", err, NULL);
        return;
    }
    memcpy(s_chat + s_chat_len, piece, n);
    s_chat_len += n;
    s_chat[s_chat_len] = '\0';
    muse_hatch_console("ack", NULL, "\"bytes\":%u", (unsigned)s_chat_len);
    if (last) {
        muse_hatch_text_turn(s_chat);   /* frees it */
        s_chat = NULL;
    }
}

static void print_status(void)
{
    muse_hatch_status_t st;
    muse_hatch_status(&st);
    char vm[MUSE_VM_MAX + 1];
    muse_settings_hatch_vm(vm);
    printf("@status {\"board\":\"StackChan\",\"chat\":true,\"device\":{\"hatch\":{\"state\":\"%s\","
           "\"detail\":\"%s\",\"vm\":\"%s\",\"want_vm\":\"%s\",\"token\":%s}}}\n",
           muse_hatch_state_name(st.state), st.detail, st.vm_id, vm,
           muse_settings_hatch_token_len() ? "true" : "false");
    fflush(stdout);
}

/* "@brief AGE TEXT" or "@answer AGE QUESTION || TEXT", on one line (AGE in s, -1: none yet). */
static void print_result(bool brief)
{
    char *text = heap_caps_malloc(RESULT_MAX, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    char question[256];
    if (!text) {
        return;
    }
    int age = brief ? muse_bridge_brief(text, RESULT_MAX, false)
                    : muse_bridge_last_answer(question, sizeof(question), text, RESULT_MAX);
    for (char *p = text; *p; p++) {
        if (*p == '\n' || *p == '\r') {
            *p = ' ';
        }
    }
    if (brief) {
        printf("@brief %d %s\n", age, text);
    } else {
        printf("@answer %d %s || %s\n", age, question, text);
    }
    fflush(stdout);
    free(text);
}

static muse_bridge_command_cb_t s_command_cb;

void muse_bridge_set_command_cb(muse_bridge_command_cb_t cb)
{
    s_command_cb = cb;
}

static void command(char *line, bool whole)
{
    if (!strcmp(line, "status")) {
        print_status();
    } else if (!strcmp(line, "chat.cancel")) {
        free(s_chat);
        s_chat = NULL;
        muse_hatch_text_cancel();
    } else if (!strncmp(line, "chat=", 5) || !strncmp(line, "chat+=", 6)) {
        bool last = line[4] == '=';
        chat_line(line + (last ? 5 : 6), last, whole);
    } else if (!strncmp(line, "hatch.token=", 12) || !strncmp(line, "hatch.token+=", 13)) {
        bool append = line[11] == '+';
        /* Never echo the token. */
        bool ok = whole && muse_settings_set_hatch_token(line + (append ? 13 : 12), append) == ESP_OK;
        printf("@hatch.token %s %u\n", ok ? "ok" : "error", (unsigned)muse_settings_hatch_token_len());
        fflush(stdout);
    } else if (!strncmp(line, "hatch.vm=", 9)) {
        muse_settings_set_hatch_vm(line + 9);
        printf("@hatch.vm ok\n");
        fflush(stdout);
    } else if (!strncmp(line, "ask=", 4)) {
        muse_hatch_unescape(line + 4);
        printf("@ask %s\n", muse_bridge_ask(line + 4) ? "queued" : "error");
        fflush(stdout);
    } else if (!strcmp(line, "brief=refresh")) {
        muse_bridge_refresh_brief(true);
        printf("@brief refreshing\n");
        fflush(stdout);
    } else if (!strcmp(line, "brief") || !strcmp(line, "answer")) {
        print_result(!strcmp(line, "brief"));
    } else if (s_command_cb && s_command_cb(line)) {
        /* handled by the app */
    } else {
        printf("@error unknown command\n");
        fflush(stdout);
    }
}

static void console_task(void *arg)
{
    (void)arg;
    EXT_RAM_BSS_ATTR static char line[LINE_MAX];
    size_t len = 0;
    bool in_cmd = false, whole = true;
    for (;;) {
        uint8_t c;
        if (usb_serial_jtag_read_bytes(&c, 1, portMAX_DELAY) != 1) {
            continue;
        }
        if (c == '\r') {
            continue;
        }
        if (c == '\n') {
            if (in_cmd) {
                line[len] = '\0';
                command(line, whole);
                memset(line, 0, len);   /* tokens pass through here */
            }
            len = 0;
            in_cmd = false;
            whole = true;
            continue;
        }
        if (!in_cmd) {
            in_cmd = len == 0 && c == '>';   /* only '>' lines are commands */
            continue;
        }
        if (len + 1 < sizeof(line)) {
            line[len++] = (char)c;
        } else {
            whole = false;
        }
    }
}

void muse_bridge_start(void)
{
    muse_bridge_settings_load();
    muse_hatch_start();
    muse_bridge_ask_start();

    usb_serial_jtag_driver_config_t cfg = USB_SERIAL_JTAG_DRIVER_CONFIG_DEFAULT();
    cfg.rx_buffer_size = 2048;
    if (usb_serial_jtag_driver_install(&cfg) != ESP_OK) {
        ESP_LOGE(TAG, "no USB serial: chat over serial is off");
        return;
    }
    /* stdout shares the driver's TX ring with console writes. */
    usb_serial_jtag_vfs_use_driver();
    /* Internal-RAM stack: the setters write NVS. */
    if (xTaskCreate(console_task, "muse_console", 4096, NULL, 4, NULL) != pdPASS) {
        ESP_LOGE(TAG, "console task failed");
    }
    ESP_LOGI(TAG, "started; token %s", muse_settings_hatch_token_len() ? "set" : "not set");
}
