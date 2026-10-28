"""Draws the Pokémon avatar skins: one face background plus eye and mouth sprites per character.

All five share one plush-like style (dome head, soft top-lit gradient, gloss, rounded eyes with
two highlights, blush); each keeps its signature marks. Sprites follow the avatar's states:
eyes for each emotion plus closed (blink), mouths for each emotion plus two talking sizes.

Writes PNGs to out/ (for preview), a contact sheet, and the C source the firmware embeds:
  main/stackchan/avatar/skins/pokemon/pokemon_assets.c

Usage: .venv/bin/python gen_faces.py
Unofficial, non-commercial fan art. Pokémon and its characters are trademarks and copyrights of
Nintendo, The Pokémon Company, Game Freak and Creatures; see DISCLAIMER.md in the repository root.
"""

import math
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
C_FILE = HERE.parents[1] / "main/stackchan/avatar/skins/pokemon/pokemon_assets.c"

S = 4                       # supersampling
W, H = 320, 240             # screen
EYE_W, EYE_H = 64, 76       # eye sprite
MOUTH_W, MOUTH_H = 112, 64  # mouth sprite
# Layout, in screen pixels; must match pokemon.cpp
EYE_DX, EYE_Y, MOUTH_Y = 62, 100, 152

EMOTIONS = ["neutral", "happy", "angry", "sad", "doubt", "sleepy", "cool"]  # order of avatar::Emotion
EYE_STATES = EMOTIONS + ["closed"]
MOUTH_STATES = EMOTIONS + ["talk_s", "talk_l"]

CHARS = {
    "pikachu": dict(
        body="#FFD83A", body_top="#FFE873", shade="#E9AE10", backdrop="#FFF7DA",
        eye="#2A1A12", iris=None, line="#3B2416", inner="#8C2B2E", tongue="#F07C7C",
        blush="#E8413C", blush_a=255, blush_r=27, nose="pikachu"),
    "charmander": dict(
        body="#F8954E", body_top="#FFB27A", shade="#DD6A2A", backdrop="#FFEBDD",
        eye="#1E2A33", iris="#2F9A97", line="#5A2A14", inner="#8C2B2E", tongue="#F07C7C",
        blush="#FF5A4A", blush_a=140, blush_r=22, nose="charmander", fangs="top", cutout=True),
    "bulbasaur": dict(
        body="#8ED6C2", body_top="#B2E8D9", shade="#5DAE98", backdrop="#E6F7EF",
        eye="#2A1416", iris="#D9383C", sclera="#FFFFFF", line="#1F4F44", inner="#8C2B2E",
        tongue="#F07C7C", blush="#FF6F8E", blush_a=150, blush_r=22, nose="bulbasaur", fangs="corners",
        wide=True),
    "squirtle": dict(
        body="#8FD1F3", body_top="#B9E4FA", shade="#5AAED9", backdrop="#E3F3FC",
        eye="#2A1420", iris="#7E2F55", line="#1E4A66", inner="#8C2B2E", tongue="#F07C7C",
        blush="#FF6F8E", blush_a=150, blush_r=22, nose="snout", shades=True),
    "ditto": dict(
        body="#C8A5E8", body_top="#DCC4F3", shade="#A27FCB", backdrop="#3A2A4A",
        eye="#231A2B", iris=None, line="#231A2B", inner="#6E2E4A", tongue="#E68AA8",
        blush="#FF8CC0", blush_a=120, blush_r=20, nose=None, dots=True),
}


# --------------------------------------------------------------------------- helpers

def rgba(hex_color, a=255):
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)


def canvas(w, h, fill=(0, 0, 0, 0)):
    img = Image.new("RGBA", (w * S, h * S), fill)
    return img, ImageDraw.Draw(img)


def box(cx, cy, w, h):
    return [(cx - w / 2) * S, (cy - h / 2) * S, (cx + w / 2) * S, (cy + h / 2) * S]


def ellipse(d, cx, cy, w, h, fill=None, outline=None, width=0):
    d.ellipse(box(cx, cy, w, h), fill=fill, outline=outline, width=int(width * S))


def arc(d, cx, cy, w, h, start, end, color, width):
    """Arc of the ellipse (cx, cy, w, h), angles in degrees (0 = right, 90 = down), round caps."""
    d.arc(box(cx, cy, w, h), start, end, fill=color, width=int(width * S))
    for a in (start, end):
        x = cx + w / 2 * math.cos(math.radians(a)) - (width / 2) * math.cos(math.radians(a))
        y = cy + h / 2 * math.sin(math.radians(a)) - (width / 2) * math.sin(math.radians(a))
        ellipse(d, x, y, width, width, fill=color)


def line(d, pts, color, width):
    d.line([(x * S, y * S) for x, y in pts], fill=color, width=int(width * S), joint="curve")
    for x, y in (pts[0], pts[-1]):
        ellipse(d, x, y, width, width, fill=color)


