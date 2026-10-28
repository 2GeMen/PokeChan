/*
 * SPDX-FileCopyrightText: 2026 M5Stack Technology CO LTD
 *
 * SPDX-License-Identifier: MIT
 */
#include "stackchan_display.h"
#include <esp_log.h>
#include <esp_err.h>
#include <esp_lvgl_port.h>
#include <esp_psram.h>
#include <vector>
#include <cstring>
#include <src/misc/cache/lv_cache.h>
#include <settings.h>
#include <lvgl.h>
#include <lvgl_theme.h>
#include <stackchan/stackchan.h>
#include <assets/lang_config.h>
#include <hal/hal.h>
#include <stackchan/avatar/skins/pokemon/pokemon.h>
#include "avatar_character.h"
#include <application.h>
#include <muse_bridge.h>
#include <esp_heap_caps.h>
#include <algorithm>

using namespace stackchan;
using namespace stackchan::avatar;

#define TAG "StackChanAvatarDisplay"

static StackChanAvatarDisplay* s_display = nullptr;
static const char* kDefaultCharacter     = "stackchan";
static bool on_console_command(const char* line);
static int64_t s_expression_until_us        = 0;
static esp_timer_handle_t s_expression_timer = nullptr;
static int s_emotion_motion_id               = -1;  // EmotionMotionModifier: head gestures for emotions

static EmotionMotionModifier* emotion_motion()
{
    return static_cast<EmotionMotionModifier*>(GetStackChan().getModifier(s_emotion_motion_id));
}

LV_FONT_DECLARE(BUILTIN_TEXT_FONT);
LV_FONT_DECLARE(BUILTIN_ICON_FONT);
LV_FONT_DECLARE(font_awesome_30_4);

// Have to register themes, so the asset apply can update the text font
void StackChanAvatarDisplay::InitializeLcdThemes()
{
    auto text_font       = std::make_shared<LvglBuiltInFont>(&BUILTIN_TEXT_FONT);
    auto icon_font       = std::make_shared<LvglBuiltInFont>(&BUILTIN_ICON_FONT);
    auto large_icon_font = std::make_shared<LvglBuiltInFont>(&font_awesome_30_4);

    // light theme
    auto light_theme = new LvglTheme("light");
    light_theme->set_background_color(lv_color_hex(0xFFFFFF));        // rgb(255, 255, 255)
    light_theme->set_text_color(lv_color_hex(0x000000));              // rgb(0, 0, 0)
    light_theme->set_chat_background_color(lv_color_hex(0xE0E0E0));   // rgb(224, 224, 224)
    light_theme->set_user_bubble_color(lv_color_hex(0x00FF00));       // rgb(0, 128, 0)
    light_theme->set_assistant_bubble_color(lv_color_hex(0xDDDDDD));  // rgb(221, 221, 221)
    light_theme->set_system_bubble_color(lv_color_hex(0xFFFFFF));     // rgb(255, 255, 255)
    light_theme->set_system_text_color(lv_color_hex(0x000000));       // rgb(0, 0, 0)
    light_theme->set_border_color(lv_color_hex(0x000000));            // rgb(0, 0, 0)
    light_theme->set_low_battery_color(lv_color_hex(0x000000));       // rgb(0, 0, 0)
    light_theme->set_text_font(text_font);
    light_theme->set_icon_font(icon_font);
    light_theme->set_large_icon_font(large_icon_font);

    // dark theme
    auto dark_theme = new LvglTheme("dark");
    dark_theme->set_background_color(lv_color_hex(0x000000));        // rgb(0, 0, 0)
    dark_theme->set_text_color(lv_color_hex(0xFFFFFF));              // rgb(255, 255, 255)
    dark_theme->set_chat_background_color(lv_color_hex(0x1F1F1F));   // rgb(31, 31, 31)
    dark_theme->set_user_bubble_color(lv_color_hex(0x00FF00));       // rgb(0, 128, 0)
    dark_theme->set_assistant_bubble_color(lv_color_hex(0x222222));  // rgb(34, 34, 34)
    dark_theme->set_system_bubble_color(lv_color_hex(0x000000));     // rgb(0, 0, 0)
    dark_theme->set_system_text_color(lv_color_hex(0xFFFFFF));       // rgb(255, 255, 255)
    dark_theme->set_border_color(lv_color_hex(0xFFFFFF));            // rgb(255, 255, 255)
    dark_theme->set_low_battery_color(lv_color_hex(0xFF0000));       // rgb(255, 0, 0)
    dark_theme->set_text_font(text_font);
    dark_theme->set_icon_font(icon_font);
    dark_theme->set_large_icon_font(large_icon_font);

    auto& theme_manager = LvglThemeManager::GetInstance();
    theme_manager.RegisterTheme("light", light_theme);
    theme_manager.RegisterTheme("dark", dark_theme);
}

