# PokeChan

[中文说明](README.zh-CN.md)

**PokeChan** is a community firmware mod for the [M5Stack StackChan](https://github.com/m5stack/StackChan)
desktop robot. It keeps everything StackChan does and adds:

- **Pokémon faces**: Pikachu, Charmander, Bulbasaur, Squirtle and Ditto, switchable by voice
  ("switch to Pikachu"), with all the original animation: blinking, talking, breathing and idle glances.
- **Signature moves**: Charmander's tail flame flares up when it's angry, Pikachu's cheeks spark, and
  Squirtle puts on sunglasses when it's being cool.
- **Head gestures**: the head moves with the mood — a nod when happy, a shake and a glare when angry,
  chin up when cool, a look up at the badge while thinking. Say "stop moving" to turn it off.
- **Skill badges**: while a tool runs, the face looks thoughtful and a badge pops up (weather, news,
  search, Muse, reminder, camera), like a Pokémon using a move. The text speech bubble is gone; the
  mouth just talks.
- **Muse on board**: asks your [Meta Muse](https://gadgets.muse.ai/) assistant about your calendar,
  email and memories, using the Muse Gadget SDK's session code ported into the firmware. Answers are
  spoken in the same turn.
- **Mac-side MCP tools**: free weather (Open-Meteo), web search and news search (DuckDuckGo) through
  the StackChan World App's MCP endpoint, running as a login service on your Mac.

![The five faces](docs/pokechan/images/faces.png)

![Signature moves](docs/pokechan/images/effects.png) ![Skill badges](docs/pokechan/images/skills.png)

> **Unofficial fan project.** PokeChan is not affiliated with, endorsed or sponsored by Nintendo,
> The Pokémon Company, Game Freak, Creatures, M5Stack, Meta or Xiaozhi. Pokémon and its character
> names and designs are trademarks and copyrights of their owners. The Pokémon faces are
> non-commercial fan art. Read [DISCLAIMER.md](DISCLAIMER.md) before using or sharing them.

## How it fits together

```
 "Hi Stack-chan"            ┌──────────────────────────────┐
  voice ──────────────────▶ │ StackChan (ESP32-S3, CoreS3)  │
                            │  xiaozhi voice + wake word    │
                            │  PokeChan faces, skill badges │
                            │  Muse bridge (Noise over WSS) ├──▶ Muse (Meta) — calendar, mail, memories
                            └──────────────┬───────────────┘
                                           │ MQTT / WebSocket
                                           ▼
                                  xiaozhi.me (free LLM, ASR, TTS)
                                           │ MCP endpoint (WebSocket)
                                           ▼
                            Mac: mcp-server/ (weather, web and news search)
```

## Repository layout

This repository is a fork of [m5stack/StackChan](https://github.com/m5stack/StackChan). PokeChan's
changes are on the `pokechan` branch:

| Path | What it is |
| --- | --- |
| `firmware/` | StackChan firmware with PokeChan's changes (ESP-IDF 5.5.4) |
| `firmware/components/muse_hatch/` | Muse bridge: session code from the Muse Gadget SDK plus the StackChan glue |
| `firmware/components/noise_core/`, `minimp3/` | Libraries from the Muse Gadget SDK |
| `firmware/main/stackchan/avatar/skins/pokemon/` | Pokémon skins, fx layers and skill badges |
| `firmware/tools/pokemon_faces/` | Generator that draws all face, fx and badge art |
| `firmware/tools/muse/muse_token.py` | Moves your Muse device token from the official Muse firmware to PokeChan |
| `firmware/patches/xiaozhi-esp32.patch` | Patch on xiaozhi-esp32 v2.2.4 (StackChan's, plus async MCP tools) |
| `mcp-server/` | Mac-side MCP server and launchd service |
| `docs/pokechan/` | PokeChan documentation (Chinese) |
| `app/`, `server/`, `remote/` | Upstream StackChan app, server and remote, unchanged |

## Quick start

1. Build and flash the firmware: [docs/pokechan/build-and-flash.md](docs/pokechan/build-and-flash.md)
2. Optional: connect Muse: [docs/pokechan/muse.md](docs/pokechan/muse.md)
3. Optional: run the Mac tools: [docs/pokechan/mcp-server.md](docs/pokechan/mcp-server.md)
4. Talk to it: [docs/pokechan/skills.md](docs/pokechan/skills.md) lists every tool and what to say.

More: [features and new assets](docs/pokechan/features.md) · [faces and the art generator](docs/pokechan/skins.md)
· [debug console](docs/pokechan/debug-console.md) · [security and privacy](SECURITY.md)

## Licenses

- PokeChan's own code: MIT ([LICENSE](LICENSE)).
- StackChan firmware: MIT, M5Stack ([firmware/LICENSE](firmware/LICENSE)); xiaozhi-esp32: MIT.
- Code from the Muse Gadget SDK: Apache-2.0, Meta Platforms
  ([firmware/components/muse_hatch/LICENSE.muse-gadget-sdk](firmware/components/muse_hatch/LICENSE.muse-gadget-sdk));
  modified files say so in their headers.
- Everything else: see [NOTICE](NOTICE) and [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).

The original StackChan README is kept as [README.StackChan.md](README.StackChan.md).
