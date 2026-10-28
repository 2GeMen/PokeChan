/*
 * Pokémon avatar skins; see pokemon.h.
 */
#include "pokemon.h"
#include "pokemon_assets.h"
#include "../default/default.h"
#include <esp_heap_caps.h>
#include <esp_log.h>
#include <esp_timer.h>
#include <cstring>

using namespace uitk;
using namespace uitk::lvgl_cpp;
using namespace stackchan::avatar;

// From LVGL's lodepng (LV_USE_LODEPNG); its header can't be included from C++ here. LVGL's copy returns
// an lv_draw_buf_t (RGBA bytes, stride per row) through out, not a plain pixel array.
extern "C" unsigned lodepng_decode32(unsigned char** out, unsigned* w, unsigned* h, const unsigned char* in,
                                     size_t insize);

static const char* TAG = "PokemonAvatar";

static std::weak_ptr<PokemonImages> s_last_images;

static uint32_t checksum(const lv_image_dsc_t& dsc)
{
    uint32_t sum = 0;
    for (uint32_t i = 0; i < dsc.data_size; i++) {
        sum = sum * 31 + dsc.data[i];
    }
    return sum;
}

void PokemonImages::debugCheck()
{
    auto images = s_last_images.lock();
    if (!images) {
        ESP_LOGI(TAG, "check: no images");
        return;
    }
    const auto& bg = images->bg;
    ESP_LOGI(TAG, "check: bg %p cf %d %dx%d stride %d size %u sum %08x first %02x%02x%02x%02x", bg.data,
             bg.header.cf, bg.header.w, bg.header.h, bg.header.stride, (unsigned)bg.data_size,
             (unsigned)checksum(bg), bg.data[0], bg.data[1], bg.data[2], bg.data[3]);
}

// Layout in pixels from the screen center; must match tools/pokemon_faces/gen_faces.py
static const int _eye_dx       = 62;
static const int _eye_y        = -20;
static const int _mouth_y      = 32;
static const int _eye_offset   = 12;  // how far eyes move for position -100..100
static const int _mouth_offset = 10;

static const char* const _emotion_names[] = {"neutral", "happy", "angry", "sad", "doubt", "sleepy", "cool"};

/* -------------------------------------------------------------------------- */
/*                                   Images                                   */
/* -------------------------------------------------------------------------- */

static const PokemonAsset* find_asset(const std::string& character, const std::string& key)
{
    for (int i = 0; i < kPokemonAssetCount; i++) {
        if (character == kPokemonAssets[i].character && key == kPokemonAssets[i].key) {
            return &kPokemonAssets[i];
        }
    }
    return nullptr;
}

bool PokemonImages::exists(const std::string& character)
{
    return find_asset(character, "bg") != nullptr;
}

std::vector<std::string> PokemonImages::characters()
{
    std::vector<std::string> names;
    for (int i = 0; i < kPokemonAssetCount; i++) {
        if (strcmp(kPokemonAssets[i].key, "bg") == 0) {
            names.push_back(kPokemonAssets[i].character);
        }
    }
    return names;
}

/**
 * @brief Decodes one PNG into dsc: RGB565 when alpha is false, RGB565A8 otherwise
 */
static void* decode(const PokemonAsset* asset, bool alpha, lv_image_dsc_t* dsc)
{
    unsigned char* out = nullptr;
    unsigned w = 0, h = 0;
    unsigned err = lodepng_decode32(&out, &w, &h, asset->png, asset->size);
    auto decoded = (lv_draw_buf_t*)out;
    if (err || !decoded) {
        ESP_LOGE(TAG, "decode %s/%s: lodepng error %u", asset->character, asset->key, err);
        return nullptr;
    }

    size_t px   = (size_t)w * h;
    size_t size = px * (alpha ? 3 : 2);
    auto* buf   = (uint8_t*)heap_caps_malloc(size, MALLOC_CAP_SPIRAM);
    if (buf) {
        auto* color = (uint16_t*)buf;
        uint8_t* a  = buf + px * 2;
        for (size_t i = 0; i < px; i++) {
            const uint8_t* p = decoded->data + (i / w) * decoded->header.stride + (i % w) * 4;
            color[i]         = ((p[0] >> 3) << 11) | ((p[1] >> 2) << 5) | (p[2] >> 3);
            if (alpha) {
                a[i] = p[3];
            }
        }

        memset(dsc, 0, sizeof(*dsc));
        dsc->header.magic  = LV_IMAGE_HEADER_MAGIC;
        dsc->header.cf     = alpha ? LV_COLOR_FORMAT_RGB565A8 : LV_COLOR_FORMAT_RGB565;
        dsc->header.w      = w;
        dsc->header.h      = h;
        dsc->header.stride = w * 2;
        dsc->data_size     = size;
        dsc->data          = buf;
    } else {
        ESP_LOGE(TAG, "no memory for %s/%s", asset->character, asset->key);
    }
    lv_draw_buf_destroy(decoded);
    return buf;
}

