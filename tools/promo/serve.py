"""Local render server for the promo pipeline.

Serves the repository root (so the page can load app/assets/stack_chan_model.glb) and saves the frames
the page POSTs:  POST /frame/<clip>/<n>  body = PNG bytes  -> tools/promo/frames/<clip>/<n:05d>.png

    python serve.py [port]      then open http://localhost:8765/tools/promo/web/render.html
"""
import http.server
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8765


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(REPO), **kw)

    def do_POST(self):
        m = re.fullmatch(r"/frame/([\w-]+)/(\d+)", self.path)
        if not m:
            self.send_error(404)
            return
        out = ROOT / "frames" / m.group(1)
        out.mkdir(parents=True, exist_ok=True)
        data = self.rfile.read(int(self.headers["Content-Length"]))
        (out / f"{int(m.group(2)):05d}.png").write_bytes(data)
        self.send_response(204)
        self.end_headers()

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, *a):
        pass


http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
