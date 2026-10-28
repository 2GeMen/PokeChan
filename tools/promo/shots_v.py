"""Vertical (1080x1920) cut for short-video platforms: ~30 s at 120 BPM, every change lands on a beat.

    python shots_v.py            # all shots -> shots/v*.json (render with render.html?w=1080&h=1920)
"""
import math
import sys

from shots import BODY, HEAD, MID, Face, cam_keys, idle_blinks, keys, write

BPM = 120
BEAT = 60 / BPM          # 0.5 s

# shot lengths in beats; starts are cumulative (see compose_v.py for the same table)
LENGTHS = dict(v01_hook=6, v02_switch=10, v03_angry=5, v04_sparks=4, v05_cool=5,
               v06_weather=6, v07_search=4, v08_muse=6, v09_lineup=7, v10_end=7)


def dur(name):
    return LENGTHS[name] * BEAT


def v01_hook():
    """first 3 s: the face flips on every beat — the hook"""
    order = ["pikachu", "charmander", "bulbasaur", "squirtle", "ditto", "pikachu"]
    f = Face("pikachu").emo(0, "happy")
    for i, n in enumerate(order[1:], 1):
        f.char(i * BEAT, n)
    f.switch_dip = 0.08

    def fr(t):
        kick = sum(math.exp(-((t - i * BEAT - 0.08) / 0.09) ** 2) for i in range(1, 6)) * 4
        return {"screen": f.frame(t), "pitch": -kick, "yaw": keys(t, [(0, -8), (3, 6)]),
                "cam": cam_keys(t, [(0, dict(target=MID, dist=300, az=-14, el=6, fov=30)),
                                    (3, dict(target=MID, dist=272, az=8, el=4, fov=30))])}
    write("v01_hook", dur("v01_hook"), fr, bg="#FFD83A", shadow=0.2, shift=110)


def v02_switch():
    switches = [("charmander", 1.0), ("squirtle", 2.5), ("bulbasaur", 4.0)]
    f = Face("pikachu").emo(0, "happy")
    for n, t0 in switches:
        f.char(t0, n)
    f.blink_at(0.6, 2.0, 3.4)

    def fr(t):
        nod = sum(math.exp(-((t - t0 - 0.2) / 0.16) ** 2) for _, t0 in switches) * 7
        return {"screen": f.frame(t), "pitch": -nod, "yaw": keys(t, [(0, -6), (5, 6)]),
                "cam": cam_keys(t, [(0, dict(target=BODY, dist=330, az=-18, el=6, fov=30)),
                                    (5, dict(target=BODY, dist=300, az=12, el=4, fov=30))])}
    write("v02_switch", dur("v02_switch"), fr, bg="#F5F5F7")


def v03_angry():
    f = Face("charmander").emo(0.5, "angry")

    def fr(t):
        shake = 5 * math.sin((t - 0.5) * 2 * math.pi * 5) * math.exp(-max(0, t - 0.5) * 3) if t > 0.5 else 0
        return {"screen": f.frame(t), "yaw": 10 + shake, "pitch": keys(t, [(0.5, 0), (0.9, 5)]),
                "cam": cam_keys(t, [(0, dict(target=MID, dist=275, az=30, el=4, fov=30)),
                                    (2.5, dict(target=MID, dist=235, az=20, el=2, fov=30))])}
    write("v03_angry", dur("v03_angry"), fr, bg="#140A06", shift=60)


def v04_sparks():
    f = Face("pikachu").emo(0.5, "angry")

    def fr(t):
        shake = 4 * math.sin((t - 0.5) * 2 * math.pi * 6) * math.exp(-max(0, t - 0.5) * 3.5) if t > 0.5 else 0
        return {"screen": f.frame(t), "yaw": -8 + shake, "pitch": 3,
                "cam": cam_keys(t, [(0, dict(target=MID, dist=265, az=-22, el=3, fov=30)),
                                    (2.0, dict(target=MID, dist=240, az=-16, el=3, fov=30))])}
    write("v04_sparks", dur("v04_sparks"), fr, bg="#F5F5F7", shift=60)


