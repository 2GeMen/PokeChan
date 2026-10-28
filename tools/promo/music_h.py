"""Landscape version (96 beats = 48 s) of the original score v3; same themes and mix, arranged to shots_h.py.

Original score v3 for the vertical cut: the v2 8-bit "adventure anthem" with a modern electronic mix
(808 kick + sub, clap, supersaw pads, sidechain pumping, ping-pong delay, reverb, risers), at a modest level.

It borrows the *style* of classic handheld RPG music (brass-like fanfare, dotted march rhythm, two square
leads in thirds, snare rolls, a key change for lift) but no existing melody. 120 BPM, 60 beats = 30 s.

Shot events it hits (beats): cuts 6 16 21 25 30 36 40 46 53; angry 17, sparks 22, shades 26;
skill badges 31 36 41.

    python music.py   -> out/music_v.wav
"""
import wave
from pathlib import Path

import numpy as np

SR = 48000
BPM = 120
BEAT = 60 / BPM
TOTAL = 96
ROOT = Path(__file__).resolve().parent
N = int((TOTAL * BEAT + 2) * SR)

NOTE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def midi(s):
    n = NOTE[s[0]]
    i = 1
    while s[i] in "#b":
        n += 1 if s[i] == "#" else -1
        i += 1
    return 12 * (int(s[i:]) + 1) + n


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


class Bus:
    def __init__(self, pan=0.0):
        self.x = np.zeros(N)
        self.pan = pan

    def add(self, beat, sig, gain=1.0):
        i = int(beat * BEAT * SR)
        if i >= N:
            return
        self.x[i:i + len(sig)] += gain * sig[:N - i]


def env(n, a=0.004, d=0.09, s=0.7, r=0.03):
    t = np.arange(n) / SR
    e = np.where(t < a, t / a, np.where(t < a + d, 1 - (1 - s) * (t - a) / d, s))
    k = min(int(r * SR), n)
    if k:
        e[-k:] *= np.linspace(1, 0, k)
    return e


def square(f, n, duty, vib=0.0, slide_from=None):
    t = np.arange(n) / SR
    fr = np.full(n, f)
    if slide_from:
        k = min(n, int(0.04 * SR))
        fr[:k] = np.linspace(slide_from, f, k)
    if vib:
        fr = fr * (1 + vib * np.sin(2 * np.pi * 5.8 * t) * np.clip((t - 0.15) / 0.2, 0, 1))
    ph = np.cumsum(fr) / SR % 1.0
    x = np.where(ph < duty, 1.0, -1.0)
    return np.convolve(x, np.ones(4) / 4, mode="same")  # take the edge off


def triangle(f, n):
    ph = (np.arange(n) * f / SR) % 1.0
    return 4 * np.abs(ph - 0.5) - 1


lead1, lead2, bassb, drums, arpb, pad = Bus(-0.15), Bus(0.2), Bus(0), Bus(0), Bus(0.3), Bus(-0.25)
sub, kicks, fxb = Bus(0), Bus(0), Bus(0)
KICK_TIMES = []  # beats, drives the sidechain
transpose = 0  # semitones, applied at note time


def tone(bus, beat, name, length, duty=0.25, gain=0.16, vib=0.005, stac=False, slide=False):
    m = midi(name) + transpose
    n = int(length * BEAT * SR * (0.55 if stac else 0.95))
    sig = square(hz(m), n, duty, vib if length >= 1 else 0, hz(m - 2) if slide else None)
    bus.add(beat, sig * env(n, d=0.12, s=0.65 if not stac else 0.4), gain)


def mel(bus, b0, notes, **kw):
    """notes: (beat offset, name, length[, 's' staccato])"""
    for nt in notes:
        off, name, ln = nt[:3]
        tone(bus, b0 + off, name, ln, stac=len(nt) > 3 and "s" in nt[3], slide=len(nt) > 3 and "/" in nt[3], **kw)


