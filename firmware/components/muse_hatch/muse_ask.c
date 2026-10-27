/*
 * StackChan bridge: questions for Muse from the rest of the firmware.
 *
 * Muse answers in 10-60 s (longer when it looks at the calendar or mail), far
 * too long to hold xiaozhi's main thread, so questions are asked here, one at a
 * time, on a task of their own: muse_bridge_ask() queues one and returns, and
 * the answer goes to the callback when it comes. The same task keeps a brief
 * of the user's day (calendar and important mail) fresh, so the common
 * question can be answered at once from it.
 *
 * Replies are collected from muse_hatch_console, which the chat session calls
 * for every piece of a typed turn.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/idf_additions.h"
#include "freertos/queue.h"
#include "freertos/semphr.h"
#include "freertos/task.h"

#include "muse_bridge.h"
#include "muse_chat.h"

static const char *TAG = "muse_ask";

#define ANSWER_MAX 3072
#define QUESTION_MAX 512
#define TURN_TIMEOUT_MS (6 * 60 * 1000)         /* the session gives up after 5 min */
#define BRIEF_EVERY_US (60 * 60 * 1000000LL)
#define BRIEF_RETRY_US (5 * 60 * 1000000LL)
#define BRIEF_FIRST_US (45 * 1000000LL)         /* after boot: let Wi-Fi and xiaozhi settle */

#define BRIEF_PROMPT                                                                         \
    "请用简短自然的中文口语，总结我今天和明天日历上的安排，再提一下过去一天里需要我注意的" \
    "重要邮件（最多三封，没有就说没有）。总共不超过150字，不要用列表、编号或Markdown，"     \
    "像朋友聊天一样说。"
#define ASK_SUFFIX                                                                     \
    "\n\n（这是我通过桌面机器人 StackChan 用语音问的。请用简短自然的中文口语回答，" \
    "不超过120字，不要用列表、编号或Markdown。）"

typedef enum { JOB_ASK, JOB_BRIEF } job_kind_t;

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
static int64_t s_answer_us, s_brief_us;
static volatile bool s_busy;

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

static void do_brief(void)
{
    bool ok = run_turn(BRIEF_PROMPT);
    if (ok) {
        store(&s_brief, s_turn_text);
        xSemaphoreTake(s_mutex, portMAX_DELAY);
        s_brief_us = now_us();
        xSemaphoreGive(s_mutex);
    }
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
    int64_t next_brief = now_us() + BRIEF_FIRST_US;
    for (;;) {
        job_t job;
        if (xQueueReceive(s_jobs, &job, pdMS_TO_TICKS(10000)) == pdTRUE) {
            s_busy = true;
            if (job.kind == JOB_ASK) {
                do_ask(job.text);
            } else {
                do_brief();
                next_brief = now_us() + (s_brief_us ? BRIEF_EVERY_US : BRIEF_RETRY_US);
            }
            s_busy = false;
            continue;
        }
        if (now_us() >= next_brief) {
            s_busy = true;
            do_brief();
            s_busy = false;
            int64_t age = now_us() - s_brief_us;
            next_brief = now_us() + (s_brief_us && age < BRIEF_EVERY_US ? BRIEF_EVERY_US : BRIEF_RETRY_US);
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
    muse_hatch_console_hook = on_console;
    /* PSRAM stack: internal RAM is what xiaozhi runs short of, and this task
     * never touches flash. */
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

void muse_bridge_refresh_brief(void)
{
    if (s_jobs) {
        job_t job = { JOB_BRIEF, NULL };
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

int muse_bridge_brief(char *out, size_t cap)
{
    if (!s_brief) {
        out[0] = '\0';
        return -1;
    }
    xSemaphoreTake(s_mutex, portMAX_DELAY);
    strlcpy(out, s_brief, cap);
    int age = age_s(s_brief_us);
    xSemaphoreGive(s_mutex);
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
