"""Landscape cut with music: shots_h.py frames + compose.py titles/captions + music_h.wav + sound effects.

    python compose_h.py   -> out/pokechan_promo_16x9.mp4  (48 s, cuts on the beat)
"""
import subprocess
import wave
from pathlib import Path

import numpy as np
from PIL import Image

import compose as C

ROOT = Path(__file__).resolve().parent
W, H, FPS, SR = 1920, 1080, 30, 48000

# shot-local seconds; one beat = 0.5 s
TIMELINE = [
    dict(shot="h01_reveal", dark=True,
         titles=[(0.3, 1.4, "这是 StackChan。"), (1.8, 4.9, "现在，它会变身。")],
         sfx=[(1.5, "boot")]),
    dict(shot="h02_switch",
         titles=[(0.1, 4.9, "一句话，换一张脸。")],
         says=[(0.3, 0.95, "换成小火龙"), (1.3, 1.95, "换成妙蛙种子"), (2.3, 2.95, "换成杰尼龟"), (3.3, 3.95, "换成百变怪")],
         sfx=[(1.0, "pop"), (2.0, "pop"), (3.0, "pop"), (4.0, "pop")]),
    dict(shot="h03_angry", dark=True,
         titles=[(0.1, 3.9, "情绪，有招牌动作。")],
         says=[(0.05, 0.95, "你又把我的充电线拔了？")],
         sfx=[(1.0, "flame")]),
    dict(shot="h04_sparks",
         sfx=[(1.0, "zap")]),
    dict(shot="h05_cool",
         titles=[(0.1, 2.9, "耍酷，就戴墨镜。")],
         says=[(0.05, 0.95, "你今天真帅。")],
         sfx=[(1.0, "cool")]),
    dict(shot="h06_weather",
         titles=[(0.1, 4.9, "每个技能，都有招式。")],
         says=[(0.0, 0.95, "明天天气怎么样？")],
         sfx=[(0.5, "badge")]),
    dict(shot="h07_news",
         says=[(0.0, 0.95, "今天有什么科技新闻？")],
         sfx=[(0.5, "badge")]),
    dict(shot="h08_search",
         says=[(0.0, 1.4, "帮我搜一下明天的 NBA 比赛都有哪几场")],
         sfx=[(0.5, "badge")]),
    dict(shot="h09_muse", dark=True,
         titles=[(0.1, 4.9, "你的 Muse，住进桌面。")],
         says=[(0.0, 0.95, "我明天有什么安排？")],
         sfx=[(0.5, "badge")]),
    dict(shot="h10_lineup",
         titles=[(0.2, 5.8, "五张脸，一个桌面伙伴。")],
         names=(0.6, 5.8, "皮卡丘  ·  小火龙  ·  妙蛙种子  ·  杰尼龟  ·  百变怪")),
    dict(shot="h11_end", dark=True, end=2.0),
]
FADE_IN, FADE_OUT = 0.4, 0.8


def audio(total):
    with wave.open(str(ROOT / "out" / "music_h.wav")) as w:
        music = np.frombuffer(w.readframes(w.getnframes()), "<i2").reshape(-1, 2) / 32767
    n = int(total * SR)
    fx = np.zeros(n + 2 * SR)
    start = 0.0
    for seg in TIMELINE:
        for t, kind in seg.get("sfx", []):
            s = C.sfx(kind)
            i = int((start + t) * SR)
            fx[i:i + len(s)] += s
        start += len(list((ROOT / "frames" / seg["shot"]).glob("*.png"))) / FPS
    music = np.pad(music, ((0, max(0, n - len(music))), (0, 0)))[:n]
    out = 0.8 * music + 0.4 * fx[:n, None]
    out /= max(1.0, np.abs(out).max() / 0.95)
    path = ROOT / "out" / "mix_h.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(out, -1, 1) * 32767).astype("<i2").tobytes())
    return path


def main():
    segs = [(seg, sorted((ROOT / "frames" / seg["shot"]).glob("*.png"))) for seg in TIMELINE]
    total_frames = sum(len(f) for _, f in segs)
    dur = total_frames / FPS
    wav = audio(dur)
    out = ROOT / "out" / "pokechan_promo_16x9.mp4"
    proc = subprocess.Popen([C.FFMPEG, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                             "-r", str(FPS), "-i", "-", "-i", str(wav), "-c:v", "libx264", "-preset", "slow", "-crf", "18",
                             "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
                             str(out)], stdin=subprocess.PIPE)
    checks = {int(x * FPS) for x in (3.0, 7.5, 11.5, 15.5, 18.5, 22.0, 29.0, 33.0, 39.0, 46.0)}
    k = 0
    for seg, frames in segs:
        for i, src in enumerate(frames):
            frame = Image.open(src).convert("RGBA")
            C.overlay(frame, seg, i / FPS, len(frames) / FPS)
            rgb = frame.convert("RGB")
            gt = k / FPS
            f = min(1.0, gt / FADE_IN, (dur - gt) / FADE_OUT)
            if f < 1:
                rgb = Image.eval(rgb, lambda v, f=max(0.0, f): int(v * f))
            proc.stdin.write(rgb.tobytes())
            if k in checks:
                rgb.save(ROOT / "out" / f"hcheck_{k:04d}.jpg", quality=80)
            k += 1
    proc.stdin.close()
    proc.wait()
    print(f"{out.name}: {k} frames, {k / FPS:.1f}s, {out.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
