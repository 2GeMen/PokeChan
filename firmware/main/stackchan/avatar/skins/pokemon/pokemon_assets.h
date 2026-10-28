/*
 * Pokémon avatar skin assets, embedded as PNG; see tools/pokemon_faces/gen_faces.py.
 */
#pragma once
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    const char* character;  // "pikachu", ...
    const char* key;        // "bg", "eye_happy_l", "mouth_talk_s", ...
    const uint8_t* png;
    size_t size;
} PokemonAsset;

extern const PokemonAsset kPokemonAssets[];
extern const int kPokemonAssetCount;

// An animated layer over the face; its frames are assets "fx<layer>_<emotion or any>_<n>"
typedef struct {
    const char* character;
    int layer;
    int x;  // sprite center, pixels from the screen center
    int y;
    int behind;  // drawn behind the head (the background is then cut out)
} PokemonFxLayer;

extern const PokemonFxLayer kPokemonFx[];
extern const int kPokemonFxCount;

typedef struct {
    const char* character;
    uint32_t backdrop;  // 0xRRGGBB, shown around the head when the background is cut out
    int cutout;         // background has alpha
} PokemonSkin;

extern const PokemonSkin kPokemonSkins[];
extern const int kPokemonSkinCount;

#ifdef __cplusplus
}
#endif
