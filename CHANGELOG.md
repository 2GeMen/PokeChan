# Changelog / 更新记录

## v0.1.0 — 2026-10-28

First public release. 首个公开版本。

### 新增 / Added

- **宝可梦脸盘**：皮卡丘、小火龙、妙蛙种子、杰尼龟、百变怪，语音换脸（`self.robot.set_character`），选择会保存；保留原版的眨眼、说话、呼吸、待机张望动画。
  Pokémon faces, switchable by voice and saved; all original animation kept.
- **招牌特效**：小火龙火尾巴（生气时更旺）、皮卡丘脸颊放电、杰尼龟墨镜；新增"酷"情绪，以及定时表情工具 `self.robot.show_expression`。
  Signature fx layers, a new Cool emotion and a timed expression tool.
- **情绪带动头部动作**：开心点头、生气甩头瞪人、耍酷抬下巴侧脸、思考时看向技能图标、换脸点头；可用语音关闭（`self.robot.set_head_gestures`）。
  Head gestures that follow the emotion; can be turned off by voice.
- **更安静的待机**：待机时头保持不动，只在白天整点活动一下（晚 11 点到早 7 点不动），被唤醒时抬头看人。
  Quieter idle: the head keeps still, looks around on the hour in the daytime, and looks up when woken.
- **唤醒更灵**："Hi Stack Chan" 的唤醒门槛从 0.585 调到 0.50，实测唤醒率从 7/10 提高到 20/20，没有发现误唤醒。
  Wake word threshold 0.585 → 0.50: 7/10 → 20/20 in testing, no false wakes.
- **技能图标**：调用工具时显示思考表情，并弹出天气、新闻、搜索、Muse、提醒、拍照等图标；去掉了显示不了中文的文字气泡。
  Skill badges while tools run; the broken text bubble is gone.
- **Muse 桥**：把 Muse Gadget SDK 的会话移植进固件，异步 MCP 工具让答案在同一轮对话里念出来。
  日程简报每天只向 Muse 要一次，存在设备里，所以不会刷屏你的 Muse 聊天记录。
  Muse bridge with same-turn async answers; the daily brief is asked once a day.
- **Mac 端 MCP 服务**：免费的天气（Open-Meteo）、网页搜索和新闻搜索。
  安装时需要设置自己所在的城市（`POKECHAN_HOME_NAME` / `_LAT` / `_LON`），见 [docs/pokechan/mcp-server.md](docs/pokechan/mcp-server.md)。
  Mac-side MCP server for weather, web and news search; your home city is a required setting.
- **工具**：脸盘素材生成器、Muse 令牌迁移工具、串口调试命令（`>face=`、`>expr=`、`>move=`、`>head`、`>gestures=`、`>snap`、`>mem` 等）、宣传片和封面制作工具（`tools/promo/`）。
  Art generator, Muse token tool, debug console, promo pipeline.

### 已知问题 / Known issues

- 屏幕字体没有中文字形，所以系统消息（如激活码）以外的中文不在屏幕上显示。
  The screen font has no CJK glyphs.
- Muse 服务（`hatch.metaaivm.com`）偶尔连不上，这时问 Muse 会返回"CAN'T REACH MUSE"。
  Muse is sometimes unreachable.
