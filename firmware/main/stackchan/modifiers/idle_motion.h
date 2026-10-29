/*
 * SPDX-FileCopyrightText: 2026 M5Stack Technology CO LTD
 *
 * SPDX-License-Identifier: MIT
 */
#pragma once
#include "../modifiable.h"
#include "../utils/random.h"
#include <smooth_ui_toolkit.hpp>
// #include <mooncake_log.h>
#include <hal/hal.h>
#include <cstdint>
#include <ctime>
#include <iterator>
#include <memory>

namespace stackchan {

/**
 * @brief Head motion while xiaozhi is idle.
 *
 * Random: a move every interval_min..interval_max ms (the original behavior).
 * Hourly: the head settles in the rest pose and stays still, then looks around
 * once on the hour, during the day only, so it doesn't disturb anyone.
 */
class IdleMotionModifier : public Modifier {
public:
    static constexpr int REST_PITCH  = 200;  // looking ahead
    static constexpr int QUIET_FROM  = 23;   // hourly: no motion from 23:00 ...
    static constexpr int QUIET_UNTIL = 7;    // ... until 07:00 (local time)

    IdleMotionModifier(uint32_t interval_min = 4000, uint32_t interval_max = 8000)
        : _interval_min(interval_min), _interval_max(interval_max)
    {
        _next_tick = GetHAL().millis() + 1000;  // 启动 1 秒后开始第一次动作
    }

    static std::unique_ptr<IdleMotionModifier> hourly()
    {
        auto m     = std::make_unique<IdleMotionModifier>();
        m->_hourly = true;
        return m;
    }

    void pause()
    {
        _paused = true;
    }
    void resume()
    {
        if (_paused) {
            _paused    = false;
            _next_tick = GetHAL().millis() + 500;
        }
    }

    void _update(Modifiable& stackchan) override
    {
        if (_paused || !stackchan.hasAvatar()) return;

        uint32_t now = GetHAL().millis();

        if (_hourly) {
            update_hourly(stackchan, now);
            return;
        }

        // 如果时间没到，直接跳过
        if (now < _next_tick) {
            return;
        }

        // 如果上次动作还没做完，就把下一次尝试推迟 500ms，避免指令堆积
        if (stackchan.motion().isMoving()) {
            _next_tick = now + 500;
            return;
        }

        // 执行动作
        perform_idle_motion(stackchan);

        // 算下一次的时间间隔
        uint32_t delay = Random::getInstance().getInt(_interval_min, _interval_max);
        _next_tick     = now + delay;
        // mclog::info("next idle motion in {} ms", delay);
    }

private:
    struct Step {
        uint16_t t;  // ms from the start of the look-around
        int16_t yaw;
        int16_t pitch;
        uint16_t speed;
    };
    // Left, right, up, then back to rest: about 5 s, at gentle speeds.
    static constexpr Step LOOK_AROUND[] = {
        {0, -350, 320, 200}, {1500, 350, 320, 200}, {3000, 0, 480, 200}, {4300, 0, REST_PITCH, 150}};

    // Local hour (0-23), or -1 until SNTP has set the clock.
    static int local_hour()
    {
        time_t t = time(nullptr);
        if (!GetHAL().timeSynced() || t < 1735689600) {  // 2025-01-01
            return -1;
        }
        struct tm tm;
        localtime_r(&t, &tm);
        return tm.tm_hour;
    }

    void update_hourly(Modifiable& stackchan, uint32_t now)
    {
        auto& motion = stackchan.motion();
        if (now < _next_tick || motion.isModifyLocked()) {
            return;
        }
        if (!_rested) {
            // Settle once when idle starts, then keep still.
            motion.moveWithSpeed(0, REST_PITCH, 150);
            _rested    = true;
            _last_hour = local_hour();
            _next_tick = now + 1000;
            return;
        }
        if (_step >= 0) {
            const Step& k = LOOK_AROUND[_step];
            if (now - _look_start < k.t) {
                return;
            }
            motion.moveWithSpeed(k.yaw, k.pitch, k.speed);
            _step = _step + 1 < (int)std::size(LOOK_AROUND) ? _step + 1 : -1;
            return;
        }
        // On the hour: checked once a second.
        _next_tick = now + 1000;
        int hour   = local_hour();
        if (hour < 0 || hour == _last_hour) {
            return;
        }
        bool first = _last_hour < 0;  // the clock just got set: not an hour turning
        _last_hour = hour;
        if (first || hour >= QUIET_FROM || hour < QUIET_UNTIL) {
            return;
        }
        _step       = 0;
        _look_start = now;
        _next_tick  = now;
    }

    void perform_idle_motion(Modifiable& stackchan)
    {
        auto& motion = stackchan.motion();
        if (motion.isModifyLocked()) {
            return;
        }

        int action = Random::getInstance().getInt(0, 100);

        if (action < 50) {
            // 【动作 1：随意环视】使用归一化坐标 (-1.0 ~ 1.0)
            float target_x = Random::getInstance().getFloat(-0.4f, 0.4f);   // 左右看
            float target_y = Random::getInstance().getFloat(-0.95f, 0.2f);  // 上下看
            int speed      = Random::getInstance().getInt(150, 300);

            // mclog::info("action 1: look at normalized ({}, {}) in speed {}", target_x, target_y, speed);
            motion.lookAtNormalized(target_x, target_y, speed);
        } else if (action < 80) {
            // 【动作 2：微小的观察动作】基于当前位置的小偏移
            auto current = motion.getCurrentAngles();  // Vector2i(yaw, pitch)

            int diff_yaw   = Random::getInstance().getInt(-150, 150);
            int diff_pitch = Random::getInstance().getInt(-80, 80);

            int target_yaw   = uitk::clamp(current.x + diff_yaw, -800, 800);
            int target_pitch = uitk::clamp(current.y + diff_pitch, 0, 600);
            int speed        = Random::getInstance().getInt(100, 250);

            // mclog::info("action 2: small move to ({}, {}) in speed {}", target_yaw, target_pitch, speed);
            motion.moveWithSpeed(target_yaw, target_pitch, speed);
        } else if (action < 90) {
            // 【动作 3：快速撇一眼】速度快，跨度中等
            int target_yaw   = Random::getInstance().getInt(-500, 500);
            int target_pitch = Random::getInstance().getInt(100, 400);
            int speed        = Random::getInstance().getInt(250, 400);

            // mclog::info("action 3: quick glance to ({}, {}) in speed {}", target_yaw, target_pitch, speed);
            motion.moveWithSpeed(target_yaw, target_pitch, speed);
        } else {
            // 【动作 4：yaw 回正】
            int target_pitch = Random::getInstance().getInt(50, 400);
            int speed        = Random::getInstance().getInt(100, 300);

            // mclog::info("action 4: go home to (0, {}) in speed {}", target_pitch, speed);
            motion.moveWithSpeed(0, target_pitch, speed);
        }
    }

    uint32_t _interval_min;
    uint32_t _interval_max;
    uint32_t _next_tick = 0;
    bool _paused        = false;

    bool _hourly         = false;
    bool _rested         = false;
    int _last_hour       = -1;
    int _step            = -1;  // in LOOK_AROUND, -1: not looking around
    uint32_t _look_start = 0;
};

}  // namespace stackchan
