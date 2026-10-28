# Security and privacy / 安全与隐私

## Secrets PokeChan uses / PokeChan 用到的密钥

| Secret | Where it lives | Never |
| --- | --- | --- |
| Muse SDK token (`mgst_…`) | your own file, e.g. `~/.config/pokechan/muse_sdk_token.txt`; the official Muse firmware's `sdkconfig` while you build it | commit it, paste it into issues or logs |
| Muse device token (`access_token`) | the device's NVS (`muse_hatch` / `token`); your token file from `muse_token.py read` | share a flash backup or the token file |
| MCP endpoint URL (`wss://…token=…`) | your own file, e.g. `~/.config/pokechan/mcp_endpoint.txt` (mode 600) | share it: whoever has it can attach tools to your robot |
| Wi-Fi password | the device's NVS (StackChan) | share a flash backup |

- This repository contains no tokens. `.gitignore` files keep build output, logs, virtualenvs and
  `mcp-server/*.txt` out of git; `firmware/scan_secrets.py` (from StackChan) scans for leaks before you
  push.
- The serial console never echoes the Muse token, and `muse_token.py` only prints its length.
- The device stores tokens in plain NVS. Anyone with USB access to the robot can read them. Revoke a
  leaked Muse token by removing the gadget in the Muse app; replace a leaked MCP endpoint in the
  StackChan World App.

## What leaves your network / 数据流向

| Data | Goes to |
| --- | --- |
| Your voice, the conversation | xiaozhi.me (StackChan's normal service) |
| Muse questions and answers | Muse (Meta) and, as tool results, xiaozhi.me's language model |
| Weather and search queries | Open-Meteo and DuckDuckGo, from your Mac |

PokeChan adds no telemetry.

## Reporting / 报告问题

Please report security problems privately to the maintainers (GitHub security advisory) rather than
in a public issue.

- 本仓库不包含任何令牌。推送前可以用 `firmware/scan_secrets.py` 扫描一遍。
- 设备上的令牌以明文存在 NVS 里，能用 USB 连上设备的人都能读到。令牌泄露时：Muse 令牌在 Muse App 里移除这个小设备即可作废；MCP 接入点地址在 StackChan World App 里重新生成。
- 发现安全问题，请通过 GitHub 的 security advisory 私下报告，不要公开发 issue。