def bass(beat, name, length, gain=0.34):
    m = midi(name) + transpose
    n = int(length * BEAT * SR * 0.9)
    bassb.add(beat, triangle(hz(m), n) * env(n, a=0.002, d=0.05, s=0.9, r=0.02), gain)
    t = np.arange(n) / SR
    sub.add(beat, np.sin(2 * np.pi * hz(m - 12) * t) * env(n, a=0.004, d=0.05, s=0.95, r=0.03), gain * 0.9)


rng = np.random.default_rng(11)


def kick(beat, g=0.95):
    """808-style: pitch-dropping sine with a long tail, plus a short click"""
    n = int(0.42 * SR)
    t = np.arange(n) / SR
    f = 46 + 140 * np.exp(-t / 0.022)
    body = np.tanh(1.8 * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.16))
    click = rng.standard_normal(n) * np.exp(-t / 0.002) * 0.3
    kicks.add(beat, body + click, g)
    KICK_TIMES.append(beat)


def snare(beat, g=0.36, clap=None):
    n = int(0.16 * SR)
    t = np.arange(n) / SR
    x = rng.standard_normal(n) * np.exp(-t / 0.045) + 0.6 * np.sin(2 * np.pi * 185 * t) * np.exp(-t / 0.035)
    drums.add(beat, x, g)
    if clap if clap is not None else g > 0.3:
        # clap: three quick bursts then a short tail, band-limited
        m = int(0.25 * SR)
        c = np.zeros(m)
        for k, d in enumerate((0, 0.011, 0.022)):
            i = int(d * SR)
            b = rng.standard_normal(int(0.012 * SR))
            c[i:i + len(b)] += b * (0.8 if k < 2 else 1.0)
        i = int(0.022 * SR)
        c[i:] += rng.standard_normal(m - i) * np.exp(-np.arange(m - i) / SR / 0.06)
        c = c - np.convolve(c, np.ones(6) / 6, mode="same")
        drums.add(beat, c, g * 0.9)


def tom(beat, f0=150, g=0.5):
    n = int(0.25 * SR)
    t = np.arange(n) / SR
    f = f0 * (1 + 0.6 * np.exp(-t / 0.03))
    drums.add(beat, np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.12), g)


def hat(beat, g=0.08, opn=False):
    n = int((0.14 if opn else 0.035) * SR)
    x = rng.standard_normal(n)
    x = x - np.convolve(x, np.ones(4) / 4, mode="same")
    drums.add(beat, x * np.exp(-np.arange(n) / SR / (0.06 if opn else 0.01)), g)


def crash(beat, g=0.2):
    n = int(1.6 * SR)
    x = rng.standard_normal(n)
    x = x - np.convolve(x, np.ones(3) / 3, mode="same")
    drums.add(beat, x * np.exp(-np.arange(n) / SR / 0.5), g)


def roll(b0, beats, g0=0.12, g1=0.38):
    steps = int(beats * 4)
    for i in range(steps):
        snare(b0 + i * 0.25, g0 + (g1 - g0) * i / max(1, steps - 1))


# ---------------------------------------------------------------- grooves
def march(b0, bars=1, fill=False):
    for k in range(bars):
        b = b0 + k * 4
        for i in range(4):
            kick(b + i, 0.9 if i % 2 == 0 else 0.6)
            hat(b + i + 0.5)
        snare(b + 1)
        snare(b + 3)
        snare(b + 3.75, 0.18)  # pickup ghost, the march "rat-a"
    if fill:
        b = b0 + (bars - 1) * 4
        for i, f in enumerate((210, 180, 150, 120)):
            tom(b + 2 + i * 0.5, f)


def halftime(b0, bars=1):
    for k in range(bars):
        b = b0 + k * 4
        kick(b)
        kick(b + 1.5, 0.55)
        snare(b + 2)
        for i in range(8):
            hat(b + i * 0.5, 0.06 if i % 2 else 0.08)


def bass_drive(b0, roots):
    """octave-bouncing eighths, one root per bar"""
    for k, r in enumerate(roots):
        hi = r[:-1] + str(int(r[-1]) + 1)
        for i in range(8):
            bass(b0 + k * 4 + i * 0.5, r if i % 2 == 0 else hi, 0.5)