def finish(img):
    return img.resize((img.width // S, img.height // S), Image.LANCZOS)


def mask_above(img, p0, p1):
    """Clears everything above the line p0-p1 (sprite pixels, 1x coordinates)."""
    m = Image.new("L", img.size, 255)
    md = ImageDraw.Draw(m)
    (x0, y0), (x1, y1) = p0, p1
    # extend the line past the sprite edges
    k = (y1 - y0) / (x1 - x0)
    xa, xb = -50, EYE_W + 50
    md.polygon([(xa * S, (y0 + k * (xa - x0)) * S), (xb * S, (y0 + k * (xb - x0)) * S),
                (xb * S, -999), (xa * S, -999)], fill=0)
    alpha = img.getchannel("A")
    img.putalpha(Image.composite(alpha, Image.new("L", img.size, 0), m))


# --------------------------------------------------------------------------- eyes

def big_eye(c, d, scale=1.0):
    cx, cy = EYE_W / 2, EYE_H / 2 + 2
    w, h = 38 * scale, 50 * scale
    if c.get("sclera"):
        ellipse(d, cx, cy, w, h, fill=rgba(c["eye"]))
        ellipse(d, cx, cy, w - 6, h - 6, fill=rgba(c["sclera"]))
        ellipse(d, cx + 1, cy + 4, w * 0.62, h * 0.66, fill=rgba(c["iris"]))
        ellipse(d, cx + 1, cy + 5, w * 0.32, h * 0.36, fill=rgba(c["eye"]))
    else:
        ellipse(d, cx, cy, w, h, fill=rgba(c["eye"]))
        if c.get("iris"):
            ellipse(d, cx, cy + 6 * scale, w * 0.72, h * 0.58, fill=rgba(c["iris"]))
            ellipse(d, cx, cy + 7 * scale, w * 0.38, h * 0.34, fill=rgba(c["eye"]))
    ellipse(d, cx - 6 * scale, cy - 11 * scale, 15 * scale, 15 * scale, fill=rgba("#FFFFFF"))
    ellipse(d, cx + 8 * scale, cy + 11 * scale, 6 * scale, 6 * scale, fill=rgba("#FFFFFF", 230))


def dot_eye(c, d, scale=1.0):
    cx, cy = EYE_W / 2, EYE_H / 2
    ellipse(d, cx, cy, 11 * scale, 13 * scale, fill=rgba(c["eye"]))


def draw_eye(c, state, left):
    """left: the eye on the screen's left. Inner side is toward the screen center."""
    img, d = canvas(EYE_W, EYE_H)
    col = rgba(c["eye"])
    dots = c.get("dots")
    inner = EYE_W if left else 0      # x of the inner edge
    outer = 0 if left else EYE_W
    cx, cy = EYE_W / 2, EYE_H / 2

    if state == "closed":
        if dots:
            line(d, [(cx - 8, cy), (cx + 8, cy)], col, 3.5)
        else:
            arc(d, cx, cy - 6, 40, 26, 15, 165, col, 6)
    elif state == "happy":
        if dots:
            arc(d, cx, cy + 3, 18, 14, 200, 340, col, 3.5)
        else:
            arc(d, cx, cy + 10, 42, 40, 200, 340, col, 7)
    elif state in ("angry", "sad"):
        (dot_eye if dots else big_eye)(c, d)

        top = cy - (8 if dots else 27)
        drop = 9 if dots else 16
        # angry: inner side lower; sad: outer side lower
        lo, hi = (inner, outer) if state == "angry" else (outer, inner)
        p_lo, p_hi = (lo, top + drop + 6), (hi, top - 2)
        mask_above(img, p_hi, p_lo)
        d = ImageDraw.Draw(img)
        line(d, [(hi * 0.85 + lo * 0.15, p_hi[1] + drop * 0.15 + 0.5),
                 (lo * 0.85 + hi * 0.15, p_lo[1] - drop * 0.15 - 0.5)], col, 3.5 if dots else 5)
        if state == "sad" and not dots:
            # small tear at the outer corner
            tx = outer + (10 if left else -10)
            ellipse(d, tx, cy + 26, 8, 11, fill=rgba("#7EC8F2", 235))
    elif state in ("sleepy", "doubt"):
        squint = state == "sleepy" or not left   # doubt: only the right eye squints
        if not squint:
            (dot_eye if dots else big_eye)(c, d, 0.86)
        else:
            (dot_eye if dots else big_eye)(c, d)
            y = cy + (1 if dots else (4 if state == "sleepy" else -2))
            if state == "doubt":
                mask_above(img, (0, y - 4 if left else y + 4), (EYE_W, y + 4 if left else y - 4))
                d = ImageDraw.Draw(img)
                line(d, [(cx - (9 if dots else 22), y + 3), (cx + (9 if dots else 22), y - 3)], col,
                     3.5 if dots else 5)
            else:
                mask_above(img, (0, y), (EYE_W, y))
                d = ImageDraw.Draw(img)
                line(d, [(cx - (9 if dots else 21), y), (cx + (9 if dots else 21), y)], col, 3.5 if dots else 5)
    elif state == "cool":
        if c.get("shades"):
            return finish(img)   # hidden behind the sunglasses (fx layer)
        # smug: heavy lids, sloping down toward the outer side
        (dot_eye if dots else big_eye)(c, d)
        y_in, y_out = (cy - 1, cy + 4) if dots else (cy - 6, cy + 2)
        p_in, p_out = (inner, y_in), (outer, y_out)
        mask_above(img, p_in, p_out) if inner < outer else mask_above(img, p_out, p_in)
        d = ImageDraw.Draw(img)
        span = 9 if dots else 22
        a, b = (cx - span, cx + span)
        ya = y_in + (y_out - y_in) * ((a - inner) / (outer - inner))
        yb = y_in + (y_out - y_in) * ((b - inner) / (outer - inner))
        line(d, [(a, ya), (b, yb)], col, 3.5 if dots else 5)
    else:  # neutral
        (dot_eye if dots else big_eye)(c, d)
    return finish(img)


# --------------------------------------------------------------------------- mouths

def nose(c, d):
    cx = MOUTH_W / 2
    if c["nose"] == "pikachu":
        ellipse(d, cx, 9, 7, 4.5, fill=rgba(c["line"]))
    elif c["nose"] == "charmander":
        # two small round nostrils, just above the upper lip
        ellipse(d, cx - 11, 8, 3.4, 3.4, fill=rgba(c["line"], 220))
        ellipse(d, cx + 11, 8, 3.4, 3.4, fill=rgba(c["line"], 220))
    elif c["nose"] == "bulbasaur":
        # tiny nostrils set wide and low, beside the wide mouth
        ellipse(d, cx - 24, 13, 2.6, 2.2, fill=rgba(c["line"], 220))
        ellipse(d, cx + 24, 13, 2.6, 2.2, fill=rgba(c["line"], 220))
    elif c["nose"] == "snout":
        # no nostrils: the rounded snout over the mouth
        arc(d, cx, 17, 46, 20, 200, 340, rgba(c["line"], 150), 2.4)


def open_mouth(c, d, cx, cy, w, h, flat_top=False):
    lc, ic, tc = rgba(c["line"]), rgba(c["inner"]), rgba(c["tongue"])
    if flat_top:
        # D shape: flat top, round bottom
        m = Image.new("L", (MOUTH_W * S, MOUTH_H * S), 0)
        md = ImageDraw.Draw(m)
        md.ellipse(box(cx, cy - h / 2, w, h * 2), fill=255)
        md.rectangle([0, 0, MOUTH_W * S, (cy - h / 2) * S], fill=0)
        shape = m
    else:
        m = Image.new("L", (MOUTH_W * S, MOUTH_H * S), 0)
        ImageDraw.Draw(m).ellipse(box(cx, cy, w, h), fill=255)
        shape = m
    lw = 3.2 * S
    grown = shape.filter(ImageFilter.MaxFilter(int(lw) * 2 + 1))
    layer = Image.new("RGBA", shape.size, lc)
    target = d._image
    target.alpha_composite(Image.composite(layer, Image.new("RGBA", shape.size, (0, 0, 0, 0)), grown))
    inner_layer = Image.new("RGBA", shape.size, ic)
    tl = ImageDraw.Draw(inner_layer)
    tl.ellipse(box(cx, cy + h * (0.42 if flat_top else 0.38), w * 0.7, h * (0.75 if flat_top else 0.62)), fill=tc)
    fangs = c.get("fangs")
    if fangs:
        top = cy - h / 2 if (flat_top or h < 20) else cy - h / 2 + h * 0.12
        xs = [cx - w * 0.3, cx + w * 0.3] if fangs == "top" else [cx - w * 0.38, cx + w * 0.38]
        fh = max(4.0, min(7.0, h * 0.3))
        for x in xs:
            tl.polygon([((x - 3) * S, top * S), ((x + 3) * S, top * S), (x * S, (top + fh) * S)],
                       fill=rgba("#FFFFFF"))
    target.alpha_composite(Image.composite(inner_layer, Image.new("RGBA", shape.size, (0, 0, 0, 0)), shape))


def draw_mouth(c, state):
    img, d = canvas(MOUTH_W, MOUTH_H)
    lc = rgba(c["line"])
    cx = MOUTH_W / 2
    dots = c.get("dots")
    lw = 3 if dots else 4
    nose(c, d)

    if state == "neutral":
        if c["nose"] == "pikachu":
            arc(d, cx - 8, 22, 16, 14, 10, 170, lc, lw)
            arc(d, cx + 8, 22, 16, 14, 10, 170, lc, lw)
        elif dots:
            arc(d, cx, 14, 66, 26, 25, 155, lc, lw)
        elif c.get("wide"):
            arc(d, cx, 12, 70, 26, 25, 155, lc, lw)
        else:
            arc(d, cx, 16, 40, 22, 25, 155, lc, lw)
    elif state == "happy":
        if dots:
            open_mouth(c, d, cx, 30, 64, 20, flat_top=True)
        elif c.get("wide"):
            open_mouth(c, d, cx, 32, 66, 22, flat_top=True)
        else:
            open_mouth(c, d, cx, 34, 46, 24, flat_top=True)
    elif state == "talk_s":
        open_mouth(c, d, cx, 30, 30 if not dots else 40, 18 if not dots else 12)
    elif state == "talk_l":
        open_mouth(c, d, cx, 34, 38 if not dots else 54, 34 if not dots else 24)
    elif state == "angry":
        if c["nose"] == "pikachu":
            arc(d, cx - 8, 32, 16, 14, 190, 350, lc, lw)
            arc(d, cx + 8, 32, 16, 14, 190, 350, lc, lw)
        else:
            arc(d, cx, 38, 34, 20, 205, 335, lc, lw)
    elif state == "sad":
        arc(d, cx, 40, 40 if not dots else 56, 26, 210, 330, lc, lw)
    elif state == "doubt":
        pts = [(cx - 18 + i, 28 + 3.5 * math.sin(i / 36 * 2 * math.pi) - i * 0.12) for i in range(0, 37, 2)]
        line(d, pts, lc, lw)
    elif state == "sleepy":
        ellipse(d, cx, 30, 14, 16, outline=lc, width=lw)
    elif state == "cool":
        # smirk: one corner pulled up
        pts = []
        for i in range(21):
            t = i / 20
            pts.append((cx - 20 + 40 * t, 26 + 3 * math.sin(math.pi * min(t / 0.7, 1)) - 10 * max(0, t - 0.7) / 0.3))
        line(d, pts, lc, lw)
        line(d, [(cx + 22, 13), (cx + 25, 17)], lc, lw * 0.7)
    return finish(img)


# --------------------------------------------------------------------------- backgrounds

def gradient(w, h, top, bottom):
    g = Image.new("RGBA", (w, h))
    t, b = rgba(top), rgba(bottom)
    px = g.load()
    for y in range(h):
        f = y / (h - 1)
        col = tuple(int(t[i] + (b[i] - t[i]) * f) for i in range(4))
        for x in range(w):
            px[x, y] = col
    return g


def paste_shape(base, mask, fill_img):
    base.alpha_composite(Image.composite(fill_img, Image.new("RGBA", base.size, (0, 0, 0, 0)), mask))


def head_mask(name):
    m = Image.new("L", (W * S, H * S), 0)
    md = ImageDraw.Draw(m)
    if name == "ditto":
        # blob with a wavy top edge
        md.rectangle([0, 70 * S, W * S, H * S], fill=255)
        for i, (x, y, r) in enumerate([(-10, 70, 50), (60, 46, 46), (130, 40, 44), (196, 46, 44),
                                       (262, 40, 46), (330, 66, 50)]):
            md.ellipse(box(x, y + r * 0.6, r * 2.1, r * 2), fill=255)
        md.rectangle([0, 60 * S, W * S, H * S], fill=255)
    else:
        md.ellipse(box(160, 300, 470, 556), fill=255)
    return m


def draw_background(name, c):
    S_W, S_H = W * S, H * S
    # cutout: the backdrop stays transparent so fx layers can sit behind the head
    img = Image.new("RGBA", (S_W, S_H), (0, 0, 0, 0) if c.get("cutout") else rgba(c["backdrop"]))
    d = ImageDraw.Draw(img)

    # behind the head
    if name == "pikachu":
        for side in (-1, 1):
            ear = Image.new("RGBA", (S_W, S_H), (0, 0, 0, 0))
            ed = ImageDraw.Draw(ear)
            ed.ellipse(box(160 + side * 120, 18, 62, 150), fill=rgba(c["body"]))
            ed.ellipse(box(160 + side * 120, -34, 62, 120), fill=rgba("#2A2220"))
            ed.ellipse(box(160 + side * 120, 18, 62, 150), outline=rgba(c["shade"]), width=3 * S)
            ear = ear.rotate(-side * 28, center=((160 + side * 120) * S, 60 * S), resample=Image.BICUBIC)
            img.alpha_composite(ear)
    elif name == "bulbasaur":
        ellipse(d, 160, 6, 230, 120, fill=rgba("#6CC160"))
        ellipse(d, 160, 6, 230, 120, outline=rgba("#3F8F3A"), width=3)
        for x0 in (110, 160, 210):
            arc(d, x0, 40, 60, 90, 205, 335, rgba("#3F8F3A"), 3)
        for side in (-1, 1):
            d.polygon([((160 + side * 92) * S, 34 * S), ((160 + side * 150) * S, 2 * S),
                       ((160 + side * 136) * S, 62 * S)], fill=rgba(c["body"]))
            d.line([((160 + side * 150) * S, 2 * S), ((160 + side * 136) * S, 62 * S)],
                   fill=rgba(c["shade"]), width=3 * S)
            d.line([((160 + side * 92) * S, 34 * S), ((160 + side * 150) * S, 2 * S)],
                   fill=rgba(c["shade"]), width=3 * S)

    head = head_mask(name)
    body = gradient(S_W, S_H, c["body_top"], c["body"])
    # soft rim shade inside the head edge
    edge = head.filter(ImageFilter.GaussianBlur(10 * S))
    shade = Image.new("RGBA", (S_W, S_H), rgba(c["shade"]))
    body.alpha_composite(Image.composite(Image.new("RGBA", (S_W, S_H), (0, 0, 0, 0)), shade,
                                         edge.point(lambda v: 255 if v > 200 else int(v * 1.25))).filter(
        ImageFilter.GaussianBlur(2 * S)))
    paste_shape(img, head, body)
    # outline just outside the head edge
    ring = ImageChops.subtract(head.filter(ImageFilter.MaxFilter(11)), head)
    paste_shape(img, ring, Image.new("RGBA", (S_W, S_H), rgba(c["shade"])))

    # gloss: shared across the set
    gloss = Image.new("RGBA", (S_W, S_H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(gloss)
    gy = 64 if name == "ditto" else 40
    gd.ellipse(box(92, gy, 70, 22), fill=(255, 255, 255, 120))
    gd.ellipse(box(134, gy - 6, 16, 9), fill=(255, 255, 255, 120))
    gloss = gloss.filter(ImageFilter.GaussianBlur(3 * S))
    img.alpha_composite(Image.composite(gloss, Image.new("RGBA", (S_W, S_H), (0, 0, 0, 0)), head))

    # signature marks on the face
    d = ImageDraw.Draw(img)
    if name == "bulbasaur":
        # angular forehead spots, as in the official art
        spot = rgba("#5A9F88")
        for pts in [[(138, 34), (186, 30), (176, 52), (128, 56)],      # big slanted quad
                    [(112, 62), (122, 60), (121, 74), (110, 75)],      # small quad
                    [(160, 62), (172, 82), (148, 82)],                 # triangle between the eyes
                    [(210, 60), (220, 62), (219, 74), (209, 73)]]:
            d.polygon([(x * S, y * S) for x, y in pts], fill=spot)
    elif name == "charmander":
        ellipse(d, 160, 268, 230, 120, fill=rgba("#FCE7A5"))

    elif name == "squirtle":
        for side in (-1, 1):
            # brown shell with its pale rim, behind the shoulders
            ellipse(d, 160 + side * 196, 236, 170, 150, fill=rgba("#FFF6E2"))
            ellipse(d, 160 + side * 196, 236, 156, 136, fill=rgba("#A45F36"))
            ellipse(d, 160 + side * 196, 236, 156, 136, outline=rgba("#6E3A1E"), width=3)
            for k in (1, 2):
                arc(d, 160 + side * 196, 236, 156 - 40 * k, 136 - 36 * k, 180, 360, rgba("#7E4626"), 2.5)
        # cream plastron with its plate seams
        ellipse(d, 160, 274, 200, 120, fill=rgba("#F3DE9E"))
        ellipse(d, 160, 274, 200, 120, outline=rgba("#B98A4A"), width=3)
        line(d, [(160, 216), (160, 240)], rgba("#B98A4A"), 3)
        arc(d, 160, 250, 190, 36, 200, 340, rgba("#B98A4A"), 3)
        ellipse(d, 266, 52, 12, 16, fill=rgba("#FFFFFF", 150))

    # cheeks / blush
    bl = Image.new("RGBA", (S_W, S_H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bl)
    r = c["blush_r"]
    for side in (-1, 1):
        bx = 160 + side * (118 if name == "pikachu" else 100)
        by = 160 if name == "pikachu" else 150
        bd.ellipse(box(bx, by, r * 2, r * (2 if name == "pikachu" else 1.4)), fill=rgba(c["blush"], c["blush_a"]))
    if name != "pikachu":
        bl = bl.filter(ImageFilter.GaussianBlur(3 * S))
    img.alpha_composite(bl)
    img = finish(img)
    return img if c.get("cutout") else img.convert("RGB")


# --------------------------------------------------------------------------- fx layers
# Animated sprites over the face. Frames are keyed by emotion, or "any" for every other emotion;
# the firmware cycles them, faster when angry.

FLAME_W, FLAME_H = 110, 150


def draw_flame(phase, angry):
    img = Image.new("RGBA", (FLAME_W * S, FLAME_H * S), (0, 0, 0, 0))
    cx, base = FLAME_W / 2, FLAME_H - 8
    w, h = (64, 136) if angry else (54, 112)
    cols = ["#E5281A", "#FF8A1A", "#FFE680"] if angry else ["#FF7A1A", "#FFB21A", "#FFF1A0"]
    for layer, (k, col) in enumerate(zip((1.0, 0.66, 0.36), cols)):
        m = Image.new("L", img.size, 0)
        md = ImageDraw.Draw(m)
        lw, lh = w * k, h * (k * 0.9 + 0.1)
        bulb_y = base - lw * 0.42
        md.ellipse(box(cx, bulb_y, lw, lw * 0.86), fill=255)
        tongues = [(-0.3, 0.72), (0.0, 1.0), (0.32, 0.66)] if layer < 2 else [(0.0, 1.0)]
        for i, (dx, hk) in enumerate(tongues):
            flick = 1 + (0.16 if angry else 0.09) * math.sin(phase * math.pi / 2 + i * 2.1)
            sway = (4 if angry else 2.5) * math.sin(phase * math.pi / 2 + i)
            tx, ty = cx + dx * lw + sway, base - lh * hk * flick
            md.polygon([((cx + dx * lw - lw * 0.3) * S, bulb_y * S), ((cx + dx * lw + lw * 0.3) * S, bulb_y * S),
                        (tx * S, ty * S)], fill=255)
        m = m.filter(ImageFilter.GaussianBlur(1.6 * S))
        paste_shape(img, m, Image.new("RGBA", img.size, rgba(col)))
    if angry:
        d = ImageDraw.Draw(img)
        for i in range(5):
            a = phase * 0.9 + i * 1.7
            ex = cx + 34 * math.sin(a * 1.3)
            ey = 26 + ((phase * 9 + i * 23) % 60)
            ellipse(d, ex, ey, 5, 5, fill=rgba("#FFB21A", 230))
            ellipse(d, ex, ey, 2.5, 2.5, fill=rgba("#FFF1A0"))
    return finish(img)


def draw_sparks(phase, left):
    size = 140
    img, d = canvas(size, size)
    c = size / 2
    base = 180 if left else 0
    bolt = [(0, 0), (10, -6), (10, -1.5), (22, -7), (12, 2.5), (12, -1), (2, 5)]  # along +x
    for i in range(3):
        a = math.radians(base - 55 + i * 55 + (phase - 1) * 12)
        r0 = 29 + 3 * ((phase + i) % 2)
        pts = []
        for x, y in bolt:
            x, y = x * 1.8 + r0, y * 1.8
            pts.append(((c + x * math.cos(a) - y * math.sin(a)) * S, (c + x * math.sin(a) + y * math.cos(a)) * S))
        d.polygon(pts, fill=rgba("#FFF27A"), outline=rgba("#C98A00"), width=int(2 * S))
    return finish(img)


SHADES_W, SHADES_H = 220, 64


def draw_shades():
    img, d = canvas(SHADES_W, SHADES_H)
    for lx in (SHADES_W / 2 - EYE_DX, SHADES_W / 2 + EYE_DX):
        m = Image.new("L", img.size, 0)
        md = ImageDraw.Draw(m)
        md.ellipse(box(lx, 22, 88, 64), fill=255)
        md.rectangle([0, 0, img.width, 22 * S], fill=0)
        md.rounded_rectangle(box(lx, 18, 88, 16), radius=4 * S, fill=255)
        paste_shape(img, m, Image.new("RGBA", img.size, rgba("#15181D")))
        sheen = Image.new("L", img.size, 0)
        ImageDraw.Draw(sheen).polygon([((lx - 30) * S, 46 * S), ((lx - 14) * S, 46 * S), ((lx + 6) * S, 12 * S),
                                       ((lx - 10) * S, 12 * S)], fill=90)
        paste_shape(img, ImageChops.multiply(sheen, m), Image.new("RGBA", img.size, (255, 255, 255, 255)))
    d = ImageDraw.Draw(img)
    line(d, [(SHADES_W / 2 - 18, 16), (SHADES_W / 2 + 18, 16)], rgba("#15181D"), 6)
    line(d, [(4, 13), (SHADES_W / 2 - EYE_DX - 40, 15)], rgba("#15181D"), 5)
    line(d, [(SHADES_W - 4, 13), (SHADES_W / 2 + EYE_DX + 40, 15)], rgba("#15181D"), 5)
    return finish(img)


def fx_layers(name):
    """[(x, y offset of the sprite center from the screen center, {mood: [frames]}, behind the head)]"""
    if name == "charmander":
        # tail flame rising from behind the head, top right
        return [(124, -84, {"any": [draw_flame(p, False) for p in range(4)],
                            "angry": [draw_flame(p, True) for p in range(4)]}, True)]
    if name == "pikachu":
        return [(-118, 40, {"angry": [draw_sparks(p, True) for p in range(3)]}, False),
                (118, 40, {"angry": [draw_sparks(p, False) for p in range(3)]}, False)]
    if name == "squirtle":
        return [(0, EYE_Y - H // 2, {"cool": [draw_shades()]}, False)]
    return []


# --------------------------------------------------------------------------- skill badges
# Shown over any face while a tool runs: a round badge with the skill's icon and a thought-bubble
# trail toward the face (the badge sits top right, over the eye that squints when thinking; the
# trail points down left).

BADGE = 96          # sprite size
BADGE_C = (56, 40)  # badge center in the sprite; must match show_badge() in stackchan_display.cc
BADGE_R = 32


def badge(ring, draw_icon):
    img, d = canvas(BADGE, BADGE)
    cx, cy = BADGE_C
    # soft shadow, then the badge
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse(box(cx + 2, cy + 3, BADGE_R * 2, BADGE_R * 2), fill=(0, 0, 0, 70))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(2 * S)))
    for x, y, r in ((22, 70, 7), (10, 84, 4.5)):
        ellipse(d, x + 1, y + 2, r * 2, r * 2, fill=(0, 0, 0, 50))
        ellipse(d, x, y, r * 2, r * 2, fill=rgba("#FFFFFF"), outline=rgba(ring), width=2)
    ellipse(d, cx, cy, BADGE_R * 2, BADGE_R * 2, fill=rgba("#FFFFFF"), outline=rgba(ring), width=4)
    draw_icon(d, cx, cy)
    return finish(img)


def icon_weather(d, cx, cy):
    for i in range(8):
        a = math.radians(i * 45)
        line(d, [(cx - 7 + 13 * math.cos(a), cy - 7 + 13 * math.sin(a)),
                 (cx - 7 + 18 * math.cos(a), cy - 7 + 18 * math.sin(a))], rgba("#FFB300"), 3)
    ellipse(d, cx - 7, cy - 7, 20, 20, fill=rgba("#FFC93C"))
    cloud = rgba("#9EC9F0")
    for x, y, r in ((cx - 6, cy + 9, 9), (cx + 5, cy + 4, 11), (cx + 15, cy + 10, 8)):
        ellipse(d, x, y, r * 2, r * 2, fill=cloud)
    d.rectangle([(cx - 6) * S, (cy + 9) * S, (cx + 15) * S, (cy + 18) * S], fill=cloud)


def icon_news(d, cx, cy):
    d.rounded_rectangle(box(cx, cy, 38, 32), radius=4 * S, fill=rgba("#F4F1E8"), outline=rgba("#546E7A"), width=2 * S)
    d.rectangle(box(cx, cy - 10, 30, 5), fill=rgba("#37474F"))
    d.rectangle(box(cx - 8, cy + 3, 12, 11), fill=rgba("#90A4AE"))
    for y in (cy - 1, cy + 4, cy + 9):
        line(d, [(cx + 2, y), (cx + 13, y)], rgba("#78909C"), 2)


def icon_search(d, cx, cy):
    ellipse(d, cx - 4, cy - 4, 26, 26, fill=rgba("#D6ECFF"), outline=rgba("#1E88E5"), width=4)
    ellipse(d, cx - 9, cy - 9, 7, 7, fill=rgba("#FFFFFF"))
    line(d, [(cx + 6, cy + 6), (cx + 15, cy + 15)], rgba("#1E88E5"), 6)


def icon_muse(d, cx, cy):
    # a small friendly robot head
    line(d, [(cx, cy - 13), (cx, cy - 19)], rgba("#7C4DFF"), 2.5)
    ellipse(d, cx, cy - 20, 7, 7, fill=rgba("#FF6FB5"))
    d.rounded_rectangle(box(cx, cy + 2, 36, 28), radius=9 * S, fill=rgba("#7C4DFF"))
    d.rounded_rectangle(box(cx, cy + 2, 28, 18), radius=6 * S, fill=rgba("#1B1340"))
    ellipse(d, cx - 6, cy, 6, 7, fill=rgba("#7DF9FF"))
    ellipse(d, cx + 6, cy, 6, 7, fill=rgba("#7DF9FF"))
    arc(d, cx, cy + 4, 10, 6, 20, 160, rgba("#7DF9FF"), 1.8)
    for side in (-1, 1):
        d.rounded_rectangle(box(cx + side * 20, cy + 2, 5, 10), radius=2 * S, fill=rgba("#B39DFF"))


def icon_reminder(d, cx, cy):
    bell = rgba("#FFB300")
    ellipse(d, cx, cy - 4, 24, 26, fill=bell)
    d.polygon([((cx - 12) * S, (cy - 2) * S), ((cx + 12) * S, (cy - 2) * S), ((cx + 16) * S, (cy + 10) * S),
               ((cx - 16) * S, (cy + 10) * S)], fill=bell)
    ellipse(d, cx, cy + 13, 8, 7, fill=rgba("#E65100"))
    ellipse(d, cx, cy - 17, 6, 6, fill=bell)
    ellipse(d, cx - 5, cy - 7, 5, 9, fill=rgba("#FFF3C4"))


def icon_camera(d, cx, cy):
    d.rounded_rectangle(box(cx, cy + 3, 40, 28), radius=6 * S, fill=rgba("#455A64"))
    d.rounded_rectangle(box(cx - 6, cy - 12, 14, 7), radius=2 * S, fill=rgba("#455A64"))
    ellipse(d, cx, cy + 4, 20, 20, fill=rgba("#CFD8DC"))
    ellipse(d, cx, cy + 4, 13, 13, fill=rgba("#263238"))
    ellipse(d, cx - 3, cy + 1, 4, 4, fill=rgba("#FFFFFF"))
    ellipse(d, cx + 13, cy - 4, 4, 4, fill=rgba("#FFCA28"))


def icon_sparkle(d, cx, cy):
    def star(x, y, r, col):
        k = r * 0.28
        d.polygon([(x * S, (y - r) * S), ((x + k) * S, (y - k) * S), ((x + r) * S, y * S), ((x + k) * S, (y + k) * S),
                   (x * S, (y + r) * S), ((x - k) * S, (y + k) * S), ((x - r) * S, y * S), ((x - k) * S, (y - k) * S)],
                  fill=rgba(col))
    star(cx - 3, cy + 2, 17, "#FFC93C")
    star(cx + 12, cy - 11, 8, "#FF80AB")
    star(cx + 11, cy + 13, 5, "#80D8FF")


ICONS = {
    "weather": ("#FFB300", icon_weather),
    "news": ("#607D8B", icon_news),
    "search": ("#1E88E5", icon_search),
    "muse": ("#7C4DFF", icon_muse),
    "reminder": ("#FF7043", icon_reminder),
    "camera": ("#455A64", icon_camera),
    "sparkle": ("#EC407A", icon_sparkle),
}


# --------------------------------------------------------------------------- output

def compose(bg, eyes_l, eyes_r, mouth, fx=(), mood="neutral", frame=0, backdrop="#000000"):
    """Stacks the layers the way the firmware does: backdrop, behind fx, background, eyes, mouth, front fx."""
    img = Image.new("RGBA", bg.size, rgba(backdrop))

    def add_fx(behind):
        for x, y, moods, is_behind in fx:
            frames = moods.get(mood) or moods.get("any") or []
            if frames and is_behind == behind:
                f = frames[frame % len(frames)]
                layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
                layer.paste(f, (160 + x - f.width // 2, 120 + y - f.height // 2))
                img.alpha_composite(layer)

    add_fx(True)
    img.alpha_composite(bg.convert("RGBA"))
    img.alpha_composite(eyes_l, (160 - EYE_DX - EYE_W // 2, EYE_Y - EYE_H // 2))
    img.alpha_composite(eyes_r, (160 + EYE_DX - EYE_W // 2, EYE_Y - EYE_H // 2))
    img.alpha_composite(mouth, (160 - MOUTH_W // 2, MOUTH_Y - MOUTH_H // 2))
    add_fx(False)
    return img.convert("RGB")


def c_array(name, data):
    rows = [", ".join(f"0x{b:02x}" for b in data[i:i + 20]) for i in range(0, len(data), 20)]
    return f"static const uint8_t {name}[] = {{\n    " + ",\n    ".join(rows) + "\n};\n"


def main():
    OUT.mkdir(exist_ok=True)
    sheet_cols = len(MOUTH_STATES)
    sheet = Image.new("RGB", (W * sheet_cols // 2, H * len(CHARS) // 2), "white")
    c_parts, table, fx_table = [], [], []
    for row, (name, c) in enumerate(CHARS.items()):
        bg = draw_background(name, c)
        files = {"bg": bg}
        for st in EYE_STATES:
            files[f"eye_{st}_l"] = draw_eye(c, st, True)
            files[f"eye_{st}_r"] = draw_eye(c, st, False)
        for st in MOUTH_STATES:
            files[f"mouth_{st}"] = draw_mouth(c, st)
        fx = fx_layers(name)
        for i, (x, y, moods, behind) in enumerate(fx):
            fx_table.append((name, i, x, y, int(behind)))
            for mood, frames in moods.items():
                for n, f in enumerate(frames):
                    files[f"fx{i}_{mood}_{n}"] = f
        for key, im in files.items():
            path = OUT / f"{name}_{key}.png"
            im.save(path, optimize=True)
            sym = f"{name}_{key}_png"
            c_parts.append(c_array(sym, path.read_bytes()))
            table.append((name, key, sym))
        for col, st in enumerate(MOUTH_STATES):
            eye = st if st in EMOTIONS else "neutral"
            frame = compose(bg, files[f"eye_{eye}_l"], files[f"eye_{eye}_r"], files[f"mouth_{st}"], fx, eye, 0, c["backdrop"])
            sheet.paste(frame.resize((W // 2, H // 2), Image.LANCZOS), (col * W // 2, row * H // 2))
    sheet.save(OUT / "contact_sheet.png")

    icons = Image.new("RGBA", (BADGE * len(ICONS), BADGE), (255, 247, 218, 255))
    for i, (key, (ring, fn)) in enumerate(ICONS.items()):
        im = badge(ring, fn)
        path = OUT / f"icon_{key}.png"
        im.save(path, optimize=True)
        sym = f"icon_{key}_png"
        c_parts.append(c_array(sym, path.read_bytes()))
        table.append(("icon", key, sym))
        icons.alpha_composite(im, (i * BADGE, 0))
    icons.save(OUT / "icons.png")

    C_FILE.parent.mkdir(parents=True, exist_ok=True)
    total = sum((OUT / f"{n}_{k}.png").stat().st_size for n, k, _ in table)  # icons: n == "icon"
    entries = "\n".join(f'    {{"{n}", "{k}", {s}, sizeof({s})}},' for n, k, s in table)
    fx_entries = "\n".join(f'    {{"{n}", {i}, {x}, {y}, {b}}},' for n, i, x, y, b in fx_table)
    skin_entries = "\n".join(f'    {{"{n}", 0x{c["backdrop"].lstrip("#")}, {int(bool(c.get("cutout")))}}},'
                              for n, c in CHARS.items())
    C_FILE.write_text(
        "// Generated by tools/pokemon_faces/gen_faces.py; do not edit.\n"
        "// Unofficial, non-commercial Pokémon fan art; see DISCLAIMER.md in the repository root.\n"
        '#include "pokemon_assets.h"\n\n' + "\n".join(c_parts) +
        "\nconst PokemonAsset kPokemonAssets[] = {\n" + entries + "\n};\n"
        "const int kPokemonAssetCount = sizeof(kPokemonAssets) / sizeof(kPokemonAssets[0]);\n\n"
        "const PokemonFxLayer kPokemonFx[] = {\n" + fx_entries + "\n};\n"
        "const int kPokemonFxCount = sizeof(kPokemonFx) / sizeof(kPokemonFx[0]);\n\n"
        "const PokemonSkin kPokemonSkins[] = {\n" + skin_entries + "\n};\n"
        "const int kPokemonSkinCount = sizeof(kPokemonSkins) / sizeof(kPokemonSkins[0]);\n")
    print(f"{len(table)} PNGs, {total / 1024:.0f} KB -> {C_FILE}")


if __name__ == "__main__":
    main()
