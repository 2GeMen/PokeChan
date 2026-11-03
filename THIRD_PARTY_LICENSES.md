# Third-party licenses

Components PokeChan builds on, where they come from and how they are licensed. Upstream StackChan
components are listed for completeness; their license files ship with them (fetched by
`firmware/fetch_repos.py` or the ESP-IDF component manager).

## Firmware

| Component | Version | License | Source | In this repo |
| --- | --- | --- | --- | --- |
| StackChan firmware, app, server, remote | fork base `eff0d6b` | MIT | [m5stack/StackChan](https://github.com/m5stack/StackChan) | yes (fork) |
| xiaozhi-esp32 | v2.2.4 + patch | MIT | [78/xiaozhi-esp32](https://github.com/78/xiaozhi-esp32) | patch only (`firmware/patches/`) |
| Muse Gadget SDK: muse session code, noise_core | snapshot 2026-10-27 | Apache-2.0 | [facebookincubator/muse-gadget-sdk](https://github.com/facebookincubator/muse-gadget-sdk) | yes, `firmware/components/muse_hatch/`, `noise_core/` (modified files marked) |
| minimp3 (via the Muse Gadget SDK) | SDK snapshot | CC0-1.0 | [lieff/minimp3](https://github.com/lieff/minimp3) | yes, `firmware/components/minimp3/` |
| ESP-IDF | v5.5.4 | Apache-2.0 | [espressif/esp-idf](https://github.com/espressif/esp-idf) | no (toolchain) |
| LVGL | 9.4.0 | MIT | [lvgl/lvgl](https://github.com/lvgl/lvgl) | no (component manager) |
| lodepng (inside LVGL) | LVGL's copy | zlib | [lvandeve/lodepng](https://github.com/lvandeve/lodepng) | no |
| esp-sr (wake words 你好小智 `wn9_nihaoxiaozhi`, default, and "Hi Stack-chan") | per StackChan | Espressif MIT | [espressif/esp-sr](https://github.com/espressif/esp-sr) | no |
| Kokoro-82M (TTS used once to make `main/assets/sfx/im_here.ogg`, the spoken 我在的 on wake; voice `zf_xiaoni`, pitched up) | v1.0 | Apache-2.0 | [hexgrad/Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) | the generated 0.45 s clip only |
| xiaozhi-fonts | per StackChan | MIT | [78/xiaozhi-fonts](https://github.com/78/xiaozhi-fonts) | no |
| mooncake, mooncake_log, smooth_ui_toolkit | v2.3.3 / v1.5.0 / v2.12.0 | MIT | [Forairaaaaa](https://github.com/Forairaaaaa) | no (`fetch_repos.py`) |
| ArduinoJson | v7.4.2 | MIT | [bblanchon/ArduinoJson](https://github.com/bblanchon/ArduinoJson) | no |
| esp-now | c33383de | Apache-2.0 | [espressif/esp-now](https://github.com/espressif/esp-now) | no |
| mbedTLS (in ESP-IDF) | ESP-IDF's | Apache-2.0 | [Mbed-TLS/mbedtls](https://github.com/Mbed-TLS/mbedtls) | no |

Other ESP-IDF managed components used by StackChan are listed in `firmware/dependencies.lock`; each
carries its own license in `firmware/managed_components/`.

## Mac-side MCP server (`mcp-server/`)

| Package | License | Source |
| --- | --- | --- |
| mcp (MCP Python SDK) | MIT | [modelcontextprotocol/python-sdk](https://github.com/modelcontextprotocol/python-sdk) |
| websockets | BSD-3-Clause | [python-websockets/websockets](https://github.com/python-websockets/websockets) |
| httpx | BSD-3-Clause | [encode/httpx](https://github.com/encode/httpx) |
| ddgs | MIT | [deedy5/ddgs](https://github.com/deedy5/ddgs) |

## Tools

| Package | License | Used by |
| --- | --- | --- |
| Pillow | MIT-CMU | `firmware/tools/pokemon_faces/gen_faces.py` |
| NumPy | BSD-3-Clause | same |
| esptool, pyserial | GPL-2.0-or-later / BSD-3-Clause | `firmware/tools/muse/muse_token.py` (run as separate programs / imported; not distributed here) |
| ESP-IDF `nvs_partition_tool` | Apache-2.0 | `muse_token.py read` (loaded from your ESP-IDF install) |
| [three.js](https://threejs.org/) r160 | MIT | `tools/promo/web/render.html` (loaded from the jsDelivr CDN at render time; not distributed here) |
| imageio-ffmpeg (bundles an FFmpeg binary) | BSD-2-Clause / FFmpeg: LGPL-2.1+ or GPL | `tools/promo/` encoding (installed by the user, run as a separate program; not distributed here) |
| [Noto Sans SC](https://fonts.google.com/noto/specimen/Noto+Sans+SC) | SIL Open Font License 1.1 | `tools/promo/` titles and captions (downloaded by the user; not distributed here) |
| StackChan 3D model (`app/assets/stack_chan_model.glb`) | MIT, M5Stack (upstream) | rendered by `tools/promo/` |

The promo score and sound effects are synthesized by `tools/promo/music.py`, `music_h.py` and
`compose.py`; they are original to this project and covered by its MIT License.

## Services and data

| Service | Terms | Notes |
| --- | --- | --- |
| [Open-Meteo](https://open-meteo.com/) | data CC BY 4.0; free API for non-commercial use | attribution: "Weather data by Open-Meteo.com" |
| DuckDuckGo (via ddgs) | [DuckDuckGo terms](https://duckduckgo.com/terms) | unofficial access; may be rate limited |
| [xiaozhi.me](https://xiaozhi.me/) | its own terms | voice, language model, MCP endpoint |
| Muse (Meta) | Muse / Meta terms | your own account and device token |

## Fan art

The Pokémon character art is not licensed under any of the above and not under PokeChan's MIT
License; see [DISCLAIMER.md](DISCLAIMER.md).
