# PokeChan MCP server

Weather (Open-Meteo), web search and news search (DuckDuckGo) for StackChan, served to the
StackChan World App's MCP endpoint from your own computer. No API keys needed.

```bash
mkdir -p ~/.config/pokechan && pbpaste > ~/.config/pokechan/mcp_endpoint.txt   # the wss:// URL from the app
POKECHAN_HOME_NAME=上海 POKECHAN_HOME_LAT=31.2304 POKECHAN_HOME_LON=121.4737 \
    ./install.sh  # macOS: venv + launchd login service; home city is required
```

Full guide (Chinese): [docs/pokechan/mcp-server.md](../docs/pokechan/mcp-server.md).
Weather data by [Open-Meteo.com](https://open-meteo.com/) (CC BY 4.0).
