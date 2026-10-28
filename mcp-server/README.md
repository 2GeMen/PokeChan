# PokeChan MCP server

Weather (Open-Meteo), web search and news search (DuckDuckGo) for StackChan, served to the
StackChan World App's MCP endpoint from your own computer. No API keys needed.

```bash
mkdir -p ~/.config/pokechan && pbpaste > ~/.config/pokechan/mcp_endpoint.txt   # the wss:// URL from the app
./install.sh      # macOS: venv + launchd login service
```

Full guide (Chinese): [docs/pokechan/mcp-server.md](../docs/pokechan/mcp-server.md).
Weather data by [Open-Meteo.com](https://open-meteo.com/) (CC BY 4.0).
