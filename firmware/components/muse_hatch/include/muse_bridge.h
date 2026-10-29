/*
 * StackChan <-> Muse bridge.
 *
 * Runs the Muse SDK's chat session (muse_chat_session.cpp) next to xiaozhi and
 * takes setup and chat commands over the USB serial port, in the same line
 * format as the Muse SDK's console, so tools/muse/chat.py works with it:
 *
 *   >status                 prints "@status {...}"
 *   >hatch.token=TOKEN      sets the device token (">hatch.token+=" appends)
 *   >hatch.vm=ID            picks a VM (empty: the account's default)
 *   >chat+=TEXT / >chat=TEXT  sends a typed message; the reply streams back
 *                           as "@chat {...}" lines
 *   >chat.cancel            drops a typed turn
 *   >ask=TEXT               queues a question as the voice tools do (muse_bridge_ask)
 *   >brief                  prints the cached brief (">brief=refresh" asks for a new one)
 *   >answer                 prints the last answer
 */

#pragma once

#ifdef __cplusplus
extern "C" {
#endif

#include <stdbool.h>
#include <stddef.h>

/* Loads the saved settings, starts the session task and the serial console. */
void muse_bridge_start(void);

/*
 * Questions for Muse from the rest of the firmware (muse_ask.c). Muse takes
 * 10-60 s, so asking only queues the question; the answer goes to the callback
 * (on the asking task) when it comes. A brief of the user's day is asked once
 * a day in the background (each one is a message in the user's Muse chat).
 */
typedef void (*muse_bridge_answer_cb_t)(const char *question, const char *answer);

/* Queues a question; false if it can't (not started, queue full). */
bool muse_bridge_ask(const char *question);
/* A question or brief is being asked, or waiting to be. */
bool muse_bridge_busy(void);
/* Asks for today's brief if there isn't one yet (within the daily limit);
 * `force` asks for a new one now regardless (debug console). */
void muse_bridge_refresh_brief(bool force);
/* Copies the brief; returns its age in seconds, or -1 if there isn't one
 * (with `today_only`, one from today). */
int muse_bridge_brief(char *out, size_t cap, bool today_only);
/* Copies the last question and Muse's answer; returns the answer's age in seconds, or -1. */
int muse_bridge_last_answer(char *question, size_t qcap, char *answer, size_t acap);
void muse_bridge_set_answer_cb(muse_bridge_answer_cb_t cb);
/* SNTP has set the clock: until then the brief's daily schedule waits. */
void muse_bridge_clock_synced(void);

/* Handles console commands the bridge doesn't know (">name..."): return true if handled.
 * Called on the console task. */
typedef bool (*muse_bridge_command_cb_t)(const char *line);
void muse_bridge_set_command_cb(muse_bridge_command_cb_t cb);

#ifdef __cplusplus
}
#endif
