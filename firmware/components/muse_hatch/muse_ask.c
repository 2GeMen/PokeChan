/*
 * StackChan bridge: questions for Muse from the rest of the firmware.
 *
 * Muse answers in 10-60 s (longer when it looks at the calendar or mail), far
 * too long to hold xiaozhi's main thread, so questions are asked here, one at a
 * time, on a task of their own: muse_bridge_ask() queues one and returns, and
 * the answer goes to the callback when it comes. The same task asks once a
 * day for a brief of the user's day (calendar and important mail), so the
 * common question can be answered at once from it. Every brief is a message in
 * the user's Muse chat, so it is asked no more than that, and kept in NVS so a
 * reboot doesn't ask again.
 *
 * Replies are collected from muse_hatch_console, which the chat session calls
 * for every piece of a typed turn.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/idf_additions.h"
#include "freertos/queue.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "nvs.h"

#include "muse_bridge.h"
#include "muse_chat.h"

static const char *TAG = "muse_ask";

#define ANSWER_MAX 3072
#define QUESTION_MAX 512
#define TURN_TIMEOUT_MS (6 * 60 * 1000)         /* the session gives up after 5 min */
#define BRIEF_HOUR 6                            /* local time: the day's brief is asked after this */
#define BRIEF_TRIES 3                           /* briefs asked a day at most, failed ones included */
#define BRIEF_RETRY_US (15 * 60 * 1000000LL)
#define CLOCK_VALID 1735689600                  /* 2025-01-01: before this the clock isn't set yet */
#define NVS_NS "muse_hatch"                     /* shared with muse_hatch_shim.c */

#define BRIEF_PROMPT                                                                         \
    "请用简短自然的中文口语，总结我今天和明天日历上的安排，再提一下过去一天里需要我注意的" \
    "重要邮件（最多三封，没有就说没有）。总共不超过150字，不要用列表、编号或Markdown，"     \
    "像朋友聊天一样说。"
#define ASK_SUFFIX                                                                     \
    "\n\n（这是我通过桌面机器人 StackChan 用语音问的。请用简短自然的中文口语回答，" \
    "不超过120字，不要用列表、编号或Markdown。）"

typedef enum { JOB_ASK, JOB_BRIEF, JOB_BRIEF_FORCE } job_kind_t;

typedef struct {
    job_kind_t kind;
    char *text;   /* JOB_ASK: the question, malloc'd */
} job_t;

static QueueHandle_t s_jobs;
static SemaphoreHandle_t s_turn_done;
static SemaphoreHandle_t s_mutex;   /* guards the results */
static muse_bridge_answer_cb_t s_answer_cb;

/* The turn being collected (only one at a time). */
static volatile bool s_collecting;
static bool s_turn_ok;
static char *s_turn_text;
static size_t s_turn_len;

/* Results, guarded by s_mutex. */
static char *s_answer, *s_question, *s_brief;
static int64_t s_answer_us;
static time_t s_brief_at;   /* wall clock, 0: none */
static volatile bool s_busy;

/* Today's briefs so far, on the ask task. */
static int s_tries_day, s_tries;
static int64_t s_retry_us;

/* Saves the brief: on the esp_timer task, since writing flash disables the
 * cache and this task's stack is in PSRAM. */
static esp_timer_handle_t s_save_timer;

/* The clock is only trusted once SNTP has set it (see muse_bridge_clock_synced). */
static volatile bool s_clock_synced;

static int64_t now_us(void)
{
    return esp_timer_get_time();
}

static void append(const char *text)
{
    size_t n = strlen(text);
    if (s_turn_len + n >= ANSWER_MAX) {
        n = ANSWER_MAX - 1 - s_turn_len;
    }
    memcpy(s_turn_text + s_turn_len, text, n);
    s_turn_len += n;
    s_turn_text[s_turn_len] = '\0';
}

/* On the chat session's task: keep it short. */
static void on_console(const char *type, const char *text)
{
    if (!s_collecting) {
        return;
    }
    if (!strcmp(type, "text") && text) {
        append(text);
    } else if (!strcmp(type, "message_done")) {
        if (s_turn_len && s_turn_text[s_turn_len - 1] != '\n') {
            append("\n");
        }
    } else if (!strcmp(type, "done") || !strcmp(type, "error")) {
        s_turn_ok = !strcmp(type, "done") && s_turn_len > 0;
        if (!strcmp(type, "error")) {
            s_turn_len = 0;
            append(text ? text : "error");
        }
        s_collecting = false;
        xSemaphoreGive(s_turn_done);
    }
}

