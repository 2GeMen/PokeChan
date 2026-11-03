"""Vertical 1080x1920 cut for Douyin / Xiaohongshu / Reels / Shorts: 30 s, cuts on the beat, original score.

    python compose_v.py   -> out/pokechan_promo_9x16.mp4

Layout keeps text inside the platforms' safe area: titles from y=220, captions and notes between y=1610 and y=1780 (moved down so they clear the robot)
(the bottom ~350 px is covered by the platforms' own caption and buttons).
"""
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import compose as C
from shots_v import BEAT, LENGTHS

ROOT = Path(__file__).resolve().parent
W, H, FPS, SR = 1080, 1920, 30, 48000
DARK, LIGHT, ACCENT = C.DARK_TEXT, C.LIGHT_TEXT, C.ACCENT

# shot start times (s)
START, t = {}, 0.0
for name, beats in LENGTHS.items():
    START[name] = t
    t += beats * BEAT
TOTAL = t
DARK_SHOTS = {"v03_angry", "v08_muse", "v10_end"}

# absolute-time text: (t0, t1, text)
TITLES = [
    (START["v02_switch"] + 0.1, START["v03_angry"] - 0.1, "一句话，换一张脸"),
    (START["v03_angry"] + 0.05, START["v06_weather"] - 0.1, "情绪，有招牌动作"),
    (START["v06_weather"] + 0.05, START["v08_muse"] - 0.1, "每个技能，都有招式"),
    (START["v08_muse"] + 0.05, START["v09_lineup"] - 0.1, "你的 Muse，住进桌面"),
    (START["v09_lineup"] + 0.1, START["v10_end"] - 0.1, "五张脸，一个桌面伙伴"),
]
LABELS = [  # small tag under the title
    (START["v03_angry"] + 0.4, START["v04_sparks"], "生气  →  尾巴着火"),
    (START["v04_sparks"] + 0.4, START["v05_cool"], "生气  →  脸颊放电"),
    (START["v05_cool"] + 0.4, START["v06_weather"] - 0.1, "耍酷  →  戴上墨镜"),
]
SAYS = [
    (START["v02_switch"] + 0.2, START["v02_switch"] + 1.1, "换成小火龙"),
    (START["v02_switch"] + 1.7, START["v02_switch"] + 2.6, "换成杰尼龟"),
    (START["v02_switch"] + 3.2, START["v02_switch"] + 4.1, "换成妙蛙种子"),
    (START["v06_weather"], START["v06_weather"] + 1.4, "明天天气怎么样？"),
    (START["v07_search"], START["v07_search"] + 1.6, "帮我搜一下明天的 NBA 比赛都有哪几场"),
    (START["v08_muse"], START["v08_muse"] + 1.4, "我明天有什么安排？"),
]
SFX = ([(i * BEAT, "pop") for i in range(1, 6)] +
       [(START["v02_switch"] + x, "pop") for x in (1.0, 2.5, 4.0)] +
       [(START["v03_angry"] + 0.5, "flame"), (START["v04_sparks"] + 0.5, "zap"), (START["v05_cool"] + 0.5, "cool"),
        (START["v06_weather"] + 0.5, "badge"), (START["v07_search"], "badge"), (START["v08_muse"] + 0.5, "badge")])


def centered(frame, layer, y, a):
    C.paste(frame, layer, (W - layer.width) / 2, y, a)


def tag_layer(text, dark):
    f = C.font(40, "Bold")
    tw = f.getlength(text)
    w, h = int(tw + 56), 72
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=h // 2, fill=ACCENT)
    l, t, r, b = f.getbbox(text)
    d.text(((w - (r - l)) / 2 - l, (h - (b - t)) / 2 - t), text, font=f, fill=DARK)
    return img


def hook_layers():
    l1 = C.text_layer("我的桌面机器人", 92, DARK, "Black")
    l2 = C.text_layer("会变成宝可梦！", 108, DARK, "Black")
    # white sticker behind the second line, slightly tilted
    hl = Image.new("RGBA", (l2.width + 56, l2.height + 36), (0, 0, 0, 0))
    ImageDraw.Draw(hl).rounded_rectangle((0, 0, hl.width - 1, hl.height - 1), radius=26, fill=(255, 255, 255, 255))
    hl.alpha_composite(l2, (28, 18))
    hl = hl.rotate(-2.5, resample=Image.BICUBIC, expand=True)
    return l1, hl


