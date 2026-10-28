"""Shot list for the PokeChan promo: writes shots/<name>.json (per-frame screen, servo pose and camera).

    python shots.py            # all shots
    python shots.py s03 s06    # some shots

Timing follows the firmware: blinks of ~120 ms every few seconds, mouth sprites switching ~every 90 ms
while talking, fx frames every 130 ms (70 ms when angry), the badge pop/bob/fade of show_badge().
"""
import json
import math
import random
import sys
from pathlib import Path

import screens as S

FPS = 30
ROOT = Path(__file__).resolve().parent
SHOTS = ROOT / "shots"

# model landmarks (mm, world; Z up, screen faces -Y)
HEAD = (0, 10, 0)
BODY = (0, 12, -12)
MID = (0, 11, -6)


# --------------------------------------------------------------------------- helpers
def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    if isinstance(a, (list, tuple)):
        return [lerp(x, y, t) for x, y in zip(a, b)]
    return a + (b - a) * t


def keys(t, kf, ease=smooth):
    """kf: [(time, value), ...] -> eased value at t"""
    if t <= kf[0][0]:
        return kf[0][1]
    for (t0, v0), (t1, v1) in zip(kf, kf[1:]):
        if t <= t1:
            return lerp(v0, v1, ease((t - t0) / (t1 - t0)))
    return kf[-1][1]


def orbit(target, dist, az, el, fov=30):
    """camera from azimuth az (0 = straight in front, + = to the right of the robot's face) and elevation el"""
    a, e = math.radians(az), math.radians(el)
    x = target[0] + dist * math.cos(e) * math.sin(a)
    y = target[1] - dist * math.cos(e) * math.cos(a)
    z = target[2] + dist * math.sin(e)
    return {"pos": [x, y, z], "target": list(target), "fov": fov}


def cam_keys(t, kf):
    """kf: [(time, dict(target, dist, az, el, fov)), ...]"""
    names = ("target", "dist", "az", "el", "fov")
    v = {n: keys(t, [(k, d.get(n, kf[0][1].get(n, 30))) for k, d in kf]) for n in names}
    return orbit(v["target"], v["dist"], v["az"], v["el"], v["fov"])


class Face:
    """Animates one screen like the firmware: idle gaze, blinks, talking, fx, badges, character switches."""

    def __init__(self, char, seed=1):
        self.rng = random.Random(seed)
        self.segments = [(0.0, char)]         # (from time, character)
        self.emotions = [(0.0, "neutral")]    # (from time, emotion)
        self.talk = []                        # (t0, t1)
        self.badges = []                      # (t0, t1, icon)
        self.blinks = []
        self.off_until = 0.0
        self.on_ramp = 0.0
        self.look_kf = None
        self.switch_dip = 0.12

    def char(self, t, name):
        self.segments.append((t, name))
        return self

    def emo(self, t, e):
        self.emotions.append((t, e))
        return self

    def say(self, t0, t1):
        self.talk.append((t0, t1))
        return self

    def skill(self, t0, t1, icon):
        """thinking face + badge while a tool runs (the firmware shows Doubt during a skill)"""
        self.badges.append((t0, t1, icon))
        return self

    def power_on(self, t, ramp=0.35):
        self.off_until, self.on_ramp = t, ramp
        return self

    def blink_at(self, *ts):
        self.blinks += list(ts)
        return self

    def look(self, kf):
        self.look_kf = kf
        return self

    def _at(self, lst, t):
        v = lst[0][1]
        for t0, x in lst:
            if t >= t0:
                v = x
        return v

    def frame(self, t):
        if t < self.off_until:
            return S.save(S.black())
        name = self._at(self.segments, t)
        eyes = self._at(self.emotions, t)
        badge = None
        for b0, b1, icon in self.badges:
            if b0 <= t < b1 + 0.3:
                badge = (b0, b1, icon)
        if badge and t < badge[1]:
            eyes = "doubt"
        mouth = None
        if any(a <= t < b for a, b in self.talk):
            step = int(t * 1000 / 90)
            r = random.Random(step * 7919 + 13).random()
            mouth = "talk_l" if r > 0.55 else "talk_s" if r > 0.18 else None
        if any(abs(t - b) < 0.06 for b in self.blinks) and eyes not in ("cool",):
            eyes = "closed"
        look = keys(t, self.look_kf) if self.look_kf else (0, 0)
        kw = dict(eyes=eyes, mouth=mouth, look=look,
                  fx_frame=S.fx_frame(t, eyes == "angry"),
                  fx_mood=None if eyes != "closed" else self._at(self.emotions, t))
        if badge:
            b0, b1, icon = badge
            kw.update(badge=icon, badge_scale=S.overshoot((t - b0) / 0.38), badge_dy=S.bob(t - b0),
                      badge_opa=1.0 if t < b1 else max(0.0, 1 - (t - b1) / 0.3))
        if self.on_ramp and t < self.off_until + self.on_ramp:
            kw["brightness"] = (t - self.off_until) / self.on_ramp
        for t0, _ in self.segments[1:]:
            if t0 <= t < t0 + self.switch_dip:
                kw["brightness"] = 0.15 + 0.85 * (t - t0) / self.switch_dip
        return S.save(S.face(name, **kw))


