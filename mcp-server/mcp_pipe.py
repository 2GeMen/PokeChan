"""Connects server.py to the StackChan World App's MCP endpoint.

The endpoint is a WebSocket URL with a token in it (from the app's MCP endpoint
page), read from ENDPOINT_FILE so it stays out of this repo. Each WebSocket text
frame is one JSON-RPC message; server.py speaks the same messages as lines on
stdin/stdout. On a dropped connection both sides are restarted, with backoff.

Usage: mcp_pipe.py [ENDPOINT_FILE]
  default: $POKECHAN_ENDPOINT_FILE, else ~/esp/stackchan_mcp_endpoint.txt
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

import websockets

HERE = Path(__file__).resolve().parent
ENDPOINT_FILE = Path(sys.argv[1] if len(sys.argv) > 1
                     else os.environ.get("POKECHAN_ENDPOINT_FILE", "~/esp/stackchan_mcp_endpoint.txt")).expanduser()
SERVER = [sys.executable, str(HERE / "server.py")]
BACKOFF_MIN, BACKOFF_MAX = 1, 300

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("mcp_pipe")


def log_request(msg: str) -> None:
    """Logs what the endpoint asks for: the method, and the tool name of a call."""
    try:
        req = json.loads(msg)
    except ValueError:
        return
    method = req.get("method")
    if method == "tools/call":
        log.info("tools/call %s", req.get("params", {}).get("name"))
    elif method and method != "ping":
        log.info("%s", method)


def read_endpoint() -> str:
    url = ENDPOINT_FILE.read_text().strip()
    if not url.startswith(("ws://", "wss://")):
        raise SystemExit(f"{ENDPOINT_FILE} must hold the endpoint's ws:// or wss:// URL")
    return url


async def pipe_once(url: str) -> None:
    host = urlsplit(url).hostname
    async with websockets.connect(url, ping_interval=30, ping_timeout=30, max_size=4 * 1024 * 1024) as ws:
        log.info("connected to %s", host)
        proc = await asyncio.create_subprocess_exec(
            *SERVER, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE, limit=4 * 1024 * 1024)

        async def ws_to_server():
            async for msg in ws:
                if isinstance(msg, bytes):
                    msg = msg.decode()
                log_request(msg)
                proc.stdin.write(msg.encode() + b"\n")
                await proc.stdin.drain()

        async def server_to_ws():
            while line := await proc.stdout.readline():
                await ws.send(line.decode().rstrip("\n"))

        async def server_log():
            while line := await proc.stderr.readline():
                log.info("server: %s", line.decode().rstrip())

        tasks = [asyncio.create_task(t()) for t in (ws_to_server, server_to_ws, server_log)]
        try:
            await asyncio.wait(tasks[:2], return_when=asyncio.FIRST_COMPLETED)
        finally:
            for t in tasks:
                t.cancel()
            if proc.returncode is None:
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), 5)
                except asyncio.TimeoutError:
                    proc.kill()


async def main() -> None:
    backoff = BACKOFF_MIN
    while True:
        try:
            await pipe_once(read_endpoint())
            backoff = BACKOFF_MIN
            log.info("connection closed; reconnecting")
        except (OSError, websockets.WebSocketException) as e:
            log.warning("connection failed: %s; retrying in %ds", e, backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, BACKOFF_MAX)


if __name__ == "__main__":
    os.chdir(HERE)
    asyncio.run(main())
