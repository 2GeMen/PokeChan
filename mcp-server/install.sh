#!/bin/zsh
# Installs PokeChan's MCP server as a login service on macOS.
# Usage: ./install.sh [ENDPOINT_FILE]   (default ~/.config/pokechan/mcp_endpoint.txt)
# Home city (required): set POKECHAN_HOME_NAME, _LAT, _LON before running; _TZ is optional.
set -e
cd "$(dirname "$0")"
DIR=$PWD
ENDPOINT_FILE=${1:-$HOME/.config/pokechan/mcp_endpoint.txt}
if [[ ! -s $ENDPOINT_FILE ]]; then
    echo "Put your MCP endpoint URL (wss://...) in $ENDPOINT_FILE first, then run this again."
    echo "Keep it private: it contains your access token."
    exit 1
fi
chmod 600 "$ENDPOINT_FILE"
if [[ -z $POKECHAN_HOME_NAME || -z $POKECHAN_HOME_LAT || -z $POKECHAN_HOME_LON ]]; then
    echo "Set your home city first, for example:"
    echo "  POKECHAN_HOME_NAME=上海 POKECHAN_HOME_LAT=31.2304 POKECHAN_HOME_LON=121.4737 ./install.sh"
    echo "Coordinates: https://open-meteo.com/en/docs/geocoding-api"
    exit 1
fi

command -v uv >/dev/null || { echo "Needs uv: https://docs.astral.sh/uv/"; exit 1; }
uv venv -q --python 3.12 .venv
uv pip install -q --python .venv/bin/python -r pyproject.toml
mkdir -p logs

PLIST=~/Library/LaunchAgents/com.pokechan.mcp.plist
sed -e "s|__DIR__|$DIR|g" -e "s|__ENDPOINT_FILE__|$ENDPOINT_FILE|g" \
    -e "s|__HOME_NAME__|$POKECHAN_HOME_NAME|" -e "s|__HOME_LAT__|$POKECHAN_HOME_LAT|" \
    -e "s|__HOME_LON__|$POKECHAN_HOME_LON|" -e "s|__HOME_TZ__|${POKECHAN_HOME_TZ:-auto}|" \
    launchd/com.pokechan.mcp.plist.template > "$PLIST"
launchctl bootout gui/$(id -u)/com.pokechan.mcp 2>/dev/null || true
launchctl bootstrap gui/$(id -u) "$PLIST"
echo "Installed. Log: $DIR/logs/mcp_pipe.log"