std::shared_ptr<PokemonImages> PokemonImages::load(const std::string& character)
{
    if (!exists(character)) {
        return nullptr;
    }

    int64_t start = esp_timer_get_time();
    std::shared_ptr<PokemonImages> images(new PokemonImages());

    auto load_one = [&](const std::string& key, bool alpha, lv_image_dsc_t* dsc) {
        auto asset = find_asset(character, key);
        void* buf  = asset ? decode(asset, alpha, dsc) : nullptr;
        if (!buf) {
            ESP_LOGE(TAG, "missing %s/%s", character.c_str(), key.c_str());
            return false;
        }
        images->_buffers.push_back(buf);
        return true;
    };

    bool cutout = false;
    for (int i = 0; i < kPokemonSkinCount; i++) {
        if (character == kPokemonSkins[i].character) {
            images->backdrop = kPokemonSkins[i].backdrop;
            cutout           = kPokemonSkins[i].cutout;
        }
    }

    bool ok = load_one("bg", cutout, &images->bg);
    for (int s = 0; ok && s < kEyeStates; s++) {
        std::string state = s == kEyeClosed ? "closed" : _emotion_names[s];
        ok = load_one("eye_" + state + "_l", true, &images->eyes[s][0]) &&
             load_one("eye_" + state + "_r", true, &images->eyes[s][1]);
    }
    for (int s = 0; ok && s < kMouthStates; s++) {
        std::string state = s == kMouthTalkS ? "talk_s" : s == kMouthTalkL ? "talk_l" : _emotion_names[s];
        ok = load_one("mouth_" + state, true, &images->mouths[s]);
    }
    for (int i = 0; ok && i < kPokemonFxCount; i++) {
        auto& def = kPokemonFx[i];
        if (character != def.character) {
            continue;
        }
        images->fx.emplace_back();
        auto& layer = images->fx.back();
        layer.x      = def.x;
        layer.y      = def.y;
        layer.behind = def.behind;
        for (int mood = 0; mood <= kEmotions; mood++) {
            std::string prefix = "fx" + std::to_string(def.layer) + "_" + (mood < kEmotions ? _emotion_names[mood] : "any");
            for (int n = 0; find_asset(character, prefix + "_" + std::to_string(n)); n++) {
                layer.frames[mood].emplace_back();
                ok = ok && load_one(prefix + "_" + std::to_string(n), true, &layer.frames[mood].back());
            }
        }
    }
    if (!ok) {
        return nullptr;
    }

    ESP_LOGI(TAG, "loaded %s in %d ms", character.c_str(), (int)((esp_timer_get_time() - start) / 1000));
    s_last_images = images;
    debugCheck();
    return images;
}

PokemonImages::~PokemonImages()
{
    for (auto buf : _buffers) {
        heap_caps_free(buf);
    }
}

/* -------------------------------------------------------------------------- */
/*                                   Avatar                                   */
/* -------------------------------------------------------------------------- */

void PokemonAvatar::init(lv_obj_t* parent, std::shared_ptr<PokemonImages> images, const lv_font_t* font)
{
    _images = images;

    _pannel = std::make_unique<Container>(parent);
    _pannel->align(LV_ALIGN_CENTER, 0, 0);
    _pannel->setSize(320, 240);
    _pannel->setRadius(0);
    _pannel->setBorderWidth(0);
    _pannel->setPadding(0, 0, 0, 0);
    _pannel->setBgColor(lv_color_hex(_images->backdrop));
    _pannel->removeFlag(LV_OBJ_FLAG_SCROLLABLE);

    // Fx layers behind the head go under the background; the rest go over the face
    auto create_fx = [this](bool behind) {
        for (size_t i = 0; i < _images->fx.size(); i++) {
            auto& layer = _images->fx[i];
            if (layer.behind != behind) {
                continue;
            }
            auto img = lv_image_create(_pannel->get());
            lv_obj_align(img, LV_ALIGN_CENTER, layer.x, layer.y);
            lv_obj_remove_flag(img, LV_OBJ_FLAG_CLICKABLE);
            lv_obj_add_flag(img, LV_OBJ_FLAG_HIDDEN);
            _fx[i] = img;
        }
    };
    _fx.assign(_images->fx.size(), nullptr);
    create_fx(true);

    _bg = lv_image_create(_pannel->get());
    lv_image_set_src(_bg, &_images->bg);
    lv_obj_align(_bg, LV_ALIGN_CENTER, 0, 0);
    lv_obj_remove_flag(_bg, LV_OBJ_FLAG_CLICKABLE);

    _key_elements.leftEye  = std::make_unique<PokemonEye>(_pannel->get(), _images, true);
    _key_elements.rightEye = std::make_unique<PokemonEye>(_pannel->get(), _images, false);
    _key_elements.mouth    = std::make_unique<PokemonMouth>(_pannel->get(), _images);
    create_fx(false);
    _key_elements.speechBubble =
        std::make_unique<DefaultSpeechBubble>(_pannel->get(), lv_color_white(), lv_color_black(), font);
    update();
}