def idle_blinks(face, dur, start=1.2, every=(2.6, 4.2), seed=3):
    r = random.Random(seed)
    t = start
    while t < dur:
        face.blink_at(t)
        t += r.uniform(*every)
    return face


def write(name, dur, frame_fn, **shot):
    SHOTS.mkdir(exist_ok=True)
    frames = []
    for i in range(int(round(dur * FPS))):
        t = i / FPS
        frames.append(frame_fn(t))
    (SHOTS / f"{name}.json").write_text(json.dumps({"name": name, "fps": FPS, "frames": frames, **shot}))
    print(f"{name}: {len(frames)} frames, {len({json.dumps(f.get('screen')) for f in frames})} distinct screens")


# --------------------------------------------------------------------------- shots
def s01_reveal():
    """Dark stage. Robot asleep, head down; it wakes, screen lights, looks up at you: Pikachu."""
    f = Face("pikachu").power_on(1.6).blink_at(3.6, 5.4).look([(2.0, (0, 30)), (3.0, (0, 0)), (4.5, (20, -10)), (5.5, (0, 0))])

    def fr(t):
        return {"screen": f.frame(t),
                "pitch": keys(t, [(0, 22), (1.4, 22), (2.6, 0)]),
                "yaw": keys(t, [(0, -14), (2.6, -6), (6.5, 4)]),
                "cam": cam_keys(t, [(0, dict(target=BODY, dist=330, az=-58, el=10, fov=28)),
                                    (6.5, dict(target=HEAD, dist=230, az=-24, el=6, fov=28))])}
    write("s01_reveal", 6.5, fr, bg="#000000", exposure=0.95)


def s02_switch():
    """'Switch to ...' x5: the face changes, the head gives a little nod each time."""
    order = [("pikachu", 0.0), ("charmander", 1.5), ("bulbasaur", 3.0), ("squirtle", 4.5), ("ditto", 6.0)]
    f = Face("pikachu").emo(0, "happy")
    for n, t0 in order[1:]:
        f.char(t0, n)
    f.blink_at(0.9, 2.3, 3.8, 5.3, 6.9)

    def fr(t):
        nod = sum(math.exp(-((t - t0 - 0.25) / 0.18) ** 2) for _, t0 in order[1:]) * 7
        return {"screen": f.frame(t), "pitch": -nod, "yaw": keys(t, [(0, -4), (7.5, 6)]),
                "cam": cam_keys(t, [(0, dict(target=BODY, dist=305, az=-16, el=6, fov=26)),
                                    (7.5, dict(target=BODY, dist=280, az=10, el=4, fov=26))])}
    write("s02_switch", 7.5, fr, bg="#F5F5F7")


def s03_charmander_angry():
    f = Face("charmander").emo(1.6, "angry").blink_at(0.8)

    def fr(t):
        shake = 5 * math.sin((t - 1.6) * 2 * math.pi * 5) * math.exp(-max(0, t - 1.6) * 3) if t > 1.6 else 0
        return {"screen": f.frame(t), "yaw": 8 + shake, "pitch": keys(t, [(0, 0), (1.6, 0), (2.0, 5)]),
                "cam": cam_keys(t, [(0, dict(target=MID, dist=230, az=28, el=4, fov=24)),
                                    (5.0, dict(target=MID, dist=215, az=18, el=2, fov=24))])}
    write("s03_charmander_angry", 5.0, fr, bg="#140A06", exposure=1.0, shift=40)


def s04_pikachu_sparks():
    f = Face("pikachu").emo(1.2, "angry").blink_at(0.6)

    def fr(t):
        shake = 4 * math.sin((t - 1.2) * 2 * math.pi * 6) * math.exp(-max(0, t - 1.2) * 3.5) if t > 1.2 else 0
        return {"screen": f.frame(t), "yaw": -6 + shake, "pitch": 3,
                "cam": cam_keys(t, [(0, dict(target=MID, dist=210, az=-20, el=3, fov=24)),
                                    (3.8, dict(target=MID, dist=180, az=-14, el=3, fov=24))])}
    write("s04_pikachu_sparks", 3.8, fr, bg="#F5F5F7")