def bass_gallop(b0, roots):
    """battle-ish gallop: 8th + two 16ths"""
    for k, r in enumerate(roots):
        for i in range(4):
            b = b0 + k * 4 + i
            bass(b, r, 0.5)
            bass(b + 0.5, r, 0.25)
            bass(b + 0.75, r, 0.25)


def arp(b0, chords, gain=0.055):
    for k, ch in enumerate(chords):
        for i in range(16):
            tone(arpb, b0 + k * 4 + i * 0.25, ch[[0, 1, 2, 1][i % 4]], 0.25, duty=0.125, gain=gain, vib=0)


def supersaw(f, n, voices=5, detune=0.012):
    t = np.arange(n) / SR
    x = np.zeros(n)
    for v in range(voices):
        d = 1 + detune * (v - (voices - 1) / 2) / ((voices - 1) / 2)
        x += 2 * ((t * f * d + v * 0.37) % 1.0) - 1
    x /= voices
    return lowpass(x, 2400)


def lowpass(x, fc):
    """one-pole low-pass, vectorised with an IIR via lfilter-free recursion in blocks"""
    a = np.exp(-2 * np.pi * fc / SR)
    y = np.empty_like(x)
    acc = 0.0
    # fast enough for pad-length notes
    for i in range(len(x)):
        acc = (1 - a) * x[i] + a * acc
        y[i] = acc
    return y


def chord_pad(b0, chord, length, gain=0.045):
    for name in chord:
        m = midi(name) + transpose
        n = int(length * BEAT * SR)
        pad.add(b0, supersaw(hz(m), n) * env(n, a=0.08, d=0.2, s=0.8, r=0.25), gain * 1.6)


def riser(b_end, beats=2, g=0.12):
    """white-noise sweep up into a section"""
    n = int(beats * BEAT * SR)
    t = np.linspace(0, 1, n)
    x = rng.standard_normal(n)
    hp = x - np.convolve(x, np.ones(8) / 8, mode="same")
    sig = ((1 - t) * x * 0.3 + t * hp) * t ** 2
    fxb.add(b_end - beats, sig, g)


# ---------------------------------------------------------------- the tune (original)
# Hook fanfare: triplet pickup into a held high note, answered a step lower.
FANFARE = [(0, "G4", 1 / 3), (1 / 3, "C5", 1 / 3), (2 / 3, "E5", 1 / 3), (1, "G5", 1.5, "/"),
           (2.5, "F5", .25, "s"), (2.75, "E5", .25, "s"), (3, "F5", 1), (4, "A5", 1.5, "/"), (5.5, "G5", .5, "s")]
FANFARE_LO = [(1, "E5", 1.5), (3, "D5", 1), (4, "F5", 1.5), (5.5, "E5", .5, "s")]

# Theme A (march, dotted): over C - Bb - F - G
THEME_A = [(0, "E5", .75), (.75, "F5", .25), (1, "G5", 1), (2, "C6", .75), (2.75, "B5", .25), (3, "G5", 1),
           (4, "F5", .75), (4.75, "G5", .25), (5, "A#5", 1), (6, "A5", .5, "s"), (6.5, "G5", .5, "s"), (7, "F5", 1),
           (8, "A5", .75), (8.75, "G5", .25), (9, "F5", .5), (9.5, "E5", .5)]
THEME_A2 = [(0, "C5", .75), (.75, "D5", .25), (1, "E5", 1), (2, "G5", .75), (2.75, "F5", .25), (3, "E5", 1),
            (4, "D5", .75), (4.75, "E5", .25), (5, "F5", 1), (6, "F5", .5, "s"), (6.5, "E5", .5, "s"), (7, "D5", 1),
            (8, "F5", .75), (8.75, "E5", .25), (9, "D5", .5), (9.5, "C5", .5)]

