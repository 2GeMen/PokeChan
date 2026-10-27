/*
 * StackChan bridge: the parts of the Muse SDK the chat session expects from
 * the rest of a Muse gadget (settings, Wi-Fi, Link, the screen), backed by
 * StackChan's own Wi-Fi and a small NVS namespace.
 *
 * Values are cached in RAM: the session task runs on a PSRAM stack and must
 * not touch flash, so only the setters (on the console task) write NVS.
 */

#include <string.h>

#include "esp_log.h"
#include "esp_timer.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "nvs.h"

#include "muse_chat.h"
#include "muse_link.h"
#include "muse_settings.h"
#include "muse_state.h"
#include "muse_wifi.h"

static const char *TAG = "muse_shim";

#define NVS_NS "muse_hatch"
#define DEFAULT_HOST "hatch.metaaivm.com"

static portMUX_TYPE s_lock = portMUX_INITIALIZER_UNLOCKED;
static char s_host[MUSE_HOST_MAX + 1] = DEFAULT_HOST;
static char s_vm[MUSE_VM_MAX + 1];
static char s_token[MUSE_TOKEN_MAX + 1];

#define LOCKED(stmt)                 \
    do {                             \
        portENTER_CRITICAL(&s_lock); \
        stmt;                        \
        portEXIT_CRITICAL(&s_lock);  \
    } while (0)

static void load_str(nvs_handle_t h, const char *key, char *out, size_t cap)
{
    size_t len = cap;
    if (nvs_get_str(h, key, out, &len) != ESP_OK) {
        out[0] = '\0';
    }
}

static void save_str(const char *key, const char *value)
{
    nvs_handle_t h;
    if (nvs_open(NVS_NS, NVS_READWRITE, &h) != ESP_OK) {
        ESP_LOGE(TAG, "can't open NVS to save %s", key);
        return;
    }
    if (nvs_set_str(h, key, value) != ESP_OK || nvs_commit(h) != ESP_OK) {
        ESP_LOGE(TAG, "can't save %s", key);
    }
    nvs_close(h);
}

void muse_bridge_settings_load(void)
{
    nvs_handle_t h;
    if (nvs_open(NVS_NS, NVS_READONLY, &h) != ESP_OK) {
        return;   /* nothing saved yet */
    }
    load_str(h, "host", s_host, sizeof(s_host));
    if (!s_host[0]) {
        strlcpy(s_host, DEFAULT_HOST, sizeof(s_host));
    }
    load_str(h, "vm", s_vm, sizeof(s_vm));
    load_str(h, "token", s_token, sizeof(s_token));
    nvs_close(h);
}

/* ---- muse_settings.h ---- */

void muse_settings_hatch_host(char out[MUSE_HOST_MAX + 1])
{
    LOCKED(strlcpy(out, s_host, MUSE_HOST_MAX + 1));
}

void muse_settings_hatch_vm(char out[MUSE_VM_MAX + 1])
{
    LOCKED(strlcpy(out, s_vm, MUSE_VM_MAX + 1));
}

void muse_settings_hatch_token(char out[MUSE_TOKEN_MAX + 1])
{
    LOCKED(strlcpy(out, s_token, MUSE_TOKEN_MAX + 1));
}

size_t muse_settings_hatch_token_len(void)
{
    size_t n;
    LOCKED(n = strlen(s_token));
    return n;
}

void muse_settings_set_hatch_vm(const char *vm)
{
    LOCKED(strlcpy(s_vm, vm ? vm : "", sizeof(s_vm)));
    save_str("vm", vm ? vm : "");
    muse_hatch_config_changed();
}

esp_err_t muse_settings_set_hatch_token(const char *token, bool append)
{
    esp_err_t err = ESP_OK;
    LOCKED({
        size_t have = append ? strlen(s_token) : 0;
        size_t add = strlen(token ? token : "");
        if (have + add > MUSE_TOKEN_MAX) {
            err = ESP_ERR_INVALID_SIZE;
        } else {
            memcpy(s_token + have, token, add);
            s_token[have + add] = '\0';
        }
    });
    if (err == ESP_OK) {
        static char copy[MUSE_TOKEN_MAX + 1];   /* NVS writes it from here, unlocked */
        LOCKED(strlcpy(copy, s_token, sizeof(copy)));
        save_str("token", copy);
        memset(copy, 0, sizeof(copy));
        muse_hatch_config_changed();
    }
    return err;
}

/* ---- muse_wifi.h ---- */

/* Before this, xiaozhi is still starting up (its wake word task among others)
 * and needs the internal RAM a Muse connection would take. */
#define MUSE_START_AFTER_US (25 * 1000000LL)

bool muse_wifi_connected(void)
{
    wifi_ap_record_t ap;
    return esp_timer_get_time() >= MUSE_START_AFTER_US && esp_wifi_sta_get_ap_info(&ap) == ESP_OK;
}

void muse_wifi_nap(bool nap)
{
    (void)nap;   /* StackChan's Wi-Fi stays up; xiaozhi needs it */
}

/* ---- muse_link.h: no Home Link here, so the session uses its own token ---- */

bool muse_link_hatch_linked(void)
{
    return false;
}

bool muse_link_hatch_vm(const char *want_vm, char *vm_id, size_t id_cap, char *vm_name, size_t name_cap,
                        char **vm_token)
{
    (void)want_vm, (void)vm_id, (void)id_cap, (void)vm_name, (void)name_cap;
    *vm_token = NULL;
    return false;
}

/* ---- muse_state.h ---- */

void muse_state_page(bool cjk, int *cols, int *lines)
{
    /* Only shapes the caption pages the chat code makes; the serial console
     * gets the whole reply regardless. */
    *cols = cjk ? 16 : 32;
    *lines = 6;
}