StackChanAvatarDisplay::StackChanAvatarDisplay(esp_lcd_panel_io_handle_t panel_io, esp_lcd_panel_handle_t panel,
                                               int width, int height, int offset_x, int offset_y, bool mirror_x,
                                               bool mirror_y, bool swap_xy)
    : LvglDisplay(), panel_io_(panel_io), panel_(panel)
{
    width_  = width;
    height_ = height;

    // Initialize LCD themes
    InitializeLcdThemes();

    // Load theme from settings
    Settings settings("display", false);
    std::string theme_name = settings.GetString("theme", "light");
    current_theme_         = LvglThemeManager::GetInstance().GetTheme(theme_name);

    // Draw white screen
    std::vector<uint16_t> buffer(width_, 0xFFFF);
    for (int y = 0; y < height_; y++) {
        esp_lcd_panel_draw_bitmap(panel_, 0, y, width_, y + 1, buffer.data());
    }

    // Set the display to on
    ESP_LOGI(TAG, "Turning display on");
    {
        esp_err_t __err = esp_lcd_panel_disp_on_off(panel_, true);
        if (__err == ESP_ERR_NOT_SUPPORTED) {
            ESP_LOGW(TAG, "Panel does not support disp_on_off; assuming ON");
        } else {
            ESP_ERROR_CHECK(__err);
        }
    }

    ESP_LOGI(TAG, "Initialize LVGL library");
    lv_init();

#if CONFIG_SPIRAM
    // lv image cache, currently only PNG is supported
    size_t psram_size_mb = esp_psram_get_size() / 1024 / 1024;
    if (psram_size_mb >= 8) {
        lv_image_cache_resize(2 * 1024 * 1024, true);
        ESP_LOGI(TAG, "Use 2MB of PSRAM for image cache");
    } else if (psram_size_mb >= 2) {
        lv_image_cache_resize(512 * 1024, true);
        ESP_LOGI(TAG, "Use 512KB of PSRAM for image cache");
    }
#endif

    ESP_LOGI(TAG, "Initialize LVGL port");
    lvgl_port_cfg_t port_cfg = ESP_LVGL_PORT_INIT_CONFIG();
    // port_cfg.task_priority   = 20;
    port_cfg.task_priority = 3;
#if CONFIG_SOC_CPU_CORES_NUM > 1
    port_cfg.task_affinity = 1;
#endif
    lvgl_port_init(&port_cfg);

    ESP_LOGI(TAG, "Adding LCD display");
    const lvgl_port_display_cfg_t display_cfg = {
        .io_handle      = panel_io_,
        .panel_handle   = panel_,
        .control_handle = nullptr,
        .buffer_size    = static_cast<uint32_t>(width_ * 20),
        .double_buffer  = false,
        .trans_size     = 0,
        .hres           = static_cast<uint32_t>(width_),
        .vres           = static_cast<uint32_t>(height_),
        .monochrome     = false,
        .rotation =
            {
                .swap_xy  = swap_xy,
                .mirror_x = mirror_x,
                .mirror_y = mirror_y,
            },
        .color_format = LV_COLOR_FORMAT_RGB565,
        .flags =
            {
                .buff_dma     = 1,
                .buff_spiram  = 0,
                .sw_rotate    = 0,
                .swap_bytes   = 1,
                .full_refresh = 0,
                .direct_mode  = 0,
            },
    };

    display_ = lvgl_port_add_disp(&display_cfg);
    if (display_ == nullptr) {
        ESP_LOGE(TAG, "Failed to add display");
        return;
    }

    if (offset_x != 0 || offset_y != 0) {
        lv_display_set_offset(display_, offset_x, offset_y);
    }

    // Create a timer to hide the preview image
    esp_timer_create_args_t preview_timer_args = {
        .callback =
            [](void* arg) {
                StackChanAvatarDisplay* display = static_cast<StackChanAvatarDisplay*>(arg);
                display->SetPreviewImage(nullptr);
            },
        .arg                   = this,
        .dispatch_method       = ESP_TIMER_TASK,
        .name                  = "preview_timer",
        .skip_unhandled_events = false,
    };
    esp_timer_create(&preview_timer_args, &preview_timer_);

    // Create boot logo label if not warm boot
    if (GetHAL().getWarmRebootTarget() < 0) {
        ESP_LOGI(TAG, "Create boot logo label");
        Lock();
        {
            uitk::lvgl_cpp::ScreenActive screen;
            screen.setBgColor(lv_color_hex(0x000000));
        }
        GetHAL().bootLogo = std::make_unique<BootLogo>();
        Unlock();
    }

    // Robot will be created later in SetupXiaoZhiUI()
}