# Theme B (after the key change): climbing sequence, stabs on the mood hits
THEME_B = [(0, "C5", .5, "s"), (.5, "C5", .25, "s"), (.75, "D5", .25), (1, "E5", 1, "/"), (2, "G5", 1), (3, "E5", .5, "s"),
           (3.5, "D5", .5), (4, "C5", .5, "s"), (4.5, "D5", .5), (5, "E5", 1.5), (6.5, "G5", .5), (7, "A5", 1, "/"),
           (8, "A5", .5, "s"), (8.5, "G5", .25, "s"), (8.75, "A5", .25), (9, "B5", 1), (10, "D6", 1, "/"),
           (11, "B5", .5, "s"), (11.5, "G5", .5), (12, "C6", 2, "/")]
THEME_B2 = [(0, "A4", .5, "s"), (.5, "A4", .25, "s"), (.75, "B4", .25), (1, "C5", 1), (2, "E5", 1), (3, "C5", .5, "s"),
            (3.5, "B4", .5), (4, "A4", .5, "s"), (4.5, "B4", .5), (5, "C5", 1.5), (6.5, "E5", .5), (7, "F5", 1),
            (8, "F5", .5, "s"), (8.5, "E5", .25, "s"), (8.75, "F5", .25), (9, "G5", 1), (10, "B5", 1),
            (11, "G5", .5, "s"), (11.5, "E5", .5), (12, "E5", 2)]

# Skill jingle: "used a move!" — quick rising run, then a playful answer
MOVE = [(0, "C6", .25, "s"), (.25, "G5", .25, "s"), (.5, "E6", .5, "/"), (1, "D6", .25, "s"), (1.25, "E6", .75)]
MOVE_ANS = [(2, "A5", .5, "s"), (2.5, "G5", .5, "s"), (3, "E5", .5), (3.5, "G5", .5)]

# Finale: the hook fanfare resolved, up a step
FINALE = [(0, "G5", 1 / 3), (1 / 3, "A5", 1 / 3), (2 / 3, "B5", 1 / 3), (1, "D6", 1, "/"), (2, "C6", .5, "s"),
          (2.5, "D6", .5, "s"), (3, "E6", 3, "/")]
FINALE_LO = [(1, "B5", 1), (2, "A5", .5, "s"), (2.5, "B5", .5, "s"), (3, "C6", 3)]