def v05_cool():
    f = Face("squirtle").emo(0.5, "cool")

    def fr(t):
        return {"screen": f.frame(t),
                "pitch": keys(t, [(0, 0), (0.45, 0), (0.9, -9)]),
                "yaw": keys(t, [(0, 0), (0.45, 0), (1.0, -16)]),
                "cam": cam_keys(t, [(0, dict(target=MID, dist=275, az=-6, el=-3, fov=30)),
                                    (2.5, dict(target=MID, dist=245, az=-18, el=-6, fov=30))])}
    write("v05_cool", dur("v05_cool"), fr, bg="#E3F3FC", shift=60)


def skill(name, char, icon, think, bg="#F5F5F7", az=(14, 6), happy=True, seed=5):
    d = dur(name)
    f = Face(char, seed).skill(think[0], think[1], icon).say(think[1] + 0.1, d - 0.15)
    f.emo(think[1], "happy" if happy else "neutral")
    f.look([(0, (0, 0)), (think[0], (0, 0)), (think[0] + 0.3, (35, -40)), (think[1], (35, -40)), (think[1] + 0.25, (0, 0))])

    def fr(t):
        tilt = keys(t, [(think[0], 0), (think[0] + 0.4, -6), (think[1], -6), (think[1] + 0.3, 0)])
        return {"screen": f.frame(t), "pitch": tilt, "yaw": keys(t, [(0, -2), (d, 3)]),
                "cam": cam_keys(t, [(0, dict(target=BODY, dist=330, az=az[0], el=5, fov=30)),
                                    (d, dict(target=MID, dist=285, az=az[1], el=4, fov=30))])}
    write(name, d, fr, bg=bg, shift=40)


def v06_weather():
    skill("v06_weather", "pikachu", "weather", (0.5, 1.5))


def v07_search():
    skill("v07_search", "ditto", "search", (0.0, 1.0), az=(-14, -6), seed=9)


def v08_muse():
    skill("v08_muse", "bulbasaur", "muse", (0.5, 1.5), bg="#0B0B12", az=(-18, -8), happy=False, seed=11)


def v09_lineup():
    """portrait: the five robots in a row seen from the side, receding"""
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
        idle_blinks(f, 4, start=0.3 + i * 0.5, seed=30 + i)
        faces.append(f)
    gap = 118

    def fr(t):
        # zig-zag column going back from the camera, so the five stack up the tall frame
        units = [{"screen": f.frame(t), "pos": [0 if i == 0 else (-44 if i % 2 else 44), i * gap, 0],
                  "yaw": 6 * math.sin(t * 1.2 + i * 1.3), "pitch": 2 * math.sin(t + i) - 4} for i, f in enumerate(faces)]
        return {"units": units,
                "cam": cam_keys(t, [(0, dict(target=(0, 1.7 * gap, 6), dist=900, az=-5, el=26, fov=30)),
                                    (3.5, dict(target=(0, 1.7 * gap, 6), dist=860, az=5, el=25, fov=30))])}
    write("v09_lineup", dur("v09_lineup"), fr, bg="#F5F5F7", shadow=0.16, shift=-135)


def v10_end():
    f = Face("pikachu").emo(0, "happy").say(0.1, 1.2).blink_at(2.4)

    def fr(t):
        wave = 10 * math.sin(t * 2 * math.pi * 0.9) * math.exp(-max(0, t - 1.0) * 1.0) if t > 1.0 else 0
        return {"screen": f.frame(t), "yaw": wave, "pitch": 0,
                "cam": cam_keys(t, [(0, dict(target=MID, dist=280, az=0, el=4, fov=30)),
                                    (3.5, dict(target=BODY, dist=360, az=0, el=6, fov=30))])}
    write("v10_end", dur("v10_end"), fr, bg="#000000", shift=70)


ALL = {f.__name__[:3]: f for f in (v01_hook, v02_switch, v03_angry, v04_sparks, v05_cool, v06_weather,
                                    v07_search, v08_muse, v09_lineup, v10_end)}

if __name__ == "__main__":
    for k in sys.argv[1:] or ALL:
        ALL[k]()
    print(f"total {sum(LENGTHS.values()) * BEAT:.1f}s")