StackChanAvatarDisplay::~StackChanAvatarDisplay()
{
    ESP_LOGI(TAG, "Destroying StackChanAvatarDisplay");

    if (preview_timer_ != nullptr) {
        esp_timer_stop(preview_timer_);
        esp_timer_delete(preview_timer_);
    }

    if (preview_image_ != nullptr) {
        lv_obj_del(preview_image_);
    }

    auto& stackchan = GetStackChan();
    if (stackchan.hasAvatar()) {
        stackchan.resetAvatar();
    }
}

bool StackChanAvatarDisplay::Lock(int timeout_ms)
{
    return lvgl_port_lock(timeout_ms);
}

void StackChanAvatarDisplay::Unlock()
{
    lvgl_port_unlock();
}

lv_disp_t* StackChanAvatarDisplay::GetLvglDisplay()
{
    return display_;
}

#include <hal/board/hal_bridge.h>

void StackChanAvatarDisplay::SetupUI()
{
    // Prevent duplicate calls - if already called, return early
    if (setup_ui_called_) {
        ESP_LOGW(TAG, "SetupUI() called multiple times, skipping duplicate call");
        return;
    }

    Display::SetupUI();  // Mark SetupUI as called

    auto& stackchan = GetStackChan();

    if (stackchan.hasAvatar()) {
        ESP_LOGW(TAG, "Avatar already created");
        return;
    }

    DisplayLockGuard lock(this);

    ESP_LOGI(TAG, "Creating Stack-chan Avatar...");

    s_display = this;
    stackchan.attachAvatar(CreateAvatar(avatar_character::current(), nullptr, &avatar_panel_));
    muse_bridge_set_command_cb(on_console_command);
    stackchan.addModifier(std::make_unique<BreathModifier>());
    blink_modifier_id_ = stackchan.addModifier(std::make_unique<BlinkModifier>());
    stackchan.addModifier(std::make_unique<HeadPetModifier>());
    stackchan.addModifier(std::make_unique<ImuEventModifier>());
    EmotionMotionModifier::setEnabled(avatar_character::head_gestures());
    s_emotion_motion_id = stackchan.addModifier(std::make_unique<EmotionMotionModifier>());

    preview_image_ = lv_image_create(lv_screen_active());
    lv_obj_set_size(preview_image_, 320, 240);
    lv_obj_align(preview_image_, LV_ALIGN_CENTER, 0, 0);
    lv_obj_add_flag(preview_image_, LV_OBJ_FLAG_HIDDEN);

    // GetHAL().startStackChanAutoUpdate(24);

    auto config        = hal_bridge::get_xiaozhi_config();
    idle_motion_level_ = config.idleRandomMovementLevel;

    ESP_LOGI(TAG, "Avatar created and started");
}

static void on_avatar_click()
{
    static uint32_t last_toggle_tick = 0;
    const uint32_t now               = GetHAL().millis();
    if (last_toggle_tick != 0 && now - last_toggle_tick < 2000) {
        return;
    }

    if (hal_bridge::is_xiaozhi_ready()) {
        last_toggle_tick = now;
        hal_bridge::toggle_xiaozhi_chat_state();
    }
}

std::unique_ptr<Avatar> StackChanAvatarDisplay::CreateAvatar(const std::string& character, lv_obj_t** panel,
                                                             lv_obj_t** created_panel)
{
    lv_obj_t* local_panel = nullptr;
    if (!created_panel) {
        created_panel = &local_panel;
    }
    if (character != kDefaultCharacter) {
        auto images = PokemonImages::load(character);
        if (images) {
            auto avatar = std::make_unique<PokemonAvatar>();
            avatar->init(lv_screen_active(), images);
            avatar->getPanel()->onClick().connect(on_avatar_click);
            if (panel) {
                *panel = avatar->getPanel()->get();
            }
            *created_panel = avatar->getPanel()->get();
            return avatar;
        }
        ESP_LOGW(TAG, "No skin for character %s", character.c_str());
        if (panel) {
            return nullptr;  // switching: keep the current face
        }
    }

    auto avatar = std::make_unique<DefaultAvatar>();
    avatar->init(lv_screen_active());
    avatar->getPanel()->onClick().connect(on_avatar_click);
    if (panel) {
        *panel = avatar->getPanel()->get();
    }
    *created_panel = avatar->getPanel()->get();
    return avatar;
}

bool StackChanAvatarDisplay::SetCharacter(const std::string& character)
{
    auto& stackchan = GetStackChan();
    if (!stackchan.hasAvatar()) {
        return false;
    }

    DisplayLockGuard lock(this);

    auto emotion     = stackchan.avatar().getEmotion();
    lv_obj_t* panel  = nullptr;
    auto avatar      = CreateAvatar(character, &panel);
    if (!avatar) {
        return false;
    }
    // Same layer as the old face: above the boot screen, below the preview image and overlays
    if (avatar_panel_ && lv_obj_is_valid(avatar_panel_)) {
        lv_obj_move_to_index(panel, lv_obj_get_index(avatar_panel_));
    }
    stackchan.attachAvatar(std::move(avatar));
    avatar_panel_ = panel;
    stackchan.avatar().setEmotion(emotion);

    auto blink_modifier = static_cast<BlinkModifier*>(stackchan.getModifier(blink_modifier_id_));
    if (blink_modifier) {
        blink_modifier->resyncEyeWeights();
    }
    if (auto gestures = emotion_motion()) {
        gestures->nod();
    }
    ESP_LOGI(TAG, "Character: %s", character.c_str());
    return true;
}