def compose():
    """beat map (shots_h.py): reveal 0 (screen on 3), switch 10 (12 14 16 18), angry 20 (22), sparks 28 (30),
    cool 34 (36), skills 40 / 50 / 56 / 62 (badges 41 51 57 63), lineup 72, end 84 (card 88)"""
    global transpose
    # ---- reveal 0-10: dark pad, riser into the screen lighting up, fanfare on 3
    transpose = 0
    chord_pad(0, ["C4", "G4"], 3, 0.03)
    riser(3, 3, 0.1)
    crash(3, 0.24)
    kick(3)
    mel(lead1, 3, FANFARE, gain=0.17)
    mel(lead2, 3, FANFARE_LO, gain=0.11, duty=0.5)
    chord_pad(4, ["C4", "E4", "G4"], 2)
    chord_pad(6, ["F4", "A4", "C5"], 1)
    chord_pad(7, ["F4", "A4", "D5"], 2)
    for bb, f in ((4, 110), (5, 110), (6, 130), (7, 110)):
        tom(bb, f, 0.45)
    bass(4, "C3", 2)
    bass(6, "F2", 1)
    bass(7, "D3", 1.5)
    roll(9, 1)

    # ---- switch 10-20: theme A march (a face change lands on every other beat)
    riser(10, 1, 0.1)
    crash(10)
    chord_pad(10, ["C4", "E4", "G4"], 4)
    chord_pad(14, ["A#3", "D4", "F4"], 4)
    march(10, 2)
    bass_drive(10, ["C3", "A#2"])
    mel(lead1, 10, THEME_A, gain=0.16)
    mel(lead2, 10, THEME_A2, gain=0.1, duty=0.5)
    for bb in (12, 14, 16):
        hat(bb, 0.1, True)
    kick(18)
    kick(19)
    bass(18, "G2", 1)
    bass(19, "G2", .5)
    bass(19.5, "B2", .5)
    roll(18, 2, 0.1, 0.4)
    chord_pad(18, ["G4", "B4", "D5"], 2)

    # ---- moods 20-40: key change up a step; hits on angry 22, sparks 30, shades 36
    riser(20, 2, 0.14)
    transpose = 2
    crash(20, 0.26)
    march(20, 4)
    bass_gallop(20, ["C3", "G2", "A2", "F2"])
    arp(20, [["C5", "E5", "G5"], ["B4", "D5", "G5"], ["A4", "C5", "E5"], ["A4", "C5", "F5"]])
    chord_pad(20, ["C4", "E4", "G4"], 4)
    chord_pad(24, ["B3", "D4", "G4"], 4)
    chord_pad(28, ["A3", "C4", "E4"], 4)
    chord_pad(32, ["A3", "C4", "F4"], 4)
    mel(lead1, 20, THEME_B, gain=0.16)
    mel(lead2, 20, THEME_B2, gain=0.1, duty=0.5)
    mel(lead1, 34, [(0, "G5", .5, "s"), (.5, "A5", .5, "s"), (1, "C6", 1, "/")], gain=0.15)
    for bb in (22, 30, 36):
        crash(bb, 0.14)
        kick(bb)
    bass(36, "F2", 1)
    bass(37, "G2", 1)
    for i, f in enumerate((220, 190, 160, 140, 120, 100, 90, 80)):
        tom(38 + i * 0.25, f, 0.4)
    snare(39.5, 0.4)
    snare(39.75, 0.45)

    # ---- skills 40-72: half-time; a "move!" jingle on every badge
    transpose = 0
    crash(40, 0.14)
    halftime(40, 8)
    roots = ["F2", "G2", "E2", "A2"] * 2
    pads = [["F4", "A4", "C5"], ["G4", "B4", "D5"], ["E4", "G4", "C5"], ["A4", "C5", "E5"]] * 2
    for k, r in enumerate(roots):
        bb = 40 + k * 4
        bass(bb, r, 1.5)
        bass(bb + 1.5, r, .5)
        bass(bb + 2, r[:-1] + "3", 1)
        bass(bb + 3, r, 1)
        chord_pad(bb, pads[k], 4)
    for bb in (41, 51, 57, 63):
        mel(lead1, bb, MOVE, gain=0.15)
        mel(lead2, bb, MOVE_ANS, gain=0.11, duty=0.5)
        hat(bb, 0.12, True)
    roll(71, 1)

    # ---- lineup 72-84: theme A, up a step, everything in
    riser(72, 2, 0.14)
    transpose = 2
    crash(72, 0.26)
    march(72, 3)
    bass_drive(72, ["C3", "A#2", "G2"])
    arp(72, [["C5", "E5", "G5"], ["A#4", "D5", "F5"], ["B4", "D5", "G5"]], 0.06)
    chord_pad(72, ["C4", "E4", "G4"], 4)
    chord_pad(76, ["A#3", "D4", "F4"], 4)
    chord_pad(80, ["B3", "D4", "G4"], 4)
    mel(lead1, 72, THEME_A, gain=0.17)
    mel(lead2, 72, THEME_A2, gain=0.11, duty=0.5)
    roll(83, 1, 0.15, 0.45)

    # ---- end 84-96: finale fanfare, the card lands on 88 with the last chord
    riser(84, 1, 0.12)
    transpose = 0
    crash(84, 0.3)
    kick(84)
    tom(84.5, 120, 0.4)
    mel(lead1, 84, FINALE, gain=0.17)
    mel(lead2, 84, FINALE_LO, gain=0.11, duty=0.5)
    bass(84, "G2", 1)
    bass(85, "G2", 1)
    bass(86, "D3", 1)
    bass(87, "C3", 1)
    kick(88)
    crash(88, 0.24)
    bass(88, "C3", 7)
    chord_pad(88, ["C5", "E5", "G5"], 8, 0.06)
    chord_pad(88, ["C4", "G4"], 8, 0.04)


