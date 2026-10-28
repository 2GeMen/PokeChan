"""Composes the promo: rendered shots + titles, dialogue captions, end card, and synthesized sound effects.

    python compose.py            -> out/pokechan_promo_16x9.mp4

Everything here is original: text is set in Noto Sans SC (OFL), sound effects are synthesized below.
No music; add it from the platform's licensed library when posting.
"""
import math
import subprocess
import wave
from functools import lru_cache
from pathlib import Path

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
FONT = ROOT / "fonts" / "NotoSansSC.ttf"
FPS, W, H, SR = 30, 1920, 1080, 48000
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

DARK_TEXT, LIGHT_TEXT, ACCENT = (29, 29, 31), (245, 245, 247), (255, 216, 58)

# --------------------------------------------------------------------------- timeline
# Per shot: titles (big line), says (dialogue captions), sfx. Times are shot-local seconds.
TIMELINE = [
    dict(shot="s01_reveal", dark=True,
         titles=[(0.6, 2.9, "这是 StackChan。"), (3.3, 6.3, "现在，它会变身。")],
         sfx=[(0.0, "drone"), (1.6, "boot")]),
    dict(shot="s02_switch",
         titles=[(0.2, 7.3, "一句话，换一张脸。")],
         says=[(0.8, 1.7, "换成小火龙"), (2.3, 3.2, "换成妙蛙种子"), (3.8, 4.7, "换成杰尼龟"), (5.3, 6.2, "换成百变怪")],
         sfx=[(1.5, "pop"), (3.0, "pop"), (4.5, "pop"), (6.0, "pop")]),
    dict(shot="s03_charmander_angry", dark=True,
         titles=[(0.2, 4.8, "情绪，有招牌动作。")],
         says=[(0.3, 1.5, "你又把我的充电线拔了？")],
         sfx=[(1.6, "flame")]),
    dict(shot="s04_pikachu_sparks",
         sfx=[(1.2, "zap")]),
    dict(shot="s05_squirtle_cool",
         titles=[(0.3, 4.3, "耍酷，就戴墨镜。")],
         says=[(0.2, 1.3, "你今天真帅。")],
         sfx=[(1.4, "cool")]),
    dict(shot="s06_skill_weather",
         titles=[(0.2, 5.8, "每个技能，都有招式。")],
         says=[(0.0, 1.3, "明天天气怎么样？")],
         sfx=[(0.5, "badge")]),
    dict(shot="s07_skill_news",
         says=[(0.0, 1.3, "今天有什么科技新闻？")],
         sfx=[(0.4, "badge")]),
    dict(shot="s08_skill_search",
         says=[(0.0, 1.5, "帮我搜一下明天的 NBA 比赛都有哪几场")],
         sfx=[(0.4, "badge")]),
    dict(shot="s09_muse", dark=True,
         titles=[(0.2, 6.2, "你的 Muse，住进桌面。")],
         says=[(0.0, 1.5, "我明天有什么安排？")],
         sfx=[(0.6, "badge")]),
    dict(shot="s10_lineup",
         titles=[(0.3, 6.8, "五张脸，一个桌面伙伴。")],
         names=(1.0, 6.8, "皮卡丘  ·  小火龙  ·  妙蛙种子  ·  杰尼龟  ·  百变怪"),
         sfx=[(0.3, "swell")]),
    dict(shot="s11_end", dark=True, hold=2.0, end=2.0,
         sfx=[(2.0, "chord")]),
]
FADE_IN, FADE_OUT = 0.6, 0.6


# --------------------------------------------------------------------------- text
@lru_cache(None)
def font(size, weight="Bold"):
    f = ImageFont.truetype(str(FONT), size)
    f.set_variation_by_name(weight)
    return f