void PokemonAvatar::update()
{
    Avatar::update();

    // Fx frames: flicker faster when angry
    uint32_t now      = lv_tick_get();
    int emotion       = (int)_emotion;
    uint32_t interval = _emotion == Emotion::Angry ? 70 : 130;
    if (now - _fx_tick < interval && _fx_tick != 0) {
        return;
    }
    _fx_tick = now;
    _fx_frame++;

    for (size_t i = 0; i < _fx.size(); i++) {
        auto& frames = _images->fx[i].framesFor(emotion);
        if (frames.empty()) {
            lv_obj_add_flag(_fx[i], LV_OBJ_FLAG_HIDDEN);
            continue;
        }
        lv_image_set_src(_fx[i], &frames[_fx_frame % frames.size()]);
        lv_obj_remove_flag(_fx[i], LV_OBJ_FLAG_HIDDEN);
    }
}

PokemonAvatar::~PokemonAvatar()
{
    // Delete the LVGL objects before the images they show
    _key_elements = KeyElements_t();
    _decorator_pool.clear();
    _pannel.reset();
    _images.reset();
}

Container* PokemonAvatar::getPanel() const
{
    return _pannel.get();
}

/* -------------------------------------------------------------------------- */
/*                                    Eyes                                    */
/* -------------------------------------------------------------------------- */

PokemonEye::PokemonEye(lv_obj_t* parent, std::shared_ptr<PokemonImages> images, bool isLeftEye)
    : _images(images), _is_left_eye(isLeftEye)
{
    _img = lv_image_create(parent);
    lv_obj_remove_flag(_img, LV_OBJ_FLAG_CLICKABLE);
    setWeight(100);
    setPosition(_position);
}

PokemonEye::~PokemonEye()
{
    lv_obj_delete(_img);
}

void PokemonEye::setPosition(const Vector2i& position)
{
    Element::setPosition(position);
    int x = (_is_left_eye ? -_eye_dx : _eye_dx) + map_range(_position.x, -100, 100, -_eye_offset, _eye_offset);
    int y = _eye_y + map_range(_position.y, -100, 100, -_eye_offset, _eye_offset);
    lv_obj_align(_img, LV_ALIGN_CENTER, x, y);
}

void PokemonEye::setWeight(int weight)
{
    Feature::setWeight(weight);
    refresh();
}

void PokemonEye::setEmotion(const Emotion& emotion)
{
    if (getIgnoreEmotion()) {
        return;
    }
    // The sprite carries the expression, so the eye stays fully open; blinking lowers the weight
    _emotion = emotion;
    setWeight(100);
}

Emotion PokemonEye::getEmotion() const
{
    return _emotion;
}

void PokemonEye::setVisible(bool visible)
{
    Element::setVisible(visible);
    if (visible) {
        lv_obj_remove_flag(_img, LV_OBJ_FLAG_HIDDEN);
    } else {
        lv_obj_add_flag(_img, LV_OBJ_FLAG_HIDDEN);
    }
}

void PokemonEye::setSize(int size)
{
    Feature::setSize(size);
    lv_image_set_scale(_img, 256 + _size * 64 / 100);
}

void PokemonEye::refresh()
{
    int state = _weight < 30 ? PokemonImages::kEyeClosed : (int)_emotion;
    lv_image_set_src(_img, &_images->eyes[state][_is_left_eye ? 0 : 1]);
}

/* -------------------------------------------------------------------------- */
/*                                    Mouth                                   */
/* -------------------------------------------------------------------------- */

PokemonMouth::PokemonMouth(lv_obj_t* parent, std::shared_ptr<PokemonImages> images) : _images(images)
{
    _img = lv_image_create(parent);
    lv_obj_remove_flag(_img, LV_OBJ_FLAG_CLICKABLE);
    setWeight(0);
    setPosition(_position);
}

PokemonMouth::~PokemonMouth()
{
    lv_obj_delete(_img);
}

void PokemonMouth::setPosition(const Vector2i& position)
{
    Element::setPosition(position);
    int x = map_range(_position.x, -100, 100, -_mouth_offset, _mouth_offset);
    int y = _mouth_y + map_range(_position.y, -100, 100, -_mouth_offset, _mouth_offset);
    lv_obj_align(_img, LV_ALIGN_CENTER, x, y);
}

void PokemonMouth::setWeight(int weight)
{
    Feature::setWeight(weight);
    refresh();
}

void PokemonMouth::setRotation(int rotation)
{
    Element::setRotation(rotation);
    lv_image_set_rotation(_img, _rotation);
}

void PokemonMouth::setEmotion(const Emotion& emotion)
{
    if (getIgnoreEmotion()) {
        return;
    }
    _emotion = emotion;
    refresh();
}

Emotion PokemonMouth::getEmotion() const
{
    return _emotion;
}

void PokemonMouth::setVisible(bool visible)
{
    Element::setVisible(visible);
    if (visible) {
        lv_obj_remove_flag(_img, LV_OBJ_FLAG_HIDDEN);
    } else {
        lv_obj_add_flag(_img, LV_OBJ_FLAG_HIDDEN);
    }
}

void PokemonMouth::refresh()
{
    int state = _weight < 12   ? (int)_emotion
                : _weight < 55 ? PokemonImages::kMouthTalkS
                               : PokemonImages::kMouthTalkL;
    lv_image_set_src(_img, &_images->mouths[state]);
}