def overlay(frame, gt, shot, lt):
    dark = shot in DARK_SHOTS
    tc = LIGHT if dark else DARK
    if shot == "v01_hook":
        l1, l2 = hook_layers()
        centered(frame, l1, 200, 1)
        centered(frame, l2, 320, 1)
        sub = C.text_layer("一句话，它就变身", 46, DARK, "Bold")
        centered(frame, sub, 500, 1)
    for t0, t1, text in TITLES:
        a = C.fade_in_out(gt, t0, t1, 0.25, 0.15)
        if a:
            lay = C.text_layer(text, 92, tc, "Black")
            centered(frame, lay, 230 + (1 - C.ease((gt - t0) / 0.3)) * 16, a)
    for t0, t1, text in LABELS:
        a = C.fade_in_out(gt, t0, t1, 0.2, 0.1)
        if a:
            lay = tag_layer(text, dark)
            sc = 0.85 + 0.15 * C.ease((gt - t0) / 0.18)
            lay = lay.resize((int(lay.width * sc), int(lay.height * sc)), Image.LANCZOS)
            centered(frame, lay, 370 + (72 - lay.height) / 2, a)
    for t0, t1, text in SAYS:
        a = C.fade_in_out(gt, t0, t1, 0.15, 0.15)
        if a:
            lay = C.pill(text)
            lay = lay.resize((int(lay.width * 1.25), int(lay.height * 1.25)), Image.LANCZOS)
            centered(frame, lay, 1610 + (1 - C.ease((gt - t0) / 0.2)) * 12, a)
    if shot == "v10_end":
        t0 = 0.4
        logo = C.text_layer("PokeChan", 150, ACCENT, "Black", tracking=2)
        tag = C.text_layer("一只会变身的桌面机器人。", 64, LIGHT, "Bold")
        centered(frame, logo, 200, C.ease((lt - t0) / 0.4))
        centered(frame, tag, 390, C.ease((lt - t0 - 0.2) / 0.4))
        gh = C.text_layer("开源固件  ·  github.com/2GeMen/PokeChan", 40, (161, 161, 166), "Medium")
        centered(frame, gh, 1480, C.ease((lt - t0 - 0.5) / 0.4))
        cta = tag_layer("评论区说说：你想要哪只宝可梦？", True)
        centered(frame, cta, 1555, C.ease((lt - t0 - 0.8) / 0.4))
        for i, line in enumerate(("非官方同人项目，与任天堂、The Pokémon Company、M5Stack、Meta 无关联。",
                                  "Pokémon 角色形象权利归原权利人所有。")):
            d = C.text_layer(line, 24, (130, 130, 135), "Regular")
            centered(frame, d, 1665 + i * 34, C.ease((lt - t0 - 0.8) / 0.4))
    else:
        note = C.text_layer("非官方同人项目 · 3D 渲染演示", 24, (150, 150, 155) if dark else (110, 110, 115), "Regular")
        centered(frame, note, 1750, 0.85)


def audio(with_music=True):
    """stereo: the score keeps its width; effects sit in the centre"""
    with wave.open(str(ROOT / "out" / "music_v.wav")) as w:
        music = np.frombuffer(w.readframes(w.getnframes()), "<i2").reshape(-1, 2) / 32767
    if not with_music:
        music = music * 0
    n = int(TOTAL * SR)
    fx = np.zeros(n + SR * 2)
    for t, kind in SFX:
        s = C.sfx(kind)
        i = int(t * SR)
        fx[i:i + len(s)] += s
    music = np.pad(music, ((0, max(0, n - len(music))), (0, 0)))[:n]
    out = 0.8 * music + (0.4 if with_music else 0.8) * fx[:n, None]
    out /= max(1.0, np.abs(out).max() / 0.95)
    path = ROOT / "out" / ("mix_v.wav" if with_music else "mix_v_sfx.wav")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(out, -1, 1) * 32767).astype("<i2").tobytes())
    return path


def main():
    # --no-music: sound effects only, for adding a licensed track from the platform's own library
    with_music = "--no-music" not in sys.argv
    wav = audio(with_music)
    out = ROOT / "out" / ("pokechan_promo_9x16.mp4" if with_music else "pokechan_promo_9x16_sfx_only.mp4")
    proc = subprocess.Popen([C.FFMPEG, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                             "-r", str(FPS), "-i", "-", "-i", str(wav), "-c:v", "libx264", "-preset", "slow", "-crf", "18",
                             "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
                             str(out)], stdin=subprocess.PIPE)
    checks = {int(x * FPS) for x in (0.0, 3.4, 9.0, 11.5, 13.5, 15.3, 18.3, 20.3, 25.0, 29.0)}
    k = 0
    for shot in LENGTHS:
        frames = sorted((ROOT / "frames" / shot).glob("*.png"))
        for i, src in enumerate(frames):
            frame = Image.open(src).convert("RGBA")
            overlay(frame, k / FPS, shot, i / FPS)
            rgb = frame.convert("RGB")
            left = TOTAL - k / FPS
            if left < 0.6:
                rgb = Image.eval(rgb, lambda v, f=max(0.0, left / 0.6): int(v * f))
            proc.stdin.write(rgb.tobytes())
            if k in checks:
                rgb.save(ROOT / "out" / f"vcheck_{k:04d}.jpg", quality=80)
            k += 1
    proc.stdin.close()
    proc.wait()
    print(f"{out.name}: {k} frames, {k / FPS:.1f}s, {out.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
