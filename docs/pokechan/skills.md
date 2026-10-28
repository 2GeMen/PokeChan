# 技能参考

StackChan 没有固定的唤醒关键词：说 "Hi Stack-chan" 唤醒之后，你说的话交给小智的大模型，模型对照每个工具的说明自己决定调用哪一个。下面列的是最容易触发各个工具的说法，意思相近的说法一般也能触发。

## 技能一览

| 技能 | 工具 | 在哪里运行 | 推荐说法 | 图标 |
| --- | --- | --- | --- | --- |
| 日程简报 | `self.muse.get_brief` | 设备（PokeChan） | "我今天有什么安排？""有什么重要邮件？" | Muse |
| 问 Muse | `self.muse.ask` | 设备（PokeChan） | "**问问 Muse** 周四的会几点开始？" | Muse |
| Muse 迟到的回答 | `self.muse.get_answer` | 设备（PokeChan） | 听到"叮"之后："Muse 怎么说？" | Muse |
| 天气 | `weather_forecast` | Mac（`mcp-server/`） | "明天天气怎么样？""多伦多这周会下雨吗？" | 天气 |
| 网页搜索 | `web_search` | Mac | "帮我搜一下 Costco 几点关门" | 搜索 |
| 新闻 | `news_search` | Mac | "最近有什么科技新闻？" | 新闻 |
| 换脸 | `self.robot.set_character` | 设备（PokeChan） | "换成皮卡丘""变成小火龙""换回原来的脸" | （无） |
| 查当前的脸 | `self.robot.get_character` | 设备（PokeChan） | "你现在是谁？" | （无） |
| 做表情 | `self.robot.show_expression` | 设备（PokeChan） | "生个气给我看看""做个酷的表情""装酷" | （无） |
| 提醒 | `self.robot.create_reminder` / `get_reminders` / `stop_reminder` | 设备（StackChan） | "10 分钟后提醒我关火" | 提醒 |
| 转头 | `self.robot.set_head_angles` / `get_head_angles` | 设备（StackChan） | "往左看""抬头" | （无） |
| 灯光 | `self.robot.set_led_color` | 设备（StackChan） | "把灯调成蓝色" | （无） |
| 拍照 | `self.camera.take_photo` | 设备（小智） | "看看我手里拿的是什么" | 拍照 |
| 音量、亮度、主题 | `self.audio_speaker.set_volume`、`self.screen.*` | 设备（小智） | "声音大一点" | （无） |
| 平台自带的工具 | 比如 `get_weather`、`internet_search` | xiaozhi.me | 模型有时会选它们 | 天气 / 搜索 |

表中"设备（PokeChan）"是 PokeChan 新增的工具，"设备（StackChan）"和"设备（小智）"是原版就有的。

## 技能图标与思考表情

模型调用工具时，设备会收到一条 `% 工具名...` 消息。PokeChan 根据工具名来决定显示什么：

| 工具名包含 | 图标 |
| --- | --- |
| `muse` | Muse 小机器人 |
| `weather` | 天气（太阳和云） |
| `news` | 新闻（报纸） |
| `search` | 搜索（放大镜） |
| `reminder` | 提醒（铃铛） |
| `camera` / `photo` | 拍照（相机） |
| 其他工具 | 通用的星星 |

![技能图标](images/icons.png)

- 调用期间，脸保持"疑惑 / 思考"表情，右上角的图标弹出后上下浮动。
- 开始回答时，表情恢复成服务器最新下发的情绪，图标停留约 1 秒后淡出。如果回到待机，或者超过 90 秒，也会自动收起。
- 换脸、做表情、转头、调灯光、调音量、调亮度这类只改变机器人自身的工具，不弹图标，也不切换成思考表情。

## 表情从哪里来

1. 小智服务器每次回复都会发一条 `{"type":"llm","emotion":"..."}` 消息。这个情绪是根据大模型回复开头的表情符号换算出来的。
2. PokeChan 再把这些情绪对应到屏幕上的 7 种表情：

| 屏幕表情 | 对应的情绪 |
| --- | --- |
| 平静 | neutral，以及下面没列到的情绪 |
| 开心 | happy、laughing、funny、loving、relaxed、delicious、kissy、silly |
| 生气 | angry |
| 难过 | sad、crying、embarrassed |
| 疑惑 | doubtful、surprised、shocked、thinking、confused |
| 困 | sleepy |
| 酷 / 得意 | cool、confident、winking |

3. 实际使用中，模型几乎每句都用 😊 开头，服务器基本只发 happy 和 neutral。所以 PokeChan 加了 `self.robot.show_expression`：模型可以主动指定一个表情，并保持几秒（默认 8 秒，最长 30 秒）。在这几秒里，服务器每句话发来的情绪都会被忽略，时间到了再恢复。

| 表情 | 招牌特效 |
| --- | --- |
| angry | 小火龙的火尾巴烧旺、冒火星；皮卡丘脸颊放电 |
| cool | 杰尼龟戴墨镜 |

## 换脸

- 可选的脸：`stackchan`（原版 Stack-chan 脸）、`pikachu`、`charmander`、`bulbasaur`、`squirtle`、`ditto`。
- 选择会存进 NVS（`avatar` 命名空间的 `character` 键），重启后保留。
- 切换时会解码这个角色的 PNG 素材，大约需要 0.4 到 0.8 秒，期间画面会停住一下。