def fft_convolve(x, ir):
    n = len(x) + len(ir) - 1
    m = 1 << (n - 1).bit_length()
    return np.fft.irfft(np.fft.rfft(x, m) * np.fft.rfft(ir, m), m)[:len(x)]


def reverb_ir(seconds=1.6, seed=0):
    r = np.random.default_rng(seed)
    n = int(seconds * SR)
    t = np.arange(n) / SR
    ir = r.standard_normal(n) * np.exp(-t / (seconds / 5))
    ir[:int(0.012 * SR)] = 0  # pre-delay
    ir = ir - np.convolve(ir, np.ones(30) / 30, mode="same")  # keep the tail bright, not muddy
    return ir / np.sqrt((ir ** 2).sum())


def pingpong(x, delay_s, fb=0.35, taps=5):
    d = int(delay_s * SR)
    L, R = np.zeros_like(x), np.zeros_like(x)
    for k in range(1, taps + 1):
        g = fb ** k
        tgt = L if k % 2 else R
        tgt[d * k:] += g * x[:-d * k]
    return L, R


def sidechain(n, depth=0.55, release=0.16):
    """gain curve that ducks on every kick and recovers"""
    g = np.ones(n)
    rel = int(release * SR)
    curve = 1 - depth * np.exp(-np.arange(rel) / (rel / 4))
    for b in KICK_TIMES:
        i = int(b * BEAT * SR)
        if i < n:
            seg = g[i:i + rel]
            g[i:i + rel] = np.minimum(seg, curve[:len(seg)])
    return g


def main():
    compose()
    n = int(TOTAL * BEAT * SR)
    cut = lambda b: b.x[:n]
    sc = sidechain(n)

    dry_l = np.zeros(n)
    dry_r = np.zeros(n)

    def pan_add(x, pan, gain=1.0):
        nonlocal dry_l, dry_r
        dry_l += gain * x * (1 - max(0, pan))
        dry_r += gain * x * (1 + min(0, pan))

    pan_add(cut(lead1), -0.1, 1.1)
    pan_add(cut(lead2), 0.25, 0.8)
    pan_add(cut(bassb) * sc, 0, 0.6)
    pan_add(cut(sub) * sc, 0, 0.38)
    pan_add(cut(kicks), 0, 0.5)
    pan_add(cut(drums), 0, 0.55)
    pan_add(cut(arpb) * sc, 0.35, 1.5)
    pan_add(cut(pad) * sc, 0, 1.6)
    pan_add(cut(fxb), 0, 0.8)

    # dotted-eighth ping-pong on the lead
    dl, dr = pingpong(cut(lead1), 0.75 * BEAT, fb=0.32)
    dry_l += 0.35 * dl
    dry_r += 0.35 * dr
    # reverb send: leads, arp, pad, a little snare
    send = 0.5 * cut(lead1) + 0.4 * cut(lead2) + 0.5 * cut(arpb) + 0.35 * cut(pad) + 0.15 * cut(drums)
    wet_l = fft_convolve(send, reverb_ir(1.6, 1))
    wet_r = fft_convolve(send, reverb_ir(1.6, 2))
    L = dry_l + 0.28 * wet_l
    R = dry_r + 0.28 * wet_r

    st = np.stack([L, R], 1)
    st -= st.mean(0)
    fade = int(1.0 * SR)
    st[-fade:] *= (np.linspace(1, 0, fade) ** 1.5)[:, None]
    # master: modest loudness (not loud), soft limiter as glue
    st *= 0.13 / max(1e-6, np.sqrt((st ** 2).mean()))
    st = np.tanh(st * 1.3) / 1.3
    st *= 0.72 / max(0.72, np.abs(st).max())
    (ROOT / "out").mkdir(exist_ok=True)
    out = ROOT / "out" / "music_h.wav"
    with wave.open(str(out), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((st * 32767).astype("<i2").tobytes())
    print(f"{out.name}: {n / SR:.1f}s  peak {np.abs(st).max():.2f}  rms {np.sqrt((st ** 2).mean()):.3f}")


if __name__ == "__main__":
    main()
