"""Short-video covers: 3D group shot of the five robots + bold title and feature stickers.

    python cover.py scene     # writes shots/cover_*.json (render each with render.html?w=..&h=.. -> frames/cover_*/00000.png)
    python cover.py text      # composes out/cover_9x16.png, out/cover_3x4.png, out/cover_1x1.png
"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

import compose as C
import screens as S
from shots import orbit

ROOT = Path(__file__).resolve().parent
DARK, ACCENT = C.DARK_TEXT, C.ACCENT
BG = "#FFD83A"

SIZES = {"9x16": (1080, 1920), "3x4": (1080, 1440), "1x1": (1080, 1080), "16x9": (1920, 1080)}


def screens():
    return {
        "pikachu": S.save(S.face("pikachu", "happy"), "cover"),
        "charmander": S.save(S.face("charmander", "angry", fx_frame=2), "cover"),
        "squirtle": S.save(S.face("squirtle", "cool"), "cover"),
        "bulbasaur": S.save(S.face("bulbasaur", "doubt", badge="muse", look=(35, -40)), "cover"),
        "ditto": S.save(S.face("ditto", "doubt", badge="search", look=(35, -40)), "cover"),
    }


def scene():
    scr = screens()
    # hero in front, two flanking a step back, two more behind
    units = [
        {"screen": scr["ditto"], "pos": [118, 210, 0], "yaw": -14, "pitch": -2},
        {"screen": scr["bulbasaur"], "pos": [-118, 210, 0], "yaw": 14, "pitch": -2},
        {"screen": scr["squirtle"], "pos": [78, 95, 0], "yaw": -10, "pitch": -7},
        {"screen": scr["charmander"], "pos": [-78, 95, 0], "yaw": 10, "pitch": 4},
        {"screen": scr["pikachu"], "pos": [0, 0, 0], "yaw": 0, "pitch": -3},
    ]
    cams = {  # (target, dist, el, shift px, lateral spread)
        "9x16": ((0, 90, 0), 780, 25, 60, 0.62),
        "3x4": ((0, 70, 4), 600, 13, 130, 1.0),
        "1x1": ((0, 80, 4), 480, 14, 130, 0.86),
        "16x9": ((-95, 80, 6), 530, 14, 0, 0.9),
    }
    for k, (target, dist, el, shift, sx) in cams.items():
        us = [dict(u, pos=[u["pos"][0] * sx, u["pos"][1], 0]) for u in units]
        shot = {"name": f"cover_{k}", "fps": 30, "bg": BG, "shadow": 0.22, "shift": shift,
                "frames": [{"units": us, "cam": orbit(target, dist, 0, el, 30)}]}
        (ROOT / "shots").mkdir(exist_ok=True)
        (ROOT / "shots" / f"cover_{k}.json").write_text(json.dumps(shot))
        print("wrote", k)


def sticker(text, size=40, fill=(255, 255, 255), fg=DARK, rot=0.0, pad=(30, 16)):
    f = C.font(size, "Black")
    l, t, r, b = f.getbbox(text)
    w, h = r - l + pad[0] * 2, b - t + pad[1] * 2
    img = Image.new("RGBA", (w + 12, h + 12), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((6, 9, w + 6, h + 9), radius=h // 2, fill=(29, 29, 31, 255))  # hard shadow
    d.rounded_rectangle((3, 3, w + 3, h + 3), radius=h // 2, fill=fill, outline=(29, 29, 31), width=4)
    d.text((3 + pad[0] - l, 3 + pad[1] - t), text, font=f, fill=fg)
    return img.rotate(rot, resample=Image.BICUBIC, expand=True) if rot else img


def title_block(lines, sizes):
    """black heavy text, the last line on a white tilted sticker"""
    layers = []
    for i, (txt, sz) in enumerate(zip(lines, sizes)):
        if i == len(lines) - 1:
            layers.append(sticker(txt, sz, rot=-2.5, pad=(34, 18)))
        else:
            layers.append(C.text_layer(txt, sz, DARK, "Black"))
    return layers


def place(base, layer, cx, y):
    base.alpha_composite(layer, (int(cx - layer.width / 2), int(y)))


def badge_open(size=34):
    return sticker("开源", size, fill=DARK, fg=ACCENT, rot=8, pad=(26, 12))


FEATURES = [
    ("pikachu", "语音换脸", "一句话切换 5 只宝可梦，眨眼、说话动画全保留"),
    ("charmander", "招牌特效", "生气尾巴着火、脸颊放电，耍酷就戴墨镜"),
    ("ditto", "技能招式", "查天气、看新闻、联网搜索，都会亮出技能徽章"),
    ("bulbasaur", "接入 Muse", "日程、邮件、记忆，问一句就念给你听"),
    ("squirtle", "开源可玩", "MIT 开源固件，天气和搜索免费，无需 API key"),
]


def thumb(path, w=124):
    im = Image.open(ROOT / path).convert("RGBA").resize((w, w * 3 // 4), Image.LANCZOS)
    m = Image.new("L", im.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, im.width - 1, im.height - 1), radius=14, fill=255)
    framed = Image.new("RGBA", (im.width + 12, im.height + 12), (0, 0, 0, 0))
    ImageDraw.Draw(framed).rounded_rectangle((0, 0, framed.width - 1, framed.height - 1), radius=18, fill=(14, 14, 16, 255))
    framed.paste(im, (6, 6), m)
    return framed


def feature_sheet(img):
    """left column: brand, title, five features with real screen thumbnails; the 3D group is on the right"""
    scr = screens()
    x0 = 96
    img.alpha_composite(C.text_layer("PokeChan", 46, DARK, "Black", tracking=1), (x0, 64))
    img.alpha_composite(badge_open(26), (x0 + 250, 58))
    img.alpha_composite(C.text_layer("我的桌面机器人", 70, DARK, "Black"), (x0, 134))
    st = sticker("会变成宝可梦！", 78, rot=-2, pad=(28, 12))
    img.alpha_composite(st, (x0 - 14, 220))
    y = 384
    for char, title, desc in FEATURES:
        th = thumb(scr[char])
        img.alpha_composite(th, (x0, y))
        img.alpha_composite(C.text_layer(title, 36, DARK, "Black"), (x0 + th.width + 26, y + 2))
        img.alpha_composite(C.text_layer(desc, 26, (70, 58, 10), "Medium"), (x0 + th.width + 26, y + 56))
        y += th.height + 16
    for i, line in enumerate(("非官方同人项目，与任天堂、The Pokémon Company、", "M5Stack、Meta 无关联 · 画面为 3D 渲染")):
        d = C.text_layer(line, 22, (90, 75, 20), "Medium")
        img.alpha_composite(d, (img.width - d.width - 56, img.height - 92 + i * 32))


def compose_one(key):
    W, H = SIZES[key]
    img = Image.open(ROOT / "frames" / f"cover_{key}" / "00000.png").convert("RGBA")
    if key == "9x16":
        t = title_block(["我的桌面机器人", "会变成宝可梦！"], [100, 120])
        place(img, t[0], W / 2, 150)
        place(img, t[1], W / 2, 290)
        place(img, C.text_layer("一句话换脸 · 会生气会耍酷 · 还能查天气", 40, DARK, "Bold"), W / 2, 500)
        chips = [("语音换脸", (255, 255, 255), -4), ("尾巴着火", (255, 140, 90), 3), ("戴墨镜", (143, 209, 243), -3),
                 ("技能徽章", (255, 255, 255), 4), ("接入 Muse", (200, 165, 232), -2)]
        pos = [(200, 1500), (560, 1520), (880, 1495), (330, 1640), (720, 1650)]
        for (txt, fill, rot), (x, y) in zip(chips, pos):
            place(img, sticker(txt, 40, fill=fill, rot=rot), x, y)
        img.alpha_composite(badge_open(38), (W - 210, 60))
        disc = C.text_layer("非官方同人项目 · 与任天堂 / The Pokémon Company 无关联 · 3D 渲染", 24, (90, 75, 20), "Medium")
        place(img, disc, W / 2, H - 70)
    elif key == "3x4":
        t = title_block(["我的桌面机器人", "会变成宝可梦！"], [92, 110])
        place(img, t[0], W / 2, 90)
        place(img, t[1], W / 2, 215)
        chips = [("语音换脸", (255, 255, 255), -4), ("尾巴着火", (255, 140, 90), 3), ("戴墨镜", (143, 209, 243), -3),
                 ("技能徽章", (255, 255, 255), 4)]
        pos = [(170, 1215), (440, 1235), (690, 1210), (920, 1240)]
        for (txt, fill, rot), (x, y) in zip(chips, pos):
            place(img, sticker(txt, 34, fill=fill, rot=rot), x, y)
        img.alpha_composite(badge_open(32), (W - 180, 40))
        disc = C.text_layer("非官方同人项目 · 与任天堂 / The Pokémon Company 无关联 · 3D 渲染", 22, (90, 75, 20), "Medium")
        place(img, disc, W / 2, H - 56)
    elif key == "16x9":
        feature_sheet(img)
    else:
        t = title_block(["桌面机器人", "变宝可梦！"], [96, 112])
        place(img, t[0], W / 2, 60)
        place(img, t[1], W / 2, 175)
        img.alpha_composite(badge_open(30), (W - 170, 36))
        disc = C.text_layer("非官方同人项目 · 3D 渲染", 22, (90, 75, 20), "Medium")
        place(img, disc, W / 2, H - 50)
    (ROOT / "out").mkdir(exist_ok=True)
    out = ROOT / "out" / f"cover_{key}.png"
    img.convert("RGB").save(out, optimize=True)
    img.convert("RGB").save(out.with_suffix(".jpg"), quality=92)
    print(out.name, img.size)


if __name__ == "__main__":
    if sys.argv[1] == "scene":
        scene()
    else:
        for k in sys.argv[2:] or SIZES:
            compose_one(k)
