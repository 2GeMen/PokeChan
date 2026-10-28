/*
 * PokeChan: head gestures that follow the face's emotion.
 *
 * SPDX-License-Identifier: MIT
 */
#pragma once
#include "../modifiable.h"
#include "../utils/random.h"
#include <smooth_ui_toolkit.hpp>
#include <hal/hal.h>
#include <atomic>
#include <cstdint>
#include <string>
#include <vector>

namespace stackchan {

/**
 * @brief Moves the head when the face's emotion changes: a nod when happy, a shake and a glare when
 * angry, chin up and a turn when cool, a look up toward the skill badge while thinking, and so on.
 *
 * It watches avatar().getEmotion(), so every way an emotion is set (the chat's emotions,
 * show_expression, skills) gets a gesture without extra hooks. Gestures are small (5-16 degrees),
 * only start when the emotion changes, and never fight a locked or already moving head.
 * Held gestures (angry, cool, sad, sleepy, thinking) stay until the emotion changes, then the head
 * goes back to where it was.
 */
class EmotionMotionModifier : public Modifier {
public:
    struct Key {
        uint16_t t;       // ms from the gesture start
        int16_t yaw;      // offset from the base pose, 0.1 degree; negative is the robot's left
        int16_t pitch;    // offset, 0.1 degree; positive is up
        uint16_t speed;   // 0-1000
    };

    // While a gesture plays the update loop should run at full rate (see hal.cpp)
    static inline std::atomic<uint32_t> busy_until_ms{0};

    static void setEnabled(bool enabled)
    {
        _enabled = enabled;
    }
    static bool isEnabled()
    {
        return _enabled;
    }

    // Gestures follow emotions only during a conversation; when idle, IdleMotionModifier owns the head
    static void setInConversation(bool on)
    {
        _in_conversation = on;
    }

    EmotionMotionModifier()
    {
        _last_gesture_ms = GetHAL().millis();
    }

    // A quick nod, e.g. after switching characters
    void nod()
    {
        _pending_nod = true;
    }

    // Plays the gesture for an emotion now, for testing ("neutral", "happy", ..., "nod")
    void test(const char* name)
    {
        _pending_test = name;
    }

    void _update(Modifiable& stackchan) override
    {
        if (!stackchan.hasAvatar()) {
            return;
        }
        uint32_t now = GetHAL().millis();
        auto emotion = stackchan.avatar().getEmotion();

        if (!_pending_test.empty()) {
            auto name = std::move(_pending_test);
            _pending_test.clear();
            if (name == "nod") {
                start(stackchan, nod_keys(), false, now, From::Test);
            } else {
                for (int i = 0; i < 7; i++) {
                    if (name == kNames[i]) {
                        apply(stackchan, (avatar::Emotion)i, now, true);
                    }
                }
            }
        } else if (_pending_nod) {
            _pending_nod = false;
            if (_enabled && !_holding && _keys.empty()) {
                start(stackchan, nod_keys(), false, now);
            }
        } else if (emotion != _last_emotion) {
            if (_enabled) {
                apply(stackchan, emotion, now, false);
            }
        }
        _last_emotion = emotion;

        play(stackchan, now);
    }

private:
    static inline bool _enabled         = true;
    static inline bool _in_conversation = false;
    static constexpr const char* kNames[7] = {"neutral", "happy", "angry", "sad", "doubt", "sleepy", "cool"};

    static bool held(avatar::Emotion e)
    {
        return e == avatar::Emotion::Angry || e == avatar::Emotion::Cool || e == avatar::Emotion::Sad ||
               e == avatar::Emotion::Sleepy || e == avatar::Emotion::Doubt;
    }

    static std::vector<Key> nod_keys()
    {
        return {{0, 0, -70, 900}, {260, 0, 0, 500}};
    }

