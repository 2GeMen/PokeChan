"""Encodes rendered frame folders into H.264 clips.

    python encode.py                 # every frames/<shot>/ -> clips/<shot>.mp4
    python encode.py s03_charmander_angry
"""
import subprocess
import sys
from pathlib import Path

import imageio_ffmpeg

ROOT = Path(__file__).resolve().parent
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def encode(name, fps=30):
    src = ROOT / "frames" / name
    out = ROOT / "clips" / f"{name}.mp4"
    out.parent.mkdir(exist_ok=True)
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-framerate", str(fps), "-i", str(src / "%05d.png"),
                    "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart", str(out)], check=True)
    n = len(list(src.glob("*.png")))
    print(f"{out.name}: {n} frames, {n / fps:.1f}s, {out.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    names = sys.argv[1:] or sorted(p.name for p in (ROOT / "frames").iterdir() if p.is_dir() and p.name[:1] == "s" and p.name[1:3].isdigit())
    for n in names:
        encode(n)
