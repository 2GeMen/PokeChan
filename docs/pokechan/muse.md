# 接入 Muse

PokeChan 把 [Muse Gadget SDK](https://github.com/facebookincubator/muse-gadget-sdk) 的会话代码（TLS → WebSocket → Noise XX 握手 → `/chat/stream`）移植进了 StackChan 固件，组件在 `firmware/components/muse_hatch/`。接入后，StackChan 可以直接问你的 Muse 助手，Muse 连着的 Google 日历、Gmail 和个人记忆都能用上。

## 原理

```
小智大模型 ──调用工具──▶ self.muse.ask / get_brief / get_answer（设备上的 MCP 工具）
                              │
                              ▼
                    muse_ask 任务（PSRAM 栈）── 问题 ──▶ Muse VM（hatch.metaaivm.com，Noise 加密会话）
                              ◀── 回复文本 ─────────
```

- **设备令牌**：配对时 Muse App 下发的 `access_token`。固件用它向 `api.muse.ai` 换取 VM 地址和会话凭证。
- **简报**：每天早上 6 点（设备本地时间）以后，自动向 Muse 要一份"今天和明天的日程 + 重要邮件"简报，一天只要一次，失败时 15 分钟后重试，一天最多 3 次。简报存在 NVS 里，重启后不会重新要。每份简报都会以你的名义出现在 Muse 的聊天记录里，所以不会更频繁地要。`self.muse.get_brief` 直接读这份缓存，马上就能返回；还没有当天的简报时（比如早上 6 点前），它会立刻去要一份。日期按设备设置里的时区算，请在设置里选好时区（或用调试命令 `>tz=`），而且要等开机后 SNTP 校准过时钟才会去要。
- **提问**：`self.muse.ask` 是一个异步 MCP 工具。工具调用不会卡住设备主线程，Muse 回答后在同一轮对话里直接念出来。超过 60 秒还没回答，会先说"Muse 还在查"；等答案到了"叮"一声，你再问"Muse 怎么说"，它就会通过 `self.muse.get_answer` 念出来。
- **延迟**（实测）：简单问题 5 到 25 秒，查日历、邮件 7 到 73 秒。

## 第一步：配对，拿到设备令牌

配对只能在**官方 Muse 小设备固件**里完成，因为它实现了和 Muse App 的蓝牙配对流程。所以要先临时刷官方固件，配对后读出令牌，再刷回 PokeChan。

1. 在 [gadgets.muse.ai](https://gadgets.muse.ai/) 申请 SDK token（`mgst_…`），存成一个私有文件，比如 `~/.config/pokechan/muse_sdk_token.txt`，权限设为 600。
2. **先整片备份 StackChan 的 Flash**（见 [build-and-flash.md](build-and-flash.md)）。官方固件用的分区表不一样，后面要靠这份备份恢复。
3. 按 Muse Gadget SDK 的说明，用 ESP-IDF 6.0.1 编译 CoreS3 版官方固件（`tools/muse/board.sh build cores3`）。SDK token 会写进 `build-*/sdkconfig` 的 `CONFIG_GADGET_SDK_TOKEN`，这个文件不要提交到任何地方。
4. 刷入官方固件，打开手机 Muse App 的开发者模式，搜索并配对设备（名字类似 `MuseGadget-XXXXXX`），直到 App 里显示已连接。
5. 读出令牌（需要先 source ESP-IDF 的 `export.sh`，让 `IDF_PATH` 生效）：

   ```bash
   python firmware/tools/muse/muse_token.py read /dev/cu.usbmodem101 ~/.config/pokechan/muse_device_token.json
   ```

   脚本只打印令牌长度，文件权限是 600。
6. 用第 2 步的备份整片写回，恢复 StackChan 原来的分区表和数据，然后刷入 PokeChan 的 app（`idf.py app-flash`）。

## 第二步：把令牌交给 PokeChan

```bash
python firmware/tools/muse/muse_token.py send /dev/cu.usbmodem101 ~/.config/pokechan/muse_device_token.json
```

令牌通过串口命令 `>hatch.token=` 分段写入，存在设备 NVS 的 `muse_hatch` 命名空间里，串口不会回显令牌内容。脚本会一直等到 Muse 显示 `Connected` 才结束。

检查状态：在串口发送 `>status`，返回 `@status {...}`，其中 `hatch.state` 应该是 `Connected`。

## 怎么问

| 你说的话 | 用到的工具 |
| --- | --- |
| "我今天有什么安排？""明天有课吗？""有什么重要邮件？" | `self.muse.get_brief`（读缓存，秒回） |
| "问问 Muse 周四的会几点开始？""用 Muse 查一下老师上周发的邮件" | `self.muse.ask`（实时问） |
| 听到"叮"一声之后："Muse 怎么说？" | `self.muse.get_answer` |

想确保一定去问 Muse，就用"问问 Muse"开头。语音识别有时会把 Muse 写成"缪斯""muss"，一般不影响模型理解。

## 安全与隐私

- 令牌以明文存在设备 NVS 里。能用 USB 连上这台设备的人都能读出来，所以不要把设备借给不信任的人，也不要分享 Flash 备份。
- 想撤销授权，在 Muse App 里移除这个小设备即可。令牌失效后，需要重新走一遍第一步。
- 发给 Muse 的问题和 Muse 的回答都只在设备、Muse 服务和小智服务之间传递（回答会交给小智的大模型转述）。PokeChan 不会把它们发给别的地方。
- 仓库里没有任何令牌。令牌文件请放在仓库之外，比如 `~/.config/pokechan/`。
