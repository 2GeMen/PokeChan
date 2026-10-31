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
- **说"休息吧"就结束对话**：设备识别这类短句，说完回答就回到待机，不再依赖云端。
  Dismissals such as "休息吧" end the session on the device.
- **默认唤醒词改为"你好小智"**：门槛 0.52，唤醒后本地说一声"我在的"；"Hi Stack Chan"可用 `>wake=stackchan` 切换。
  The default wake word is now 你好小智 (threshold 0.52) with a local spoken reply; Hi Stack Chan stays selectable.
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
- 唤醒率约 8/10（单轮 10 次实测），还没有测过电视解说下的误唤醒。
  The wake word catches about 8 in 10 calls; false wakes around TV commentary are untested.
- 闲置后和服务器的连接可能断开，要等约 60 秒才重连，这段时间唤醒会失败。
  An idle connection can drop and takes about 60 s to come back; wake fails meanwhile.
- Muse 服务（`hatch.metaaivm.com`）偶尔连不上，这时问 Muse 会返回"CAN'T REACH MUSE"。
  Muse is sometimes unreachable.
