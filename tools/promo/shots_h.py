"""Landscape (1920x1080) cut, re-timed to 120 BPM: 96 beats = 48 s, every cut and event on a beat.

Same cameras and look as shots.py, tighter timing. Event beats are listed in LENGTHS' comments and are
what music_h.py hits.

    python shots_h.py    -> shots/h*.json (render with render.html at the default 1920x1080)
"""
import math
import sys

from shots import BODY, HEAD, MID, Face, cam_keys, idle_blinks, keys, write

BEAT = 0.5
LENGTHS = dict(            # beats; events (shot-local beats)
    h01_reveal=10,         # screen on at 3
    h02_switch=10,         # switches at 2, 4, 6, 8
    h03_angry=8,           # angry at 2
    h04_sparks=6,          # angry at 2
    h05_cool=6,            # shades at 2
    h06_weather=10,        # badge 1, answer 5
    h07_news=6,            # badge 1, answer 3.5
    h08_search=6,          # badge 1, answer 3.5
    h09_muse=10,           # badge 1, answer 5
    h10_lineup=12,
    h11_end=12,            # end card at 4
)


def dur(n):
    return LENGTHS[n] * BEAT


def b(x):
    return x * BEAT


def h01_reveal():
    on = b(3)
    f = Face("pikachu").power_on(on).blink_at(on + 1.6, on + 3.0).look([(on + 0.3, (0, 30)), (on + 1.0, (0, 0)), (on + 2.0, (20, -10)), (on + 2.8, (0, 0))])

    def fr(t):
        return {"screen": f.frame(t),
                "pitch": keys(t, [(0, 22), (on - 0.1, 22), (on + 0.9, 0)]),
                "yaw": keys(t, [(0, -14), (on + 0.9, -6), (dur("h01_reveal"), 4)]),
                "cam": cam_keys(t, [(0, dict(target=BODY, dist=330, az=-58, el=10, fov=28)),
                                    (dur("h01_reveal"), dict(target=MID, dist=240, az=-22, el=6, fov=28))])}
    write("h01_reveal", dur("h01_reveal"), fr, bg="#000000", exposure=0.95)


def h02_switch():
    sw = [("charmander", b(2)), ("bulbasaur", b(4)), ("squirtle", b(6)), ("ditto", b(8))]
    f = Face("pikachu").emo(0, "happy")
    for n, t0 in sw:
        f.char(t0, n)
    f.blink_at(0.6, 1.6, 2.6, 3.6)

    def fr(t):
        nod = sum(math.exp(-((t - t0 - 0.2) / 0.15) ** 2) for _, t0 in sw) * 7
        return {"screen": f.frame(t), "pitch": -nod, "yaw": keys(t, [(0, -4), (dur("h02_switch"), 6)]),
                "cam": cam_keys(t, [(0, dict(target=BODY, dist=305, az=-16, el=6, fov=26)),
                                    (dur("h02_switch"), dict(target=BODY, dist=280, az=10, el=4, fov=26))])}
    write("h02_switch", dur("h02_switch"), fr, bg="#F5F5F7")


def h03_angry():
    a = b(2)
    f = Face("charmander").emo(a, "angry").blink_at(0.5)

    def fr(t):
        shake = 5 * math.sin((t - a) * 2 * math.pi * 5) * math.exp(-max(0, t - a) * 3) if t > a else 0
        return {"screen": f.frame(t), "yaw": 8 + shake, "pitch": keys(t, [(0, 0), (a, 0), (a + 0.4, 5)]),
                "cam": cam_keys(t, [(0, dict(target=MID, dist=230, az=28, el=4, fov=24)),
                                    (dur("h03_angry"), dict(target=MID, dist=205, az=18, el=2, fov=24))])}
    write("h03_angry", dur("h03_angry"), fr, bg="#140A06", shift=40)


def h04_sparks():
    a = b(2)
    f = Face("pikachu").emo(a, "angry").blink_at(0.4)

    def fr(t):
        shake = 4 * math.sin((t - a) * 2 * math.pi * 6) * math.exp(-max(0, t - a) * 3.5) if t > a else 0
        return {"screen": f.frame(t), "yaw": -6 + shake, "pitch": 3,
                "cam": cam_keys(t, [(0, dict(target=MID, dist=210, az=-20, el=3, fov=24)),
                                    (dur("h04_sparks"), dict(target=MID, dist=185, az=-14, el=3, fov=24))])}
    write("h04_sparks", dur("h04_sparks"), fr, bg="#F5F5F7")


