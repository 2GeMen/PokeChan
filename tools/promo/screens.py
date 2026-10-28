"""Renders StackChan screen frames (640x480, 2x the real 320x240) from the firmware's own face generator.

The layout and timing mirror the firmware: pokemon.cpp (eyes, mouth, fx layers) and show_badge() in
stackchan_display.cc (skill badge top right, overshoot pop, bob, fade).
"""
import hashlib
import math
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent
GEN_DIR = ROOT.parents[1] / "firmware/tools/pokemon_faces"  # the firmware's own face generator
sys.path.insert(0, str(GEN_DIR))
import gen_faces as gen  # noqa: E402

K = 2                      # output scale vs the real screen
gen.S = 4 * K              # draw at the same 4x supersampling, but keep 2x on output
gen.finish = lambda img: img.resize((img.width // 4, img.height // 4), Image.LANCZOS)

W, H = gen.W * K, gen.H * K
OUT = ROOT / "screens"

_sprites = {}


def sprites(name):
    """All sprites of one character at 2x, drawn once."""
    if name not in _sprites:
        c = gen.CHARS[name]
        s = {"bg": gen.draw_background(name, c).convert("RGBA"), "backdrop": c["backdrop"]}
        for st in gen.EYE_STATES:
            s[f"eye_{st}_l"] = gen.draw_eye(c, st, True)
            s[f"eye_{st}_r"] = gen.draw_eye(c, st, False)
        for st in gen.MOUTH_STATES:
            s[f"mouth_{st}"] = gen.draw_mouth(c, st)
        s["fx"] = gen.fx_layers(name)
        _sprites[name] = s
    return _sprites[name]


_icons = {}


def icon(key):
    if key not in _icons:
        ring, fn = gen.ICONS[key]
        _icons[key] = gen.badge(ring, fn)
    return _icons[key]


def face(name, eyes="neutral", mouth=None, look=(0, 0), fx_frame=0, fx_mood=None,
         badge=None, badge_scale=1.0, badge_dy=0.0, badge_opa=1.0, brightness=1.0, flash=0.0):
    """One screen frame. look: idle gaze -100..100 like Feature::setPosition. Returns an RGB image."""
    s = sprites(name)
    mouth = mouth or (eyes if eyes in gen.EMOTIONS else "neutral")
    mood = fx_mood or eyes
    img = Image.new("RGBA", (W, H), gen.rgba(s["backdrop"]))

    def add_fx(behind):
        for x, y, moods, is_behind in s["fx"]:
            frames = moods.get(mood) or moods.get("any") or []
            if frames and is_behind == behind:
                f = frames[fx_frame % len(frames)]
                img.alpha_composite(f, (W // 2 + x * K - f.width // 2, H // 2 + y * K - f.height // 2))

    ex = round(look[0] / 100 * 12 * K)
    ey = round(look[1] / 100 * 12 * K)
    mx = round(look[0] / 100 * 10 * K)
    my = round(look[1] / 100 * 10 * K)
    ew, eh = gen.EYE_W * K, gen.EYE_H * K
    mw, mh = gen.MOUTH_W * K, gen.MOUTH_H * K

    add_fx(True)
    img.alpha_composite(s["bg"])
    img.alpha_composite(s[f"eye_{eyes}_l"], (W // 2 - gen.EYE_DX * K - ew // 2 + ex, gen.EYE_Y * K - eh // 2 + ey))
    img.alpha_composite(s[f"eye_{eyes}_r"], (W // 2 + gen.EYE_DX * K - ew // 2 + ex, gen.EYE_Y * K - eh // 2 + ey))
    img.alpha_composite(s[f"mouth_{mouth}"], (W // 2 - mw // 2 + mx, gen.MOUTH_Y * K - mh // 2 + my))
    add_fx(False)

    if badge and badge_opa > 0 and badge_scale > 0.01:
        b = icon(badge)
        size = max(1, round(b.width * badge_scale))
        bs = b.resize((size, size), Image.LANCZOS)
        if badge_opa < 1:
            bs.putalpha(bs.getchannel("A").point(lambda a: int(a * badge_opa)))
        # LV_ALIGN_TOP_RIGHT, offset (2, -6); lv_image_set_scale zooms around the sprite center
        cx = W - b.width // 2 + 2 * K
        cy = b.height // 2 - 6 * K + round(badge_dy * K)
        img.alpha_composite(bs, (cx - size // 2, cy - size // 2))

    out = img.convert("RGB")
    if brightness < 1:
        out = Image.eval(out, lambda v: int(v * brightness))
    if flash > 0:
        out = Image.blend(out, Image.new("RGB", out.size, "white"), min(1.0, flash))
    return out


def black():
    return Image.new("RGB", (W, H), "black")


def save(img, sub="cache"):
    """Content-addressed save; returns the path relative to video/ for the render page."""
    data = img.tobytes()
    h = hashlib.sha1(data).hexdigest()[:16]
    d = OUT / sub
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{h}.png"
    if not p.exists():
        img.save(p)
    return f"screens/{sub}/{h}.png"


# --------------------------------------------------------------------------- firmware-like timing

def overshoot(t):
    """lv_anim_path_overshoot, 0..1 -> 0..~1.1..1"""
    t = max(0.0, min(1.0, t))
    return 1 + 2.70158 * (t - 1) ** 3 + 1.70158 * (t - 1) ** 2


def bob(t):
    """badge bob: -4..4 px, 0.9 s each way, ease in-out"""
    p = (t % 1.8) / 0.9
    x = p if p <= 1 else 2 - p
    e = 0.5 - 0.5 * math.cos(math.pi * x)
    return -4 + 8 * e


def fx_frame(t, angry):
    return int(t * 1000 / (70 if angry else 130))
