/*
 * Pokémon avatar skins: a face background plus eye and mouth sprites for each emotion, drawn by
 * tools/pokemon_faces/gen_faces.py and embedded as PNG. Eyes and mouths are Features, so blink,
 * speaking, breathing and idle modifiers drive them the same way as the default face.
 */
#pragma once
#include "../../avatar/avatar.h"
#include "../../avatar/elements/feature.h"
#include <lvgl.h>
#include <smooth_lvgl.hpp>
#include <memory>
#include <string>
#include <vector>

namespace stackchan::avatar {

/**
 * @brief Decoded images of one character, in PSRAM
 *
 */
class PokemonImages {
public:
    static constexpr int kEmotions    = 7;  // avatar::Emotion values
    static constexpr int kEyeStates   = kEmotions + 1;  // emotions, then closed
    static constexpr int kMouthStates = kEmotions + 2;  // emotions, then talking small and large
    static constexpr int kEyeClosed   = kEmotions;
    static constexpr int kMouthTalkS  = kEmotions;
    static constexpr int kMouthTalkL  = kEmotions + 1;

    // An animated layer (Charmander's flame, Pikachu's sparks, Squirtle's sunglasses)
    struct FxLayer {
        int x       = 0;
        int y       = 0;
        bool behind = false;
        std::vector<lv_image_dsc_t> frames[kEmotions + 1];  // per emotion, then "any"

        const std::vector<lv_image_dsc_t>& framesFor(int emotion) const
        {
            return frames[emotion].empty() ? frames[kEmotions] : frames[emotion];
        }
    };

    /**
     * @brief Decodes all images of a character; returns null for an unknown name or a decode failure.
     *        Takes a few hundred ms; does not touch LVGL objects, so it can run without the LVGL lock.
     */
    static std::shared_ptr<PokemonImages> load(const std::string& character);
    static bool exists(const std::string& character);
    static std::vector<std::string> characters();
    // Logs the latest loaded background's header and checksum
    static void debugCheck();

    ~PokemonImages();

    lv_image_dsc_t bg;
    uint32_t backdrop = 0;  // 0xRRGGBB behind a cut-out background
    lv_image_dsc_t eyes[kEyeStates][2];  // [state][0 = screen left, 1 = screen right]
    lv_image_dsc_t mouths[kMouthStates];
    std::vector<FxLayer> fx;

private:
    PokemonImages() = default;
    std::vector<void*> _buffers;
};

class PokemonAvatar : public Avatar {
public:
    void init(lv_obj_t* parent, std::shared_ptr<PokemonImages> images,
              const lv_font_t* font = &lv_font_montserrat_16);
    uitk::lvgl_cpp::Container* getPanel() const;
    void update() override;

    ~PokemonAvatar();

private:
    std::shared_ptr<PokemonImages> _images;
    std::unique_ptr<uitk::lvgl_cpp::Container> _pannel;
    lv_obj_t* _bg = nullptr;
    std::vector<lv_obj_t*> _fx;
    uint32_t _fx_tick  = 0;
    uint32_t _fx_frame = 0;
};

class PokemonEye : public Feature {
public:
    PokemonEye(lv_obj_t* parent, std::shared_ptr<PokemonImages> images, bool isLeftEye);
    ~PokemonEye();

    void setPosition(const uitk::Vector2i& position) override;
    void setWeight(int weight) override;
    void setEmotion(const Emotion& emotion) override;
    Emotion getEmotion() const override;
    void setVisible(bool visible) override;
    void setSize(int size) override;

private:
    void refresh();

    std::shared_ptr<PokemonImages> _images;
    bool _is_left_eye = false;
    Emotion _emotion  = Emotion::Neutral;
    lv_obj_t* _img    = nullptr;
};

class PokemonMouth : public Feature {
public:
    PokemonMouth(lv_obj_t* parent, std::shared_ptr<PokemonImages> images);
    ~PokemonMouth();

    void setPosition(const uitk::Vector2i& position) override;
    void setWeight(int weight) override;
    void setRotation(int rotation) override;
    void setEmotion(const Emotion& emotion) override;
    Emotion getEmotion() const override;
    void setVisible(bool visible) override;

private:
    void refresh();

    std::shared_ptr<PokemonImages> _images;
    Emotion _emotion = Emotion::Neutral;
    lv_obj_t* _img   = nullptr;
};

}  // namespace stackchan::avatar