/* Runs one typed turn and leaves its reply in s_turn_text. */
static bool run_turn(const char *prompt)
{
    if (!muse_hatch_ready()) {
        s_turn_len = 0;
        append("Muse 还没连上");
        return false;
    }
    size_t n = strlen(prompt) + 1;
    char *copy = heap_caps_malloc(n, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    if (!copy) {
        return false;
    }
    memcpy(copy, prompt, n);
    xSemaphoreTake(s_turn_done, 0);
    s_turn_len = 0;
    s_turn_text[0] = '\0';
    s_turn_ok = false;
    s_collecting = true;
    int64_t t0 = now_us();
    muse_hatch_text_turn(copy);   /* frees it */
    if (xSemaphoreTake(s_turn_done, pdMS_TO_TICKS(TURN_TIMEOUT_MS)) != pdTRUE) {
        s_collecting = false;
        muse_hatch_text_cancel();
        s_turn_len = 0;
        append("Muse 没有回应");
        return false;
    }
    while (s_turn_len && (s_turn_text[s_turn_len - 1] == '\n' || s_turn_text[s_turn_len - 1] == ' ')) {
        s_turn_text[--s_turn_len] = '\0';
    }
    ESP_LOGI(TAG, "turn %s in %d ms, %u bytes", s_turn_ok ? "done" : "failed", (int)((now_us() - t0) / 1000),
             (unsigned)s_turn_len);
    return s_turn_ok;
}

static void store(char **slot, const char *text)
{
    xSemaphoreTake(s_mutex, portMAX_DELAY);
    strlcpy(*slot, text, ANSWER_MAX);
    xSemaphoreGive(s_mutex);
}

/* The local day of `t` as yyyymmdd, or 0 while the clock isn't set. */
static int local_day(time_t t, int *hour)
{
    if (!s_clock_synced || t < CLOCK_VALID) {
        return 0;
    }
    struct tm tm;
    localtime_r(&t, &tm);
    if (hour) {
        *hour = tm.tm_hour;
    }
    return (tm.tm_year + 1900) * 10000 + (tm.tm_mon + 1) * 100 + tm.tm_mday;
}

static bool brief_is_today(void)
{
    int today = local_day(time(NULL), NULL);
    return today && s_brief_at && local_day(s_brief_at, NULL) == today;
}

static void brief_load(void)
{
    nvs_handle_t h;
    if (nvs_open(NVS_NS, NVS_READONLY, &h) != ESP_OK) {
        return;
    }
    size_t len = ANSWER_MAX;
    int64_t at = 0;
    if (nvs_get_i64(h, "brief_at", &at) == ESP_OK && nvs_get_str(h, "brief", s_brief, &len) == ESP_OK) {
        s_brief_at = (time_t)at;
    } else {
        s_brief[0] = '\0';
    }
    nvs_close(h);
}

static void brief_save(void *arg)
{
    (void)arg;
    nvs_handle_t h;
    if (nvs_open(NVS_NS, NVS_READWRITE, &h) != ESP_OK) {
        return;
    }
    xSemaphoreTake(s_mutex, portMAX_DELAY);
    bool ok = nvs_set_str(h, "brief", s_brief) == ESP_OK && nvs_set_i64(h, "brief_at", s_brief_at) == ESP_OK;
    xSemaphoreGive(s_mutex);
    if (!ok || nvs_commit(h) != ESP_OK) {
        ESP_LOGE(TAG, "can't save the brief");
    }
    nvs_close(h);
}

static void do_brief(void)
{
    if (run_turn(BRIEF_PROMPT)) {
        xSemaphoreTake(s_mutex, portMAX_DELAY);
        strlcpy(s_brief, s_turn_text, ANSWER_MAX);
        s_brief_at = time(NULL);
        xSemaphoreGive(s_mutex);
        esp_timer_start_once(s_save_timer, 1000);
        s_retry_us = 0;
    } else {
        s_retry_us = now_us() + BRIEF_RETRY_US;
    }
}

/*
 * Asks for today's brief if it's time: once a day after BRIEF_HOUR, or earlier
 * when the user asked for it (`asked`), and at most BRIEF_TRIES times a day.
 * Nothing is asked while the clock isn't set or Muse isn't connected, since
 * that wouldn't reach the chat anyway.
 */
static void maybe_brief(bool asked)
{
    int hour = 0;
    int today = local_day(time(NULL), &hour);
    if (!today || !muse_hatch_ready() || brief_is_today()) {
        return;
    }
    if (today != s_tries_day) {
        s_tries_day = today;
        s_tries = 0;
        s_retry_us = 0;
    }
    if (s_tries >= BRIEF_TRIES || (!asked && (hour < BRIEF_HOUR || now_us() < s_retry_us))) {
        return;
    }
    s_tries++;
    ESP_LOGI(TAG, "asking for the brief (%d today)", s_tries);
    s_busy = true;
    do_brief();
    s_busy = false;
}

static void do_ask(char *question)
{
    char *prompt = heap_caps_malloc(strlen(question) + sizeof(ASK_SUFFIX), MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    if (prompt) {
        strcpy(prompt, question);
        strcat(prompt, ASK_SUFFIX);
        run_turn(prompt);
        free(prompt);
    } else {
        s_turn_len = 0;
        append("内存不足");
    }
    xSemaphoreTake(s_mutex, portMAX_DELAY);
    strlcpy(s_question, question, QUESTION_MAX);
    strlcpy(s_answer, s_turn_text, ANSWER_MAX);
    s_answer_us = now_us();
    xSemaphoreGive(s_mutex);
    free(question);
    if (s_answer_cb) {
        s_answer_cb(s_question, s_answer);
    }
}

static void ask_task(void *arg)
{
    (void)arg;
    for (;;) {
        job_t job;
        if (xQueueReceive(s_jobs, &job, pdMS_TO_TICKS(10000)) != pdTRUE) {
            maybe_brief(false);
        } else if (job.kind == JOB_ASK) {
            s_busy = true;
            do_ask(job.text);
            s_busy = false;
        } else if (job.kind == JOB_BRIEF) {
            maybe_brief(true);
        } else {   /* from the debug console: now, whatever the day's count */
            s_busy = true;
            do_brief();
            s_busy = false;
        }
    }
}

void muse_bridge_ask_start(void)
{
    s_jobs = xQueueCreate(4, sizeof(job_t));
    s_turn_done = xSemaphoreCreateBinary();
    s_mutex = xSemaphoreCreateMutex();
    s_turn_text = heap_caps_calloc(1, ANSWER_MAX, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    s_answer = heap_caps_calloc(1, ANSWER_MAX, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    s_brief = heap_caps_calloc(1, ANSWER_MAX, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    s_question = heap_caps_calloc(1, QUESTION_MAX, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    if (!s_jobs || !s_turn_done || !s_mutex || !s_turn_text || !s_answer || !s_brief || !s_question) {
        ESP_LOGE(TAG, "out of memory");
        return;
    }
    brief_load();
    const esp_timer_create_args_t save_args = { .callback = brief_save, .name = "muse_brief_save" };
    if (esp_timer_create(&save_args, &s_save_timer) != ESP_OK) {
        ESP_LOGE(TAG, "save timer failed");
        return;
    }
    muse_hatch_console_hook = on_console;
    /* PSRAM stack: internal RAM is what xiaozhi runs short of, and this task
     * never touches flash (the brief is saved by s_save_timer). */
    if (xTaskCreatePinnedToCoreWithCaps(ask_task, "muse_ask", 6144, NULL, 4, NULL, tskNO_AFFINITY,
                                        MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT) != pdPASS) {
        ESP_LOGE(TAG, "task failed");
    }
}

/* ---- muse_bridge.h ---- */

bool muse_bridge_ask(const char *question)
{
    if (!s_jobs || !question || !question[0]) {
        return false;
    }
    size_t n = strnlen(question, QUESTION_MAX - 1);
    char *copy = malloc(n + 1);
    if (!copy) {
        return false;
    }
    memcpy(copy, question, n);
    copy[n] = '\0';
    job_t job = { JOB_ASK, copy };
    if (xQueueSend(s_jobs, &job, 0) != pdTRUE) {
        free(copy);
        return false;
    }
    return true;
}

void muse_bridge_refresh_brief(bool force)
{
    if (s_jobs) {
        job_t job = { force ? JOB_BRIEF_FORCE : JOB_BRIEF, NULL };
        xQueueSend(s_jobs, &job, 0);
    }
}

bool muse_bridge_busy(void)
{
    return s_busy || (s_jobs && uxQueueMessagesWaiting(s_jobs) > 0);
}

static int age_s(int64_t at)
{
    return at ? (int)((now_us() - at) / 1000000) : -1;
}

static int brief_age_s(void)
{
    time_t t = time(NULL);
    return s_brief_at && t >= CLOCK_VALID ? (int)(t - s_brief_at) : -1;
}

int muse_bridge_brief(char *out, size_t cap, bool today_only)
{
    if (!s_brief) {
        out[0] = '\0';
        return -1;
    }
    xSemaphoreTake(s_mutex, portMAX_DELAY);
    strlcpy(out, s_brief, cap);
    int age = brief_age_s();
    bool today = brief_is_today();
    xSemaphoreGive(s_mutex);
    if (today_only && !today) {
        out[0] = '\0';
        return -1;
    }
    return age;
}

int muse_bridge_last_answer(char *question, size_t qcap, char *answer, size_t acap)
{
    if (!s_answer) {
        question[0] = answer[0] = '\0';
        return -1;
    }
    xSemaphoreTake(s_mutex, portMAX_DELAY);
    strlcpy(question, s_question, qcap);
    strlcpy(answer, s_answer, acap);
    int age = age_s(s_answer_us);
    xSemaphoreGive(s_mutex);
    return age;
}

void muse_bridge_set_answer_cb(muse_bridge_answer_cb_t cb)
{
    s_answer_cb = cb;
}

void muse_bridge_clock_synced(void)
{
    s_clock_synced = true;
}