std::string avatar_character::current()
{
    Settings settings("avatar", false);
    return settings.GetString("character", kDefaultCharacter);
}

bool avatar_character::head_gestures()
{
    Settings settings("avatar", false);
    return settings.GetBool("gestures", true);
}

void avatar_character::set_head_gestures(bool enabled)
{
    Settings settings("avatar", true);
    settings.SetBool("gestures", enabled);
    EmotionMotionModifier::setEnabled(enabled);
    ESP_LOGI(TAG, "Head gestures %s", enabled ? "on" : "off");
}

std::vector<std::string> avatar_character::names()
{
    std::vector<std::string> names = {kDefaultCharacter};
    for (auto& name : PokemonImages::characters()) {
        names.push_back(name);
    }
    return names;
}

/* ------------------------- held expressions and skill badges ------------------------- */

static std::string s_held_emotion;  // the last chat emotion ignored while an expression is held
static bool s_skill_active = false;
static lv_obj_t* s_badge   = nullptr;

static void hide_badge()
{
    if (!s_badge || lv_obj_has_flag(s_badge, LV_OBJ_FLAG_HIDDEN)) {
        return;
    }
    // Let the badge linger a moment, then fade it out
    lv_anim_t a;
    lv_anim_init(&a);
    lv_anim_set_var(&a, s_badge);
    lv_anim_set_values(&a, 255, 0);
    lv_anim_set_delay(&a, 900);
    lv_anim_set_duration(&a, 350);
    lv_anim_set_exec_cb(&a, [](void* obj, int32_t v) { lv_obj_set_style_opa((lv_obj_t*)obj, v, 0); });
    lv_anim_set_completed_cb(&a, [](lv_anim_t* anim) {
        auto obj = (lv_obj_t*)anim->var;
        lv_anim_delete(obj, nullptr);
        lv_obj_add_flag(obj, LV_OBJ_FLAG_HIDDEN);
    });
    lv_anim_start(&a);
}

static void show_badge(const lv_image_dsc_t* icon)
{
    if (!s_badge) {
        s_badge = lv_image_create(lv_screen_active());
        lv_obj_align(s_badge, LV_ALIGN_TOP_RIGHT, 2, -6);
        lv_obj_remove_flag(s_badge, LV_OBJ_FLAG_CLICKABLE);
        lv_image_set_pivot(s_badge, 56, 40);  // the badge's center in the sprite
    }
    lv_anim_delete(s_badge, nullptr);
    lv_obj_move_foreground(s_badge);  // above the face, which may have been replaced since
    lv_image_set_src(s_badge, icon);
    lv_obj_set_style_opa(s_badge, 255, 0);
    lv_obj_remove_flag(s_badge, LV_OBJ_FLAG_HIDDEN);

    // Pop in, like a move being used, then bob gently while the skill runs
    lv_anim_t pop;
    lv_anim_init(&pop);
    lv_anim_set_var(&pop, s_badge);
    lv_anim_set_values(&pop, 0, 256);
    lv_anim_set_duration(&pop, 380);
    lv_anim_set_path_cb(&pop, lv_anim_path_overshoot);
    lv_anim_set_exec_cb(&pop, [](void* obj, int32_t v) { lv_image_set_scale((lv_obj_t*)obj, v); });
    lv_anim_start(&pop);

    lv_anim_t bob;
    lv_anim_init(&bob);
    lv_anim_set_var(&bob, s_badge);
    lv_anim_set_values(&bob, -4, 4);
    lv_anim_set_duration(&bob, 900);
    lv_anim_set_reverse_duration(&bob, 900);
    lv_anim_set_repeat_count(&bob, LV_ANIM_REPEAT_INFINITE);
    lv_anim_set_path_cb(&bob, lv_anim_path_ease_in_out);
    lv_anim_set_exec_cb(&bob, [](void* obj, int32_t v) { lv_obj_set_style_translate_y((lv_obj_t*)obj, v, 0); });
    lv_anim_start(&bob);
}

// Ends a held expression or skill: hides the badge and applies the emotion the chat sent meanwhile.
// Call with the LVGL lock held.
static void release_hold()
{
    s_expression_until_us = 0;
    if (s_expression_timer) {
        esp_timer_stop(s_expression_timer);
    }
    if (s_skill_active) {
        s_skill_active = false;
        hide_badge();
    }
    std::string emotion = std::move(s_held_emotion);
    s_held_emotion.clear();
    if (s_display) {
        s_display->SetEmotion(emotion.empty() ? "neutral" : emotion.c_str());
    }
}