@lru_cache(None)
def text_layer(text, size, color, weight="Bold", tracking=0):
    f = font(size, weight)
    l, t, r, b = f.getbbox(text)
    img = Image.new("RGBA", (r - l + 8 + tracking * len(text), b - t + 8), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if tracking:
        x = 4
        for ch in text:
            d.text((x - l, 4 - t), ch, font=f, fill=color)
            x += f.getlength(ch) + tracking
    else:
        d.text((4 - l, 4 - t), text, font=f, fill=color)
    return img


@lru_cache(None)
def pill(text):
    """dialogue caption: a dark rounded pill with a small speech mark"""
    f = font(38, "Medium")
    tw = f.getlength(text)
    pad_x, h = 34, 76
    w = int(tw + pad_x * 2 + 44)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=h // 2, fill=(20, 20, 22, 210))
    # speech mark: a small bubble
    cx, cy = pad_x + 12, h // 2
    d.ellipse((cx - 12, cy - 11, cx + 12, cy + 9), fill=ACCENT)
    d.polygon([(cx - 8, cy + 4), (cx - 12, cy + 15), (cx, cy + 7)], fill=ACCENT)
    l, t, r, b = f.getbbox(text)
    d.text((pad_x + 44 - l, (h - (b - t)) // 2 - t), text, font=f, fill=LIGHT_TEXT)
    return img


def ease(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def fade_in_out(t, t0, t1, fin=0.45, fout=0.3):
    if t < t0 or t > t1:
        return 0.0
    return min(ease((t - t0) / fin), ease((t1 - t) / fout))


def paste(frame, layer, x, y, alpha):
    if alpha <= 0.01:
        return
    if alpha < 0.999:
        layer = layer.copy()
        layer.putalpha(layer.getchannel("A").point(lambda a: int(a * alpha)))
    frame.alpha_composite(layer, (int(x), int(y)))


def overlay(frame, seg, t, dur):
    dark = seg.get("dark", False)
    tc = LIGHT_TEXT if dark else DARK_TEXT
    for t0, t1, text in seg.get("titles", []):
        a = fade_in_out(t, t0, t1)
        lay = text_layer(text, 84, tc, "Bold")
        rise = (1 - ease((t - t0) / 0.5)) * 18
        paste(frame, lay, (W - lay.width) / 2, 92 + rise, a)
    for t0, t1, text in seg.get("says", []):
        a = fade_in_out(t, t0, t1, 0.2, 0.2)
        lay = pill(text)
        paste(frame, lay, (W - lay.width) / 2, H - 170 + (1 - ease((t - t0) / 0.25)) * 12, a)
    if "names" in seg:
        t0, t1, text = seg["names"]
        lay = text_layer(text, 34, (110, 110, 115), "Medium")
        paste(frame, lay, (W - lay.width) / 2, H - 190, fade_in_out(t, t0, t1))
    if "end" in seg:
        t0 = seg["end"]
        logo = text_layer("PokeChan", 120, ACCENT, "Black", tracking=2)
        tag = text_layer("一只会变身的桌面机器人。", 60, LIGHT_TEXT, "Bold")
        gh = text_layer("开源固件  ·  GitHub 即将上线", 34, (161, 161, 166), "Medium")
        paste(frame, logo, (W - logo.width) / 2, 80, ease((t - t0) / 0.6))
        paste(frame, tag, (W - tag.width) / 2, 225, ease((t - t0 - 0.3) / 0.6))
        paste(frame, gh, (W - gh.width) / 2, H - 200, ease((t - t0 - 0.7) / 0.6))
        disc = text_layer("非官方同人项目，与任天堂、The Pokémon Company、M5Stack、Meta 无关联。Pokémon 角色形象权利归原权利人所有。",
                          22, (120, 120, 125), "Regular")
        paste(frame, disc, (W - disc.width) / 2, H - 120, ease((t - t0 - 0.7) / 0.6))
    # small, constant corner note (honest labelling on every frame)
    note = text_layer("非官方同人项目 · 3D 渲染演示", 20, (150, 150, 155) if dark else (120, 120, 125), "Regular")
    paste(frame, note, W - note.width - 36, H - note.height - 26, 0.8)


# --------------------------------------------------------------------------- sound effects (synthesized)
def env(n, attack, decay):
    t = np.arange(n) / SR
    return np.minimum(1, t / max(attack, 1e-4)) * np.exp(-t / decay)


def tone(freq, dur, attack=0.004, decay=0.25, harmonics=((1, 1.0),)):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = sum(a * np.sin(2 * np.pi * freq * k * t) for k, a in harmonics)
    return s * env(n, attack, decay)


def noise(dur, seed=0):
    return np.random.default_rng(seed).standard_normal(int(dur * SR))


def lowpass(x, cutoff):
    a = math.exp(-2 * math.pi * cutoff / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i, v in enumerate(x):
        acc = (1 - a) * v + a * acc
        y[i] = acc
    return y


def mix(a, b, delay=0.0):
    """a plus b started `delay` seconds later, padded to the longer of the two"""
    b = np.pad(b, (int(delay * SR), 0))
    n = max(len(a), len(b))
    return np.pad(a, (0, n - len(a))) + np.pad(b, (0, n - len(b)))


def sfx(kind):
    if kind == "boot":
        bell = ((1, 1.0), (2, 0.35), (3.01, 0.15))
        return mix(0.32 * tone(1318.5, 1.4, decay=0.45, harmonics=bell), 0.22 * tone(1975.5, 1.2, decay=0.4, harmonics=bell), 0.09)
    if kind == "pop":
        n = int(0.12 * SR)
        t = np.arange(n) / SR
        f = 520 + 900 * (t / t[-1])
        return 0.35 * np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.002, 0.035)
    if kind == "badge":
        return mix(0.22 * tone(1567.98, 0.7, decay=0.22, harmonics=((1, 1), (2, 0.2))),
                   0.2 * tone(2093.0, 0.6, decay=0.2, harmonics=((1, 1), (2, 0.2))), 0.08)
    if kind == "flame":
        n = int(1.4 * SR)
        x = lowpass(noise(1.4, 3), 900)
        t = np.arange(n) / SR
        e = np.minimum(1, t / 0.18) * np.exp(-np.maximum(0, t - 0.2) / 0.45)
        return 0.9 * x * e
    if kind == "zap":
        out = np.zeros(int(0.9 * SR))
        rng = np.random.default_rng(5)
        for k in range(9):
            s = int(rng.uniform(0, 0.75) * SR)
            b = rng.standard_normal(int(0.03 * SR)) * env(int(0.03 * SR), 0.001, 0.01)
            out[s:s + len(b)] += 0.35 * b
        n = len(out)
        t = np.arange(n) / SR
        out += 0.08 * np.sign(np.sin(2 * np.pi * 120 * t)) * np.exp(-t / 0.35)
        return out
    if kind == "cool":
        return mix(0.25 * tone(1046.5, 0.5, decay=0.12), 0.25 * tone(1568.0, 0.6, decay=0.2), 0.11)
    if kind == "drone":
        n = int(6.0 * SR)
        t = np.arange(n) / SR
        e = np.minimum(1, t / 1.5) * np.minimum(1, (6.0 - t) / 1.5)
        return 0.12 * e * (np.sin(2 * np.pi * 55 * t) + 0.5 * np.sin(2 * np.pi * 82.4 * t) + 0.25 * np.sin(2 * np.pi * 110 * t))
    if kind == "swell":
        n = int(2.5 * SR)
        t = np.arange(n) / SR
        e = np.sin(np.pi * np.minimum(1, t / 2.5)) ** 2
        return 0.07 * e * sum(np.sin(2 * np.pi * f * t) for f in (261.6, 329.6, 392.0, 523.3))
    if kind == "chord":
        n = int(3.5 * SR)
        out = np.zeros(n)
        for i, f in enumerate((523.3, 659.3, 784.0, 1046.5)):
            s = tone(f, 3.5 - i * 0.07, attack=0.01, decay=1.1, harmonics=((1, 1), (2, 0.25)))
            out[int(i * 0.07 * SR):int(i * 0.07 * SR) + len(s)] += 0.13 * s
        return out
    raise KeyError(kind)


def write_wav(path, x):
    x = np.clip(x, -1, 1)
    st = np.stack([x, x], axis=1)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((st * 32767).astype("<i2").tobytes())


# --------------------------------------------------------------------------- main
def main():
    out_dir = ROOT / "out"
    out_dir.mkdir(exist_ok=True)
    segs, total = [], 0
    for seg in TIMELINE:
        frames = sorted((ROOT / "frames" / seg["shot"]).glob("*.png"))
        n = len(frames) + int(seg.get("hold", 0) * FPS)
        segs.append((seg, frames, total, n))
        total += n
    dur = total / FPS

    audio = np.zeros(int(dur * SR) + SR)
    for seg, _, start, _ in segs:
        for t, kind in seg.get("sfx", []):
            s = sfx(kind)
            i = int((start / FPS + t) * SR)
            audio[i:i + len(s)] += s[:len(audio) - i]
    audio = audio[:int(dur * SR)]
    fade = int(FADE_OUT * SR)
    audio[-fade:] *= np.linspace(1, 0, fade)
    wav = out_dir / "sfx.wav"
    write_wav(wav, audio * 0.9)

    out = out_dir / "pokechan_promo_16x9.mp4"
    proc = subprocess.Popen([FFMPEG, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                             "-r", str(FPS), "-i", "-", "-i", str(wav), "-c:v", "libx264", "-preset", "slow", "-crf", "18",
                             "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
                             str(out)], stdin=subprocess.PIPE)
    k = 0
    for seg, frames, start, n in segs:
        for i in range(n):
            src = frames[min(i, len(frames) - 1)]
            frame = Image.open(src).convert("RGBA")
            overlay(frame, seg, i / FPS, n / FPS)
            rgb = frame.convert("RGB")
            gt = k / FPS
            fade = min(1.0, gt / FADE_IN, (dur - gt) / FADE_OUT)
            if fade < 1:
                rgb = Image.eval(rgb, lambda v, f=max(0.0, fade): int(v * f))
            proc.stdin.write(rgb.tobytes())
            if k % 300 == 0:
                print(f"{k}/{total}", flush=True)
            if k in (int(4.0 * FPS), int(9.5 * FPS), int(15.5 * FPS), int(28.5 * FPS), int(43.0 * FPS), int(52.0 * FPS), total - 10):
                rgb.save(out_dir / f"check_{k:04d}.jpg", quality=80)
            k += 1
    proc.stdin.close()
    proc.wait()
    print(f"{out.name}: {total} frames, {dur:.1f}s, {out.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