def h05_cool():
    a = b(2)
    f = Face("squirtle").emo(a, "cool").blink_at(0.4)

    def fr(t):
        return {"screen": f.frame(t),
                "pitch": keys(t, [(0, 0), (a - 0.05, 0), (a + 0.5, -9)]),
                "yaw": keys(t, [(0, 0), (a - 0.05, 0), (a + 0.6, -16)]),
                "cam": cam_keys(t, [(0, dict(target=BODY, dist=300, az=-8, el=-2, fov=24)),
                                    (dur("h05_cool"), dict(target=MID, dist=262, az=-18, el=-6, fov=24))])}
    write("h05_cool", dur("h05_cool"), fr, bg="#F5F5F7", shift=70)


def skill(name, char, icon, think, bg="#F5F5F7", az=(14, 6), happy=True, yaw=(0, 0), seed=5):
    d = dur(name)
    t0, t1 = b(think[0]), b(think[1])
    f = Face(char, seed).skill(t0, t1, icon).say(t1 + 0.1, d - 0.2)
    f.emo(t1, "happy" if happy else "neutral").blink_at(t1 + 1.0)
    f.look([(0, (0, 0)), (t0, (0, 0)), (t0 + 0.35, (35, -40)), (t1, (35, -40)), (t1 + 0.25, (0, 0))])

    def fr(t):
        tilt = keys(t, [(t0, 0), (t0 + 0.4, -6), (t1, -6), (t1 + 0.35, 0)])
        return {"screen": f.frame(t), "pitch": tilt, "yaw": keys(t, [(0, yaw[0]), (d, yaw[1])]),
                "cam": cam_keys(t, [(0, dict(target=BODY, dist=320, az=az[0], el=5, fov=24)),
                                    (d, dict(target=MID, dist=268, az=az[1], el=4, fov=24))])}
    write(name, d, fr, bg=bg)


def h06_weather():
    skill("h06_weather", "pikachu", "weather", (1, 5))


def h07_news():
    skill("h07_news", "squirtle", "news", (1, 3.5), az=(-14, -8), yaw=(-4, -2), seed=7)


def h08_search():
    skill("h08_search", "ditto", "search", (1, 3.5), az=(18, 10), yaw=(3, 5), seed=9)


def h09_muse():
    skill("h09_muse", "bulbasaur", "muse", (1, 5), bg="#0B0B12", az=(-20, -10), happy=False, seed=11)


def h10_lineup():
    cast = [("pikachu", "happy"), ("charmander", "angry"), ("bulbasaur", None), ("squirtle", "cool"), ("ditto", None)]
    faces = []
    for i, (n, e) in enumerate(cast):
        f = Face(n, seed=20 + i)
        if e:
            f.emo(0, e)
        if n == "bulbasaur":
            f.skill(-1, 99, "muse")
        if n == "ditto":
            f.skill(-1, 99, "search")
        idle_blinks(f, 7, start=0.4 + i * 0.5, seed=30 + i)
        faces.append(f)
    gap = 96

    def fr(t):
        units = [{"screen": f.frame(t), "pos": [(i - 2) * gap, 0, 0],
                  "yaw": 6 * math.sin(t * 0.9 + i * 1.3), "pitch": 2 * math.sin(t * 0.7 + i)} for i, f in enumerate(faces)]
        return {"units": units,
                "cam": cam_keys(t, [(0, dict(target=(-14, 10, -12), dist=540, az=-6, el=7, fov=30)),
                                    (dur("h10_lineup"), dict(target=(14, 10, -12), dist=510, az=6, el=5, fov=30))])}
    write("h10_lineup", dur("h10_lineup"), fr, bg="#F5F5F7", shadow=0.16)


def h11_end():
    f = Face("pikachu").emo(0, "happy").say(0.2, 1.6).blink_at(2.4, 4.2)

    def fr(t):
        wave = 10 * math.sin(t * 2 * math.pi * 0.8) * math.exp(-max(0, t - 1.6) * 1.2) if t > 1.6 else 0
        return {"screen": f.frame(t), "yaw": wave, "pitch": 0,
                "cam": cam_keys(t, [(0, dict(target=MID, dist=220, az=0, el=4, fov=26)),
                                    (b(6), dict(target=BODY, dist=410, az=0, el=6, fov=26))])}
    write("h11_end", dur("h11_end"), fr, bg="#000000", shift=60)


ALL = {f.__name__[:3]: f for f in (h01_reveal, h02_switch, h03_angry, h04_sparks, h05_cool, h06_weather,
                                    h07_news, h08_search, h09_muse, h10_lineup, h11_end)}

if __name__ == "__main__":
    for k in sys.argv[1:] or ALL:
        ALL[k]()
    print(f"total {sum(LENGTHS.values())} beats = {sum(LENGTHS.values()) * BEAT:.1f}s")