// Shows emotion and ignores the chat's emotions for us, or until release_hold(). LVGL lock held.
static void hold_emotion(Emotion emotion, int64_t us)
{
    if (!s_expression_timer) {
        esp_timer_create_args_t args = {};
        args.name                    = "expression";
        args.callback                = [](void*) {
            LvglLockGuard lock;
            if (s_expression_until_us) {
                release_hold();
            }
        };
        esp_timer_create(&args, &s_expression_timer);
    }
    esp_timer_stop(s_expression_timer);
    s_held_emotion.clear();
    s_expression_until_us = esp_timer_get_time() + us;
    GetStackChan().avatar().setEmotion(emotion);
    esp_timer_start_once(s_expression_timer, us);
}

// The badge for a tool call, or "" for tools that only change the robot itself
static std::string skill_icon(const std::string& tool)
{
    static const char* const quiet[] = {"self.robot.set_character", "self.robot.get_character",
                                        "self.robot.show_expression", "self.robot.set_head_angles",
                                        "self.robot.get_head_angles", "self.robot.set_led_color",
                                        "self.audio_speaker.",        "self.screen.",
                                        "self.get_device_status",     "self.get_system_info",
                                        "self.reboot",                "self.upgrade_firmware",
                                        "self.assets."};
    for (auto prefix : quiet) {
        if (tool.rfind(prefix, 0) == 0) {
            return "";
        }
    }
    auto has = [&tool](const char* part) { return tool.find(part) != std::string::npos; };
    if (has("muse")) return "muse";
    if (has("weather")) return "weather";
    if (has("news")) return "news";
    if (has("search")) return "search";
    if (has("reminder")) return "reminder";
    if (has("camera") || has("photo")) return "camera";
    return "sparkle";
}

// A tool call started ("% name..." from the chat): think, and show the skill's badge
static void skill_begin(const std::string& tool)
{
    auto key = skill_icon(tool);
    auto& stackchan = GetStackChan();
    if (key.empty() || !stackchan.hasAvatar()) {
        return;
    }
    ESP_LOGI(TAG, "Skill %s: %s", key.c_str(), tool.c_str());
    s_skill_active = true;
    hold_emotion(Emotion::Doubt, 90 * 1000000LL);  // safety: released by the answer or idle long before
    if (auto icon = PokemonImages::icon(key)) {
        show_badge(icon);
    }
}

bool avatar_character::show_expression(const std::string& expression, int seconds)
{
    static const char* const names[] = {"neutral", "happy", "angry", "sad", "doubt", "sleepy", "cool"};
    int index                        = -1;
    for (int i = 0; i < 7; i++) {
        if (expression == names[i]) {
            index = i;
        }
    }
    auto& stackchan = GetStackChan();
    if (index < 0 || !stackchan.hasAvatar()) {
        return false;
    }

    seconds = std::clamp(seconds, 1, 30);
    {
        LvglLockGuard lock;
        s_skill_active = false;
        hide_badge();
        hold_emotion((Emotion)index, seconds * 1000000LL);
    }
    ESP_LOGI(TAG, "Expression %s for %d s", expression.c_str(), seconds);
    return true;
}

bool avatar_character::set(const std::string& name)
{
    if (name != kDefaultCharacter && !PokemonImages::exists(name)) {
        return false;
    }
    if (!s_display || !s_display->SetCharacter(name)) {
        return false;
    }
    Settings settings("avatar", true);
    settings.SetString("character", name);
    return true;
}

static void print_memory(const char* when)
{
    ESP_LOGI(TAG, "mem %s: internal %u (largest %u), psram %u (largest %u)", when,
             (unsigned)heap_caps_get_free_size(MALLOC_CAP_INTERNAL),
             (unsigned)heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL),
             (unsigned)heap_caps_get_free_size(MALLOC_CAP_SPIRAM),
             (unsigned)heap_caps_get_largest_free_block(MALLOC_CAP_SPIRAM));
}

// Prints what LVGL renders, as "@snap W H" then hex lines of RGB565 (little endian), then "@snap end"
static void print_snapshot()
{
    lv_draw_buf_t* snap = nullptr;
    {
        LvglLockGuard lock;
        snap = lv_snapshot_take(lv_screen_active(), LV_COLOR_FORMAT_RGB565);
    }
    if (!snap) {
        printf("@snap error\n");
        return;
    }
    int w = snap->header.w, h = snap->header.h, stride = snap->header.stride;
    printf("@snap %d %d\n", w, h);
    static const char hex[] = "0123456789abcdef";
    char line[2 * 160 + 2];
    for (int y = 0; y < h; y++) {
        const uint8_t* row = snap->data + y * stride;
        for (int off = 0; off < w * 2; off += 160) {
            int n = std::min(160, w * 2 - off);
            for (int i = 0; i < n; i++) {
                line[2 * i]     = hex[row[off + i] >> 4];
                line[2 * i + 1] = hex[row[off + i] & 15];
            }
            line[2 * n]     = '\n';
            line[2 * n + 1] = 0;
            fputs(line, stdout);
        }
        vTaskDelay(1);
    }
    printf("@snap end\n");
    fflush(stdout);
    lv_draw_buf_destroy(snap);
}

