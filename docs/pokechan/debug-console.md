# 串口调试命令

PokeChan 复用 StackChan 的 USB 串口（USB-Serial-JTAG，115200）。在串口里发送以 `>` 开头的一行文字，就是一条命令。这里的命令只在你自己连着 USB 时能用，网络上碰不到。

用 pyserial 打开串口时，要把 `dtr` 和 `rts` 设为 False，否则设备会重启。

## Muse

| 命令 | 作用 |
| --- | --- |
| `>status` | 打印 `@status {...}`，里面有 Muse 的连接状态 |
| `>hatch.token=…` / `>hatch.token+=…` | 写入设备令牌（`+=` 表示追加），不会回显，只返回令牌长度 |
| `>hatch.vm=ID` | 指定 VM，留空就用账号默认的 VM |
| `>chat=TEXT` / `>chat+=TEXT` | 用打字的方式问 Muse，回复会以多行 `@chat {...}` 的形式流式返回（和 SDK 的 `chat.py` 兼容） |
| `>chat.cancel` | 取消正在进行的打字提问 |
| `>ask=TEXT` | 用语音工具同样的方式提问（带口语化的提示词） |
| `>tz` / `>tz=POSIX` | 打印时区和本地时间 / 设置时区，例如 `>tz=CST-8`（北京时间）、`>tz=PST8PDT,M3.2.0,M11.1.0`（美国太平洋时间），保存在 NVS，和设置里选时区的效果一样 |
| `>brief` / `>brief=refresh` | 打印缓存的简报 / 立即重新要一份简报（不受每天一次的限制，会出现在 Muse 聊天记录里） |
| `>answer` | 打印最近一次的回答 |

## 脸盘与显示

| 命令 | 作用 |
| --- | --- |
| `>face=pikachu` | 换脸，作用和语音换脸一样，选择会保存。前后会各打印一行内存日志 |
| `>expr=angry` | 做一个表情并保持 20 秒 |
| `>move=angry` | 只播放头部动作，不改表情。可选：neutral、happy、angry、sad、doubt、sleepy、cool、nod |
| `>head` | 打印当前舵机角度（`@head 左右 俯仰`，单位 0.1°） |
| `>gestures=off` / `>gestures=on` | 关闭或打开情绪带动的头部动作，设置会保存 |
| `>say=% weather_forecast...` | 模拟一条助手消息。以 `% ` 开头的会模拟一次工具调用（弹出技能图标）；普通文字会结束技能状态 |
| `>snap` | 把 LVGL 当前渲染的画面以十六进制 RGB565 输出（`@snap W H` …… `@snap end`），用来在电脑上还原截图 |
| `>mem` | 打印内部 RAM 和 PSRAM 的剩余量，以及最近一次加载的背景图的校验值 |

`>snap` 输出的内容大约有 300 KB，传输时可能触发看门狗告警（只是告警，不会重启），偶尔也会丢几个字节，导致截图出现横向错位。这些都只是调试时的现象，不影响正常使用。
