/*
 * SPDX-FileCopyrightText: 2026 M5Stack Technology CO LTD
 *
 * SPDX-License-Identifier: MIT
 */
#include "hal.h"
#include <mooncake_log.h>
#include <mcp_server.h>
#include <stackchan/stackchan.h>
#include <apps/common/common.h>
#include <assets/assets.h>
#include <muse_bridge.h>
#include <esp_timer.h>
#include <algorithm>
#include <mutex>
#include "board/hal_bridge.h"
#include "board/avatar_character.h"

using namespace stackchan;

static const std::string_view _tag = "HAL-MCP";

// self.muse.ask is an async tool: its tools/call waits (off the main task) for
// Muse's answer, so the model reads it out in the same turn. Past
// _muse_wait_us the call is answered with "still asking" instead, and the
// answer, when it comes, chimes; the user then asks for it (self.muse.get_answer).
// The xiaozhi.me server ignores text sent as a wake word, so the device can't
// start a turn that reads it out by itself.
static constexpr int64_t _muse_wait_us = 60 * 1000000LL;
static constexpr size_t _muse_question_max = 511;   // as muse_bridge_ask keeps it

static std::mutex _muse_mutex;
static McpTool::AsyncReply _muse_reply;   // the tools/call waiting for Muse, if any
static std::string _muse_question;        // what it asked
static esp_timer_handle_t _muse_timer;

static McpTool::AsyncReply _take_muse_reply(const char* question)
{
    std::lock_guard<std::mutex> lock(_muse_mutex);
    if (!_muse_reply || (question && _muse_question != question)) {
        return nullptr;
    }
    _muse_question.clear();
    return std::move(_muse_reply);
}

static void _on_muse_timeout(void*)
{
    if (auto reply = _take_muse_reply(nullptr)) {
        mclog::tagInfo(_tag, "muse.ask: no answer in {} s", _muse_wait_us / 1000000);
        reply(std::string("Muse 还在查，已经超过一分钟了。请告诉用户：Muse 回复后我会叮一声，到时候问我“Muse 怎么说”。"));
    }
}

static void _on_muse_answer(const char* question, const char* answer)
{
    if (auto reply = _take_muse_reply(question)) {
        esp_timer_stop(_muse_timer);
        mclog::tagInfo(_tag, "muse answered in time: {}", question);
        reply(fmt::format("Muse 的回复：{}", answer));
        return;
    }
    mclog::tagInfo(_tag, "muse answered late: {}", question);
    hal_bridge::app_play_sound(OGG_NEW_NOTIFICATION);
}