// Debug console commands: ">face=NAME", ">say=TEXT", ">expr=NAME", ">move=NAME", ">head", ">gestures=on|off",
// ">snap", ">mem"
static bool on_console_command(const char* line)
{
    std::string cmd(line);
    if (cmd.rfind("face=", 0) == 0) {
        auto name = cmd.substr(5);
        Application::GetInstance().Schedule([name]() {
            print_memory("before");
            bool ok = avatar_character::set(name);
            print_memory("after");
            printf("@face %s %s\n", name.c_str(), ok ? "ok" : "error");
            fflush(stdout);
        });
        return true;
    }
    // ">say=TEXT" plays an assistant message, e.g. ">say=% weather_forecast..." starts a skill
    if (cmd.rfind("say=", 0) == 0) {
        auto text = cmd.substr(4);
        Application::GetInstance().Schedule([text]() {
            if (s_display) {
                s_display->SetChatMessage("assistant", text.c_str());
            }
            printf("@say shown\n");
            fflush(stdout);
        });
        return true;
    }
    if (cmd.rfind("expr=", 0) == 0) {
        bool ok = avatar_character::show_expression(cmd.substr(5), 20);
        printf("@expr %s\n", ok ? "ok" : "error");
        fflush(stdout);
        return true;
    }
    // ">move=NAME" plays a head gesture now: neutral, happy, angry, sad, doubt, sleepy, cool, nod
    if (cmd.rfind("move=", 0) == 0) {
        auto name = cmd.substr(5);
        LvglLockGuard lock;
        auto gestures = emotion_motion();
        if (gestures) {
            gestures->test(name.c_str());
        }
        printf("@move %s %s\n", name.c_str(), gestures ? "ok" : "error");
        fflush(stdout);
        return true;
    }
    // ">head" prints the servo angles (0.1 degree)
    if (cmd == "head") {
        LvglLockGuard lock;
        auto angles = GetStackChan().motion().getCurrentAngles();
        printf("@head %d %d\n", angles.x, angles.y);
        fflush(stdout);
        return true;
    }
    // ">gestures=on" / ">gestures=off"
    if (cmd.rfind("gestures=", 0) == 0) {
        bool on = cmd.substr(9) == "on";
        avatar_character::set_head_gestures(on);
        printf("@gestures %s\n", on ? "on" : "off");
        fflush(stdout);
        return true;
    }
    if (cmd == "snap") {
        Application::GetInstance().Schedule([]() { print_snapshot(); });
        return true;
    }
    if (cmd == "mem") {
        print_memory("now");
        PokemonImages::debugCheck();
        return true;
    }
    return false;
}

void StackChanAvatarDisplay::LvglLock()
{
    if (!Lock(30000)) {
        ESP_LOGE("Display", "Failed to lock display");
    }
}

void StackChanAvatarDisplay::LvglUnlock()
{
    Unlock();
}

void StackChanAvatarDisplay::CreateIdleMotionModifier()
{
    auto& stackchan = GetStackChan();

    switch (idle_motion_level_) {
        case 0:
            idle_motion_modifier_id_ = -1;
            return;
        case 1:
            idle_motion_modifier_id_ = stackchan.addModifier(std::make_unique<IdleMotionModifier>(8000, 12000));
            return;
        case 3:
            idle_motion_modifier_id_ = stackchan.addModifier(std::make_unique<IdleMotionModifier>(2000, 4000));
            return;
        case 2:
        default:
            idle_motion_modifier_id_ = stackchan.addModifier(std::make_unique<IdleMotionModifier>());
            return;
    }
}

