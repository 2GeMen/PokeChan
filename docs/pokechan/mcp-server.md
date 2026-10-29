# Mac 端 MCP 服务部署

`mcp-server/` 是一个跑在你自己电脑上的 MCP 服务，给 StackChan 增加三个免费技能，都不需要 API key：

| 工具 | 数据来源 | 作用 |
| --- | --- | --- |
| `weather_forecast(city="", days=3)` | [Open-Meteo](https://open-meteo.com/) | 当前天气加 1 到 7 天预报；城市留空时查"家"所在的城市 |
| `web_search(query, max_results=5)` | DuckDuckGo（通过 [ddgs](https://pypi.org/project/ddgs/)） | 网页搜索：营业时间、事实核对、最新信息 |
| `news_search(query, max_results=5)` | DuckDuckGo News | 带日期的新闻摘要 |

## 原理

```
StackChan ──▶ xiaozhi.me 大模型 ──(MCP 接入点, WebSocket)──▶ mcp_pipe.py ──(stdio)──▶ server.py
```

- StackChan World App 的"MCP 接入点"页面会给出一个 `wss://api.xiaozhi.me/...?token=...` 地址。它把小智大模型的工具调用转发到这个 WebSocket 上。
- `mcp_pipe.py` 连上这个地址，启动 `server.py`（基于 MCP Python SDK 的 `MCPServer`），在两者之间逐行转发 JSON-RPC 消息。断线后会自动重连，重连间隔从 1 秒逐步退避到 300 秒。
- 电脑关机或休眠时，这三个技能就用不了，StackChan 的其他功能不受影响。

## 安装（macOS）

需要 [uv](https://docs.astral.sh/uv/)。

1. 在 StackChan World App 里打开 MCP 接入点页面，复制地址，存成私有文件：

   ```bash
   mkdir -p ~/.config/pokechan
   pbpaste > ~/.config/pokechan/mcp_endpoint.txt   # 先在 App 里复制好地址
   chmod 600 ~/.config/pokechan/mcp_endpoint.txt
   ```

   这个地址里带着访问令牌，拿到它的人就能往你的 StackChan 上挂工具，**不要分享，也不要提交**。

2. 设置"家"所在的城市（不问城市名时用这里的天气），然后安装。城市名和经纬度必填，没设置时 `install.sh` 会提示并退出。下面以上海为例，换成你自己的城市；经纬度可以在地图应用里查，也可以用 [Open-Meteo 地理编码](https://open-meteo.com/en/docs/geocoding-api)查：

   ```bash
   cd mcp-server
   POKECHAN_HOME_NAME=上海 POKECHAN_HOME_LAT=31.2304 POKECHAN_HOME_LON=121.4737 ./install.sh
   ```

   `install.sh` 会：
   - 建好 `.venv` 并安装依赖（`mcp`、`websockets`、`httpx`、`ddgs`）；
   - 用 `launchd/com.pokechan.mcp.plist.template` 生成 `~/Library/LaunchAgents/com.pokechan.mcp.plist`；
   - 用 `launchctl bootstrap` 加载服务，之后开机自动启动，进程退出也会自动拉起。

3. 看日志：`mcp-server/logs/mcp_pipe.log`。连上后会出现 `connected to api.xiaozhi.me`，每次调用工具会记一行 `tools/call weather_forecast` 之类的日志。

常用命令：

```bash
launchctl kickstart -k gui/$(id -u)/com.pokechan.mcp        # 重启
launchctl bootout gui/$(id -u)/com.pokechan.mcp              # 停止并卸载
```

## 手动运行（其他系统）

```bash
cd mcp-server
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r pyproject.toml
POKECHAN_HOME_NAME=上海 POKECHAN_HOME_LAT=31.2304 POKECHAN_HOME_LON=121.4737 \
POKECHAN_ENDPOINT_FILE=~/.config/pokechan/mcp_endpoint.txt .venv/bin/python mcp_pipe.py
```

Linux 可以用 systemd 的用户服务托管同样的命令。

## 配置项

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `POKECHAN_ENDPOINT_FILE` | `~/esp/stackchan_mcp_endpoint.txt` | 接入点地址文件（也可以直接作为 `mcp_pipe.py` 的第一个参数传入） |
| `POKECHAN_HOME_NAME` | 无，必填 | "家"所在城市的名字，会写进工具说明，也会在回答里念出来 |
| `POKECHAN_HOME_LAT` / `_LON` | 无，必填 | "家"的经纬度 |
| `POKECHAN_HOME_TZ` | `auto` | "家"的时区，如 `Asia/Shanghai`；不填时由 Open-Meteo 按经纬度自动判断 |

## 设计细节

- **工具名不和平台自带的重复**：天气工具叫 `weather_forecast`，不叫 `get_weather`，因为 xiaozhi.me 平台自带一个 `get_weather`。说明里写了"优先使用这个天气工具"，实测模型会选这个。
- **控制回复长度**：搜索结果截断在约 1500 字，交给模型转述，网址不念。
- **日志只记方法名和工具名**，不记参数和结果。

## 加新技能

在 `server.py` 里用 `@server.tool(description=...)` 加一个函数，说明里写清楚"什么时候调用"，然后重启服务。在 StackChan 上，没有专门图标的工具会显示通用的"星星"图标；想给它配专属图标，见 [skins.md](skins.md#技能图标)。

## 第三方服务说明

- 天气数据来自 [Open-Meteo](https://open-meteo.com/)，按 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) 授权，需要注明出处。免费 API 只能用于非商业用途。
- 搜索通过 `ddgs` 库访问 DuckDuckGo。这不是官方 API，可能受频率限制，也可能失效。请遵守 DuckDuckGo 的服务条款，不要高频或大量调用。