    static std::vector<Key> keys_for(avatar::Emotion e)
    {
        switch (e) {
            case avatar::Emotion::Happy:  // two quick nods
                return {{0, 0, 90, 900}, {260, 0, -10, 900}, {520, 0, 80, 900}, {780, 0, 0, 500}};
            case avatar::Emotion::Angry:  // shake, then glare a little downward
                return {{0, 90, 0, 1000}, {230, -90, 0, 1000}, {460, 70, 0, 1000}, {690, -50, 0, 1000},
                        {920, 0, -50, 450}};
            case avatar::Emotion::Cool:  // chin up, turn away a bit
                return {{0, 160, 90, 350}};
            case avatar::Emotion::Sad:  // head down, slightly away
                return {{0, -80, -100, 150}};
            case avatar::Emotion::Sleepy:  // slow droop
                return {{0, 0, -120, 100}};
            case avatar::Emotion::Doubt:  // look up toward the skill badge (top right of the screen,
                                          // which is the robot's left)
                return {{0, -80, 60, 300}};
            default:
                return {};
        }
    }

    // The gesture for a new emotion. test: from the console, so no cooldown, chance or idle check.
    void apply(Modifiable& stackchan, avatar::Emotion to, uint32_t now, bool test)
    {
        // Leaving a held gesture: back to where the head was (a following gesture starts from there)
        bool was_holding = _holding;
        if (_holding) {
            _holding     = false;
            auto& motion = stackchan.motion();
            if (!motion.isModifyLocked()) {
                motion.moveWithSpeed(_base_yaw, _base_pitch, 250);
                busy_until_ms = now + 800;
            }
        }
        if (!_in_conversation && !test) {
            return;
        }
        auto keys = keys_for(to);
        if (keys.empty()) {
            return;
        }
        if (!test) {
            // The chat sends "happy" for most replies: nod sometimes, not every time
            if (to == avatar::Emotion::Happy) {
                if (now - _last_gesture_ms < 6000 || Random::getInstance().getInt(0, 99) >= 60) {
                    return;
                }
            } else if (now - _last_gesture_ms < 1500) {
                return;
            }
        }
        start(stackchan, std::move(keys), held(to), now, was_holding ? From::Base : test ? From::Test : From::Here);
    }

    // Here: from where the head is now, skipped if something else is moving it.
    // Base: from the saved pose (the head is on its way back there from a held gesture).
    // Test: like Here, but never skipped.
    enum class From { Here, Base, Test };

    void start(Modifiable& stackchan, std::vector<Key> keys, bool hold, uint32_t now, From from = From::Here)
    {
        auto& motion = stackchan.motion();
        // Someone else owns the head (picked up, petted, dancing)
        if (keys.empty() || motion.isModifyLocked()) {
            return;
        }
        // While one of our gestures plays or holds, the base pose is still the right one
        bool keep_base = from == From::Base || _holding || !_keys.empty();
        if (!keep_base) {
            if (from == From::Here && motion.isMoving()) {
                return;  // another modifier or a tool is moving the head
            }
            auto angles = motion.getCurrentAngles();
            _base_yaw   = angles.x;
            _base_pitch = angles.y;
        }
        _holding         = false;
        _keys            = std::move(keys);
        _next            = 0;
        _start_ms        = now;
        _hold            = hold;
        _last_gesture_ms = now;
        busy_until_ms    = now + _keys.back().t + 700;
    }

    void play(Modifiable& stackchan, uint32_t now)
    {
        if (_next >= _keys.size()) {
            return;
        }
        auto& motion = stackchan.motion();
        if (motion.isModifyLocked()) {
            _keys.clear();
            _next = 0;
            return;
        }
        while (_next < _keys.size() && now - _start_ms >= _keys[_next].t) {
            auto& k   = _keys[_next++];
            int yaw   = uitk::clamp(_base_yaw + k.yaw, -600, 600);
            int pitch = uitk::clamp(_base_pitch + k.pitch, 0, 650);
            motion.moveWithSpeed(yaw, pitch, k.speed);
        }
        if (_next >= _keys.size()) {
            _holding = _hold;
            _keys.clear();
            _next = 0;
        }
    }

    avatar::Emotion _last_emotion = avatar::Emotion::Neutral;
    std::vector<Key> _keys;
    size_t _next              = 0;
    uint32_t _start_ms        = 0;
    uint32_t _last_gesture_ms = 0;
    bool _hold                = false;
    bool _holding             = false;
    int _base_yaw             = 0;
    int _base_pitch           = 0;
    volatile bool _pending_nod = false;
    std::string _pending_test;
};

}  // namespace stackchan