void StackChanAvatarDisplay::SetEmotion(const char* emotion)
{
    auto& stackchan = GetStackChan();

    if (!stackchan.hasAvatar() || !emotion) {
        return;
    }

    DisplayLockGuard lock(this);

    if (esp_timer_get_time() < s_expression_until_us) {
        ESP_LOGI(TAG, "SetEmotion: %s (holding an expression)", emotion);
        s_held_emotion = emotion;
        return;
    }
    ESP_LOGI(TAG, "SetEmotion: %s", emotion);

    auto& avatar = stackchan.avatar();

    // Map emotion string to stackchan::Emotion
    if (strcmp(emotion, "neutral") == 0) {
        avatar.setEmotion(Emotion::Neutral);
    } else if (strcmp(emotion, "happy") == 0) {
        avatar.setEmotion(Emotion::Happy);
    } else if (strcmp(emotion, "laughing") == 0) {
        avatar.setEmotion(Emotion::Happy);
    } else if (strcmp(emotion, "angry") == 0) {
        avatar.setEmotion(Emotion::Angry);
    } else if (strcmp(emotion, "sad") == 0) {
        avatar.setEmotion(Emotion::Sad);
    } else if (strcmp(emotion, "crying") == 0) {
        avatar.setEmotion(Emotion::Sad);
    } else if (strcmp(emotion, "sleepy") == 0) {
        avatar.setEmotion(Emotion::Sleepy);
        avatar.setSpeech("Zzz…");
        is_sleeping_ = true;
        // avatar.mouth().setWeight(10);

        // Stop idle motion
        ESP_LOGW(TAG, "Stop idle motion");
        if (idle_motion_modifier_id_ >= 0) {
            stackchan.removeModifier(idle_motion_modifier_id_);
            idle_motion_modifier_id_ = -1;
            stackchan.removeModifier(idle_expression_modifier_id_);
            idle_expression_modifier_id_ = -1;
        }

        // Return to default pose
        auto& motion = GetStackChan().motion();
        motion.pitchServo().moveWithSpeed(0, 80);

    } else if (strcmp(emotion, "funny") == 0 || strcmp(emotion, "loving") == 0 ||
               strcmp(emotion, "relaxed") == 0 || strcmp(emotion, "delicious") == 0 ||
               strcmp(emotion, "kissy") == 0 || strcmp(emotion, "silly") == 0) {
        avatar.setEmotion(Emotion::Happy);
    } else if (strcmp(emotion, "surprised") == 0 || strcmp(emotion, "shocked") == 0 ||
               strcmp(emotion, "thinking") == 0 || strcmp(emotion, "confused") == 0) {
        avatar.setEmotion(Emotion::Doubt);
    } else if (strcmp(emotion, "embarrassed") == 0) {
        avatar.setEmotion(Emotion::Sad);
    } else if (strcmp(emotion, "cool") == 0 || strcmp(emotion, "confident") == 0 ||
               strcmp(emotion, "winking") == 0) {
        avatar.setEmotion(Emotion::Cool);
    } else if (strcmp(emotion, "doubtful") == 0) {
        avatar.setEmotion(Emotion::Doubt);
    } else {
        ESP_LOGW(TAG, "Unknown emotion: %s, using NEUTRAL", emotion);
        avatar.setEmotion(Emotion::Neutral);
    }

    // Resync blink modifier base eye weights
    auto blink_modifier = static_cast<BlinkModifier*>(stackchan.getModifier(blink_modifier_id_));
    if (blink_modifier) {
        blink_modifier->resyncEyeWeights();
    }
}

void StackChanAvatarDisplay::SetChatMessage(const char* role, const char* content)
{
    if (!setup_ui_called_) {
        ESP_LOGW(TAG, "SetChatMessage('%s', '%s') called before SetupUI() - message will be lost!", role, content);
    }

    auto& stackchan = GetStackChan();
    if (!stackchan.hasAvatar()) {
        return;
    }

    // ESP_LOGE(TAG, "SetChatMessage: role=%s, content=%s", role ? role : "null", content ? content : "null");

    DisplayLockGuard lock(this);

    // Spoken replies aren't shown: the mouth moves while speaking. A tool call ("% name...") shows a
    // skill badge and a thinking face until the answer starts. System messages (e.g. activation codes)
    // still use the speech bubble.
    if (strcmp(role, "system") == 0) {
        stackchan.avatar().setSpeech(content);
    } else if (strcmp(role, "assistant") == 0) {
        if (content[0] == '%' && content[1] == ' ') {
            std::string tool(content + 2);
            auto end = tool.find("...");
            skill_begin(tool.substr(0, end));
        } else if (s_skill_active) {
            release_hold();
        }
    }
}

void StackChanAvatarDisplay::ClearChatMessages()
{
    auto& stackchan = GetStackChan();
    if (!stackchan.hasAvatar()) {
        return;
    }

    DisplayLockGuard lock(this);

    stackchan.avatar().clearSpeech();
    if (s_skill_active) {
        release_hold();
    }

    ESP_LOGI(TAG, "Chat messages cleared");
}

