"""Moves the Muse device token from the official Muse gadget firmware to PokeChan.

Pairing happens in the official Muse gadget firmware (Muse Gadget SDK): flash it, pair it in the Muse
app, then read its token here, flash PokeChan back and hand the token over. The token is never printed;
only its length is.

  muse_token.py read PORT OUT_FILE   reads the token from the paired official firmware's NVS
                                     (default nvs at 0x11000, size 0xC000; namespace homehub,
                                     key access_token) into OUT_FILE (mode 600)
  muse_token.py send PORT TOKEN_FILE sends it to PokeChan over the serial console (>hatch.token=)
                                     and waits for the Muse connection

Needs esptool and pyserial; "read" also needs IDF_PATH (for ESP-IDF's NVS parser).
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

CHUNK = 400  # console lines are up to 1024 bytes


def read_token(args):
    idf = os.environ.get("IDF_PATH")
    if not idf:
        sys.exit("Set IDF_PATH (source ESP-IDF's export.sh) so the NVS parser can be found.")
    sys.path.insert(0, str(Path(idf) / "components/nvs_flash/nvs_partition_tool"))
    from nvs_parser import NVS_Partition  # noqa: E402

    with tempfile.TemporaryDirectory() as tmp:
        dump = Path(tmp) / "nvs.bin"
        subprocess.run([sys.executable, "-m", "esptool", "--chip", "esp32s3", "--port", args.port, "-b", "921600",
                        "read-flash", args.offset, args.size, str(dump)], check=True, stdout=subprocess.DEVNULL)
        nvs = NVS_Partition("nvs", bytearray(dump.read_bytes()))

    namespaces = {}
    for page in nvs.pages:
        for e in page.entries:
            if e.state == "Written" and e.metadata["namespace"] == 0:
                namespaces[e.data["value"]] = e.key
    token = None
    for page in nvs.pages:
        for e in page.entries:
            if (e.state == "Written" and e.metadata["type"] == "string" and e.key == args.key
                    and namespaces.get(e.metadata["namespace"]) == args.namespace):
                raw = b"".join(bytes(c.raw) for c in e.children)[: e.data["size"]]
                token = raw.rstrip(b"\0").decode()
    if not token:
        sys.exit(f"No {args.namespace}/{args.key} in that NVS: is the official firmware paired?")

    out = Path(args.out).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump({"access_token": token}, f)
    print(f"Saved a {len(token)}-character token to {out} (mode 600).")


def send_token(args):
    import serial

    data = json.loads(Path(args.token_file).expanduser().read_text())
    token = data["access_token"] if isinstance(data, dict) else str(data)

    s = serial.Serial()
    s.port, s.baudrate, s.timeout, s.dtr, s.rts = args.port, 115200, 0.2, False, False
    s.open()
    secret = re.compile(r"(eyJ|mgst_)[A-Za-z0-9._-]+")

    def wait_for(prefix, timeout):
        buf, end = b"", time.time() + timeout
        while time.time() < end:
            buf += s.read(4096)
            while b"\n" in buf:
                raw, buf = buf.split(b"\n", 1)
                line = secret.sub("<redacted>", raw.decode(errors="replace").strip())
                if line.startswith(prefix):
                    return line
        return None

    for i in range(0, len(token), CHUNK):
        cmd = "hatch.token=" if i == 0 else "hatch.token+="
        s.write(b"\n>" + (cmd + token[i:i + CHUNK]).encode() + b"\n")
        print(wait_for("@hatch.token", 5) or "no reply: is PokeChan running on this port?")
    del token

    print("Waiting for Muse to connect (it starts 25 s after boot)...")
    end = time.time() + 120
    while time.time() < end:
        s.write(b"\n>status\n")
        line = wait_for("@status", 5)
        if line and '"Connected"' in line:
            print("Muse connected.")
            return
        time.sleep(3)
    print("Not connected yet; check the log for muse_chat_session errors.")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("read")
    r.add_argument("port")
    r.add_argument("out")
    r.add_argument("--offset", default="0x11000")
    r.add_argument("--size", default="0xC000")
    r.add_argument("--namespace", default="homehub")
    r.add_argument("--key", default="access_token")
    w = sub.add_parser("send")
    w.add_argument("port")
    w.add_argument("token_file")
    args = p.parse_args()
    read_token(args) if args.cmd == "read" else send_token(args)


if __name__ == "__main__":
    main()