static void _add_muse_tools(McpServer& mcp_server)
{
    muse_bridge_set_answer_cb(_on_muse_answer);

    mclog::tagInfo(_tag, "add muse.get_brief tool");
    mcp_server.AddTool(
        "self.muse.get_brief",
        "获取用户今天和明天的日程安排，以及需要注意的重要邮件。内容来自用户的个人助理 Muse（它连着用户的 Google "
        "日历和 Gmail），已提前缓存，会立即返回。用户问今天/明天有什么安排、日程、课程、会议、邮件时，优先调用这个工具，"
        "然后用自然的口语转述。",
        std::vector<Property>{}, [](const PropertyList&) -> ReturnValue {
            std::string brief(3072, '\0');
            int age = muse_bridge_brief(brief.data(), brief.size());
            brief.resize(strlen(brief.c_str()));
            if (age < 0 || brief.empty()) {
                muse_bridge_refresh_brief();
                return std::string("Muse 的日程简报还在准备，大约一分钟后再问一次。也可以用 self.muse.ask 直接问 Muse。");
            }
            return fmt::format("{}\n（这是 {} 分钟前从 Muse 获取的）", brief, age / 60);
        });

    esp_timer_create_args_t timer_args = {};
    timer_args.callback = _on_muse_timeout;
    timer_args.name     = "muse_wait";
    esp_timer_create(&timer_args, &_muse_timer);

    mclog::tagInfo(_tag, "add muse.ask tool");
    mcp_server.AddAsyncTool(
        "self.muse.ask",
        "把问题转交给用户的个人助理 Muse 并等它回答。Muse 能查看用户的 Gmail、Google 日历和个人记忆。用户说“问问 "
        "Muse”、“用 Muse 查”，或者问到需要个人信息、邮件或日程细节而 self.muse.get_brief 里没有的问题时调用。"
        "调用前先跟用户说一句“我问问 Muse，稍等一下”。Muse 通常 10 到 30 秒回答，这个工具会等到它回答，"
        "然后把 Muse 的回复用自然的口语转述给用户。",
        PropertyList({Property("question", kPropertyTypeString, std::string(""))}),
        [](const PropertyList& properties, McpTool::AsyncReply reply) {
            auto question = properties["question"].value<std::string>();
            mclog::tagInfo(_tag, "muse.ask: {}", question);
            if (question.empty()) {
                reply(std::string("没有问题内容"));
                return;
            }
            question.resize(std::min(question.size(), _muse_question_max));
            {
                std::lock_guard<std::mutex> lock(_muse_mutex);
                if (_muse_reply) {
                    reply(std::string("上一个问题还在等 Muse 回答，请稍后再问。"));
                    return;
                }
                if (!muse_bridge_ask(question.c_str())) {
                    reply(std::string("Muse 现在忙不过来，请稍后再问。"));
                    return;
                }
                _muse_reply    = std::move(reply);
                _muse_question = question;
            }
            esp_timer_stop(_muse_timer);
            esp_timer_start_once(_muse_timer, _muse_wait_us);
        });

    mclog::tagInfo(_tag, "add muse.get_answer tool");
    mcp_server.AddTool("self.muse.get_answer",
                       "读取 Muse 对上一个问题的回复。self.muse.ask 超过一分钟没等到、Muse 稍后叮一声提示时用：用户问"
                       "“Muse 怎么说”“Muse 回复了吗”时调用，然后用自然的口语转述回复内容。",
                       std::vector<Property>{}, [](const PropertyList&) -> ReturnValue {
                           mclog::tagInfo(_tag, "muse.get_answer");
                           std::string question(256, '\0');
                           std::string answer(3072, '\0');
                           int age = muse_bridge_last_answer(question.data(), question.size(), answer.data(),
                                                             answer.size());
                           question.resize(strlen(question.c_str()));
                           answer.resize(strlen(answer.c_str()));
                           if (muse_bridge_busy() && (age < 0 || answer.empty())) {
                               return std::string("Muse 还在想，请稍等。");
                           }
                           if (age < 0 || answer.empty()) {
                               return std::string("还没有向 Muse 提过问题。");
                           }
                           return fmt::format("问题：{}\nMuse 的回复（{} 秒前）：{}", question, age, answer);
                       });
}