void StackChanAvatarDisplay::SetPreviewImage(std::unique_ptr<LvglImage> image)
{
    DisplayLockGuard lock(this);
    if (preview_image_ == nullptr) {
        return;
    }

    if (image == nullptr) {
        esp_timer_stop(preview_timer_);
        lv_obj_add_flag(preview_image_, LV_OBJ_FLAG_HIDDEN);
        preview_image_cached_.reset();
        return;
    }

    preview_image_cached_ = std::move(image);
    auto img_dsc          = preview_image_cached_->image_dsc();
    // Set image source and show preview image
    lv_image_set_src(preview_image_, img_dsc);
    if (img_dsc->header.w > 0 && img_dsc->header.h > 0) {
        // Scale to fit width
        lv_image_set_scale(preview_image_, 256 * width_ / img_dsc->header.w);
    }

    lv_obj_remove_flag(preview_image_, LV_OBJ_FLAG_HIDDEN);
    lv_obj_move_foreground(preview_image_);
    esp_timer_stop(preview_timer_);
    ESP_ERROR_CHECK(esp_timer_start_once(preview_timer_, 6000 * 1000));
}

void StackChanAvatarDisplay::UpdateStatusBar(bool update_all)
{
}

void StackChanAvatarDisplay::SetTheme(Theme* theme)
{
    ESP_LOGI(TAG, "SetTheme: %s", theme->name().c_str());

    auto& stackchan = GetStackChan();
    if (!stackchan.hasAvatar()) {
        ESP_LOGE(TAG, "Avatar is invalid");
        return;
    }

    DisplayLockGuard lock(this);

    auto lvgl_theme = static_cast<LvglTheme*>(theme);
    auto text_font  = lvgl_theme->text_font()->font();

    stackchan.avatar().setSpeechTextFont((void*)text_font);
}

#include <hal/board/hal_bridge.h>
static bool _is_xiaozhi_ready = false;
static bool _is_xiaozhi_idle  = false;
bool hal_bridge::is_xiaozhi_ready()
{
    return _is_xiaozhi_ready;
}
bool hal_bridge::is_xiaozhi_idle()
{
    return _is_xiaozhi_idle;
}

void StackChanAvatarDisplay::SetStatus(const char* status)
{
    // ESP_LOGE(TAG, "SetStatus: %s", status);

    auto& stackchan = GetStackChan();
    if (!stackchan.hasAvatar()) {
        ESP_LOGE(TAG, "Avatar is invalid");
        return;
    }

    auto& avatar = stackchan.avatar();
    auto& motion = stackchan.motion();

    DisplayLockGuard lock(this);

    bool is_idle      = false;
    bool is_listening = false;

    if (strcmp(status, Lang::Strings::LISTENING) == 0) {
        if (speaking_modifier_id_ >= 0) {
            // Start speaking
            stackchan.removeModifier(speaking_modifier_id_);
            avatar.mouth().setWeight(0);
            speaking_modifier_id_ = -1;
        }

        GetHAL().setRgbColor(0, 0, 50, 0);
        GetHAL().refreshRgb();

    } else if (strcmp(status, Lang::Strings::STANDBY) == 0) {
        _is_xiaozhi_ready = true;

        if (speaking_modifier_id_ >= 0) {
            // Stop speaking
            stackchan.removeModifier(speaking_modifier_id_);
            avatar.mouth().setWeight(0);
            speaking_modifier_id_ = -1;
        }

        is_idle = true;

        GetHAL().setRgbColor(0, 0, 0, 0);
        GetHAL().refreshRgb();

    } else if (strcmp(status, Lang::Strings::SPEAKING) == 0) {
        if (speaking_modifier_id_ < 0) {
            speaking_modifier_id_ = stackchan.addModifier(std::make_unique<SpeakingModifier>(0, 180, false));
            if (auto gestures = emotion_motion()) {
                gestures->replyStarted();
            }
        }

        GetHAL().setRgbColor(0, 0, 0, 50);
        GetHAL().refreshRgb();
    } else {
        avatar.setSpeech(status);
    }

    if (is_idle) {
        // Start idle motion
        ESP_LOGW(TAG, "Start idle motion");
        if (idle_motion_modifier_id_ < 0) {
            if (idle_motion_level_ > 0) {
                CreateIdleMotionModifier();
            }
            idle_expression_modifier_id_ = stackchan.addModifier(std::make_unique<IdleExpressionModifier>());
        }

        _is_xiaozhi_idle = true;
        EmotionMotionModifier::setInConversation(false);
    } else {
        // Stop idle motion
        ESP_LOGW(TAG, "Stop idle motion");
        if (idle_motion_modifier_id_ >= 0) {
            stackchan.removeModifier(idle_motion_modifier_id_);
            idle_motion_modifier_id_ = -1;
            stackchan.removeModifier(idle_expression_modifier_id_);
            idle_expression_modifier_id_ = -1;
        }

        // if (!is_listening) {
        //     // Return to default pose
        //     motion.pitchServo().moveWithSpeed(200, 350);
        //     motion.yawServo().moveWithSpeed(0, 350);
        // }

        _is_xiaozhi_idle = false;
        EmotionMotionModifier::setInConversation(true);
    }

    // Clear sleep state
    if (is_sleeping_) {
        avatar.setSpeech("");
    }
}

void StackChanAvatarDisplay::ShowNotification(const char* notification, int duration_ms)
{
}
