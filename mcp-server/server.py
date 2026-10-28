"""StackChan's tools on the Mac: weather and web search, as an MCP server over stdio.

mcp_pipe.py connects it to the StackChan World App's MCP endpoint, so the
xiaozhi model on the robot can call these. Both work without API keys:
weather from Open-Meteo, search from DuckDuckGo (ddgs).
"""

import logging
import os

import httpx
from ddgs import DDGS
from mcp.server.mcpserver import MCPServer

log = logging.getLogger("stackchan-tools")
for noisy in ("httpx", "ddgs", "primp"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

# Home, used when no city is given. Set POKECHAN_HOME_NAME / _LAT / _LON / _TZ to your own;
# the default is Shanghai.
HOME = {
    "name": os.environ.get("POKECHAN_HOME_NAME", "上海"),
    "latitude": float(os.environ.get("POKECHAN_HOME_LAT", "31.2304")),
    "longitude": float(os.environ.get("POKECHAN_HOME_LON", "121.4737")),
    "timezone": os.environ.get("POKECHAN_HOME_TZ", "Asia/Shanghai"),
}
REPLY_MAX = 1500   # characters back to the model; it reads them out, so keep it short

# WMO weather codes (Open-Meteo), in Chinese.
WMO = {
    0: "晴", 1: "大致晴朗", 2: "多云", 3: "阴",
    45: "有雾", 48: "冻雾",
    51: "小毛毛雨", 53: "毛毛雨", 55: "大毛毛雨", 56: "冻毛毛雨", 57: "强冻毛毛雨",
    61: "小雨", 63: "中雨", 65: "大雨", 66: "冻雨", 67: "强冻雨",
    71: "小雪", 73: "中雪", 75: "大雪", 77: "雪粒",
    80: "阵雨", 81: "较强阵雨", 82: "强阵雨", 85: "阵雪", 86: "强阵雪",
    95: "雷阵雨", 96: "雷阵雨伴冰雹", 99: "强雷阵雨伴冰雹",
}

server = MCPServer(
    name="stackchan-tools",
    instructions="天气和联网搜索工具。回答用户时用简短自然的中文口语转述，不要念网址。",
)


def _geocode(client: httpx.Client, city: str) -> dict | None:
    for lang in ("zh", "en"):
        r = client.get("https://geocoding-api.open-meteo.com/v1/search",
                       params={"name": city, "count": 1, "language": lang, "format": "json"})
        r.raise_for_status()
        hits = r.json().get("results") or []
        if hits:
            h = hits[0]
            name = h.get("name", city)
            where = "，".join(x for x in (h.get("admin1"), h.get("country")) if x)
            return {"name": f"{name}（{where}）" if where else name, "latitude": h["latitude"],
                    "longitude": h["longitude"], "timezone": h.get("timezone", "auto")}
    return None


@server.tool(description="（优先使用这个天气工具，数据来自 Open-Meteo，比平台自带的更准。）查询天气：当前天气和未来几天的预报（温度、天气、降水概率、风）。"
                         f"city 留空表示用户所在的{HOME['name']}；问别的城市时填城市名，中英文都可以。"
                         "days 是预报天数，1 到 7，默认 3。")
def weather_forecast(city: str = "", days: int = 3) -> str:
    days = max(1, min(7, days))
    with httpx.Client(timeout=10) as client:
        place = HOME if not city.strip() else _geocode(client, city.strip())
        if not place:
            return f"没找到“{city}”这个地方，可以换个说法或用英文城市名。"
        r = client.get("https://api.open-meteo.com/v1/forecast", params={
            "latitude": place["latitude"], "longitude": place["longitude"], "timezone": place["timezone"],
            "forecast_days": days,
            "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m,relative_humidity_2m",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,"
                     "wind_speed_10m_max",
        })
        r.raise_for_status()
        data = r.json()
    cur, daily = data["current"], data["daily"]
    lines = [f"{place['name']}现在{WMO.get(cur['weather_code'], '天气未知')}，"
             f"{cur['temperature_2m']:.0f}度，体感{cur['apparent_temperature']:.0f}度，"
             f"湿度{cur['relative_humidity_2m']}%，风速每小时{cur['wind_speed_10m']:.0f}公里。"]
    names = ["今天", "明天", "后天"]
    for i, day in enumerate(daily["time"]):
        label = names[i] if i < len(names) else day
        rain = daily["precipitation_probability_max"][i]
        lines.append(f"{label}{WMO.get(daily['weather_code'][i], '天气未知')}，"
                     f"{daily['temperature_2m_min'][i]:.0f}到{daily['temperature_2m_max'][i]:.0f}度，"
                     f"降水概率{rain if rain is not None else '未知'}%，"
                     f"最大风速每小时{daily['wind_speed_10m_max'][i]:.0f}公里。")
    return "\n".join(lines)


def _format(results: list[dict], with_date: bool) -> str:
    out, size = [], 0
    for i, r in enumerate(results, 1):
        title = (r.get("title") or "").strip()
        body = (r.get("body") or r.get("excerpt") or "").strip()
        date = f"（{r['date'][:10]}）" if with_date and r.get("date") else ""
        src = r.get("source") or r.get("href", "").split("/")[2] if (r.get("source") or r.get("href")) else ""
        item = f"{i}. {title}{date}：{body}" + (f" ——{src}" if src else "")
        if size + len(item) > REPLY_MAX:
            break
        out.append(item)
        size += len(item)
    return "\n".join(out)


@server.tool(description="联网搜索网页，获取实时或最新的信息（比如事实查询、营业时间、比赛结果、价格、"
                         "用户问的你不确定或可能过时的事）。query 用最可能搜到结果的关键词，中英文都可以。"
                         "返回几条结果的标题和摘要，请用口语概括回答，不要念网址。")
def web_search(query: str, max_results: int = 5) -> str:
    max_results = max(1, min(8, max_results))
    try:
        results = DDGS().text(query, max_results=max_results)
    except Exception as e:
        log.warning("web_search failed: %s", e)
        return f"搜索暂时失败：{e}"
    return _format(results, with_date=False) or "没有搜到相关结果。"


@server.tool(description="搜索最新新闻。用户问最近发生了什么、某件事的最新消息、今天的新闻时调用。"
                         "query 是新闻主题，中英文都可以。返回带日期的新闻摘要，请用口语概括。")
def news_search(query: str, max_results: int = 5) -> str:
    max_results = max(1, min(8, max_results))
    try:
        results = DDGS().news(query, max_results=max_results)
    except Exception as e:
        log.warning("news_search failed: %s", e)
        return f"新闻搜索暂时失败：{e}"
    return _format(results, with_date=True) or "没有搜到相关新闻。"


if __name__ == "__main__":
    server.run("stdio")