def s05_squirtle_cool():
    f = Face("squirtle").emo(1.4, "cool").blink_at(0.7)

    def fr(t):
        return {"screen": f.frame(t),
                "pitch": keys(t, [(0, 0), (1.3, 0), (1.9, -9)]),
                "yaw": keys(t, [(0, 0), (1.3, 0), (2.0, -16)]),
                "cam": cam_keys(t, [(0, dict(target=BODY, dist=305, az=-8, el=-2, fov=24)),
                                    (4.5, dict(target=MID, dist=260, az=-18, el=-6, fov=24))])}
    write("s05_squirtle_cool", 4.5, fr, bg="#F5F5F7")


def skill_shot(name, char, icon, dur, think=(0.5, 3.0), bg="#F5F5F7", az=(14, 6), happy=True, yaw=(0, 0), seed=5):
    f = Face(char, seed).skill(think[0], think[1], icon).say(think[1] + 0.15, dur - 0.3)
    f.emo(think[1], "happy" if happy else "neutral").blink_at(think[1] + 1.2)
    f.look([(0, (0, 0)), (think[0], (0, 0)), (think[0] + 0.4, (35, -40)), (think[1], (35, -40)), (think[1] + 0.3, (0, 0))])

    def fr(t):
        tilt = keys(t, [(think[0], 0), (think[0] + 0.5, -6), (think[1], -6), (think[1] + 0.4, 0)])
        return {"screen": f.frame(t), "pitch": tilt, "yaw": keys(t, [(0, yaw[0]), (dur, yaw[1])]),
                "cam": cam_keys(t, [(0, dict(target=BODY, dist=320, az=az[0], el=5, fov=24)),
                                    (dur, dict(target=MID, dist=268, az=az[1], el=4, fov=24))])}
    write(name, dur, fr, bg=bg)


def s06_weather():
    skill_shot("s06_skill_weather", "pikachu", "weather", 6.0)


def s07_news():
    skill_shot("s07_skill_news", "squirtle", "news", 4.6, think=(0.4, 2.4), az=(-14, -8), yaw=(-4, -2), seed=7)


def s08_search():
    skill_shot("s08_skill_search", "ditto", "search", 4.6, think=(0.4, 2.4), az=(18, 10), yaw=(3, 5), seed=9)


def s09_muse():
    skill_shot("s09_muse", "bulbasaur", "muse", 6.5, think=(0.6, 3.2), bg="#0B0B12", az=(-20, -10), happy=False, seed=11)


def s10_lineup():
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
        idle_blinks(f, 7, start=0.5 + i * 0.6, seed=30 + i)
        faces.append(f)
    gap = 96

    def fr(t):
        units = []
        for i, f in enumerate(faces):
            units.append({"screen": f.frame(t), "pos": [(i - 2) * gap, 0, 0],
                          "yaw": 6 * math.sin(t * 0.9 + i * 1.3), "pitch": 2 * math.sin(t * 0.7 + i)})
        return {"units": units,
                "cam": cam_keys(t, [(0, dict(target=(-14, 10, -12), dist=540, az=-6, el=7, fov=30)),
                                    (7, dict(target=(14, 10, -12), dist=510, az=6, el=5, fov=30))])}
    write("s10_lineup", 7.0, fr, bg="#F5F5F7", shadow=0.16)


def s11_end():
    f = Face("pikachu").emo(0, "happy").say(0.3, 2.0).blink_at(2.6, 4.4)

    def fr(t):
        wave = 10 * math.sin(t * 2 * math.pi * 0.8) * math.exp(-max(0, t - 2.2) * 1.2) if t > 2.2 else 0
        return {"screen": f.frame(t), "yaw": wave, "pitch": 0,
                "cam": cam_keys(t, [(0, dict(target=MID, dist=220, az=0, el=4, fov=26)),
                                    (5.5, dict(target=BODY, dist=410, az=0, el=6, fov=26))])}
    write("s11_end", 5.5, fr, bg="#000000", shift=60)


ALL = {f.__name__[:3]: f for f in (s01_reveal, s02_switch, s03_charmander_angry, s04_pikachu_sparks,
                                    s05_squirtle_cool, s06_weather, s07_news, s08_search, s09_muse,
                                    s10_lineup, s11_end)}

if __name__ == "__main__":
    for k in sys.argv[1:] or ALL:
        ALL[k]()