void Hal::xiaozhi_mcp_init()
{
    mclog::tagInfo(_tag, "init");

    // https://github.com/78/xiaozhi-esp32/blob/main/docs/mcp-usage.md
    auto& mcp_server = McpServer::GetInstance();

    // System Prompt：
    // You can control the robot's head. Use get_yaw and get_pitch to sense current position. Use set_yaw for horizontal
    // movement and set_pitch for vertical movement. All angles are in degrees.

    mclog::tagInfo(_tag, "add robot.get_head_angles tool");
    mcp_server.AddTool("self.robot.get_head_angles",
                       "Returns current yaw/pitch in degrees. Neutral position is {yaw:0, pitch:0}.",
                       std::vector<Property>{}, [this](const PropertyList& properties) -> ReturnValue {
                           LvglLockGuard lock;  // StackChan motion update is under the lvgl lock

                           auto& motion      = GetStackChan().motion();
                           int current_yaw   = motion.yawServo().getCurrentAngle() / 10;
                           int current_pitch = motion.pitchServo().getCurrentAngle() / 10;

                           auto result = fmt::format(R"({{"yaw": {}, "pitch": {}}})", current_yaw, current_pitch);
                           mclog::tagInfo(_tag, "get_head_angles: {}", result);
                           return result;
                       });

    mclog::tagInfo(_tag, "add robot.set_head_angles tool");
    mcp_server.AddTool("self.robot.set_head_angles",
                       "Adjust head position. GUIDELINES: "
                       "1. For natural interaction, stay within +/- 45 degrees. "
                       "2. Only use values > 70 if the user explicitly asks to look far away/behind. "
                       "3. Max ranges: Yaw(-128 to 128, -128 as your left), Pitch(0 to 90, 90 as your up). "
                       "Speed(100-1000, 150 is natural).",
                       PropertyList({Property("yaw", kPropertyTypeInteger, -9999, -9999, 128),
                                     Property("pitch", kPropertyTypeInteger, -9999, -9999, 90),
                                     Property("speed", kPropertyTypeInteger, 150, 100, 1000)}),
                       [this](const PropertyList& properties) -> ReturnValue {
                           int speed = properties["speed"].value<int>();
                           int yaw   = properties["yaw"].value<int>();
                           int pitch = properties["pitch"].value<int>();

                           mclog::tagInfo(_tag, "motion set_angles: yaw: {}, pitch: {}, speed: {}", yaw, pitch, speed);

                           LvglLockGuard lock;

                           auto& motion = GetStackChan().motion();
                           if (pitch != -9999) {
                               motion.pitchServo().moveWithSpeed(pitch * 10, speed);
                           }
                           if (yaw != -9999) {
                               motion.yawServo().moveWithSpeed(yaw * 10, speed);
                           }

                           return true;
                       });

    mclog::tagInfo(_tag, "add robot.set_led_color tool");
    mcp_server.AddTool(
        "self.robot.set_led_color",
        "Set the color of the robot's INTERNAL onboard LED. This is NOT for room lights. "
        "Values: 0-168 (safe range). Red=168,0,0; Green=0,168,0; Blue=0,0,168; White=100,100,100; Off=0,0,0.",
        PropertyList({Property("red", kPropertyTypeInteger, 0, 0, 168),
                      Property("green", kPropertyTypeInteger, 0, 0, 168),
                      Property("blue", kPropertyTypeInteger, 0, 0, 168)}),
        [this](const PropertyList& properties) -> ReturnValue {
            int r = properties["red"].value<int>();
            int g = properties["green"].value<int>();
            int b = properties["blue"].value<int>();

            mclog::tagInfo(_tag, "set_led_color: r={}, g={}, b={}", r, g, b);

            LvglLockGuard lock;

            GetStackChan().leftNeonLight().setColor(r, g, b);
            GetStackChan().rightNeonLight().setColor(r, g, b);

            return true;
        });

    mclog::tagInfo(_tag, "add robot.set_character tool");
    mcp_server.AddTool(
        "self.robot.set_character",
        "切换机器人屏幕上的脸（互动形象）。可选：stackchan（默认的 Stack-chan 脸）、pikachu（皮卡丘）、"
        "charmander（小火龙）、bulbasaur（妙蛙种子）、squirtle（杰尼龟）、ditto（百变怪）。"
        "用户说“换成皮卡丘”“变成小火龙”“换回原来的脸”时调用；选择会保存，重启后保留。"
        "换好后可以用那只宝可梦的口吻简短打个招呼。",
        PropertyList({Property("character", kPropertyTypeString, std::string("stackchan"))}),
        [](const PropertyList& properties) -> ReturnValue {
            auto character = properties["character"].value<std::string>();
            std::transform(character.begin(), character.end(), character.begin(), ::tolower);
            mclog::tagInfo(_tag, "set_character: {}", character);
            if (!avatar_character::set(character)) {
                std::string names;
                for (auto& name : avatar_character::names()) {
                    names += (names.empty() ? "" : ", ") + name;
                }
                return "没有这个形象，可选：" + names;
            }
            return "已换成 " + character;
        });

    mcp_server.AddTool(
        "self.robot.show_expression",
        "让屏幕上的脸做一个表情并保持几秒：neutral（平静）、happy（开心）、angry（生气）、sad（难过）、"
        "doubt（疑惑）、sleepy（困）、cool（酷/得意）。用户让你“生个气”“做个酷的表情”“装酷”“难过一下”等时，"
        "或者你想强调情绪时调用，然后再说话。不同形象有专属效果：小火龙生气时尾巴火焰烧旺，"
        "皮卡丘生气时脸颊放电，杰尼龟 cool 时戴墨镜。seconds 默认 8。",
        PropertyList({Property("expression", kPropertyTypeString, std::string("happy")),
                      Property("seconds", kPropertyTypeInteger, 8, 1, 30)}),
        [](const PropertyList& properties) -> ReturnValue {
            auto expression = properties["expression"].value<std::string>();
            int seconds     = properties["seconds"].value<int>();
            std::transform(expression.begin(), expression.end(), expression.begin(), ::tolower);
            mclog::tagInfo(_tag, "show_expression: {} {}s", expression, seconds);
            if (!avatar_character::show_expression(expression, seconds)) {
                return "没有这个表情，可选：neutral, happy, angry, sad, doubt, sleepy, cool";
            }
            return "表情已显示";
        });

    mcp_server.AddTool("self.robot.get_character", "查询机器人当前的脸（互动形象）和可选的形象。", PropertyList(),
                       [](const PropertyList& properties) -> ReturnValue {
                           std::string names;
                           for (auto& name : avatar_character::names()) {
                               names += (names.empty() ? "" : ", ") + name;
                           }
                           return "当前：" + avatar_character::current() + "；可选：" + names;
                       });

    mclog::tagInfo(_tag, "add robot.create_reminder tool");
    mcp_server.AddTool("self.robot.create_reminder",
                       "Create a reminder. Duration is in seconds. Message is what to say when time is up. Set repeat "
                       "to true to repeat the reminder.",
                       PropertyList({Property("duration_seconds", kPropertyTypeInteger, 60, 1, 86400),
                                     Property("message", kPropertyTypeString, std::string("Time's up!")),
                                     Property("repeat", kPropertyTypeBoolean, false)}),
                       [this](const PropertyList& properties) -> ReturnValue {
                           int duration_seconds = properties["duration_seconds"].value<int>();
                           std::string message  = properties["message"].value<std::string>();
                           bool repeat          = properties["repeat"].value<bool>();

                           // Default message
                           if (message.empty()) {
                               message = "Time's up!";
                           }

                           mclog::tagInfo(_tag, "create_reminder: duration={}s, message={}, repeat={}",
                                          duration_seconds, message, repeat);

                           int id = tools::create_reminder(duration_seconds * 1000, message, repeat);

                           return id;
                       });

    mclog::tagInfo(_tag, "add robot.get_reminders tool");
    mcp_server.AddTool("self.robot.get_reminders", "Get list of active reminders.", std::vector<Property>{},
                       [this](const PropertyList& properties) -> ReturnValue {
                           mclog::tagInfo(_tag, "get_reminders");
                           auto reminders          = tools::get_active_reminders();
                           std::string result_json = "[";
                           for (size_t i = 0; i < reminders.size(); ++i) {
                               const auto& r = reminders[i];
                               result_json +=
                                   fmt::format(R"({{"id": {}, "duration_ms": {}, "message": "{}", "repeat": {}}})",
                                               r.id, r.durationMs, r.message, r.repeat ? "true" : "false");
                               if (i < reminders.size() - 1) {
                                   result_json += ", ";
                               }
                           }
                           result_json += "]";
                           mclog::tagInfo(_tag, "get_reminders result: {}", result_json);
                           return result_json;
                       });

    mclog::tagInfo(_tag, "add robot.stop_reminder tool");
    mcp_server.AddTool("self.robot.stop_reminder", "Stop a reminder by ID.",
                       PropertyList({Property("id", kPropertyTypeInteger, -1)}),
                       [this](const PropertyList& properties) -> ReturnValue {
                           int id = properties["id"].value<int>();
                           mclog::tagInfo(_tag, "stop_reminder: id={}", id);
                           tools::stop_reminder(id);
                           return true;
                       });

    _add_muse_tools(mcp_server);
}
