# -*- coding: utf-8 -*-
"""极简程序化音效：不依赖音频素材，避免 numpy。"""
import array
import math
import random

import pygame

_OK = False
_SOUNDS = {}
_MUTED = False
_SR = 44100


def _env(i, n, attack=0.01, release=0.6):
    a = int(n * attack)
    if i < a:
        return i / max(1, a)
    r = int(n * release)
    if i > n - r:
        return max(0.0, (n - i) / max(1, r))
    return 1.0


def _tone(freq, dur, vol=0.35, kind="sine", freq2=None, noise=0.0, decay=2.4):
    n = int(_SR * dur)
    buf = array.array("h")
    ph = 0.0
    for i in range(n):
        t = i / _SR
        f = freq if freq2 is None else freq + (freq2 - freq) * (i / n)
        ph += math.tau * f / _SR
        if kind == "sine":
            v = math.sin(ph)
        elif kind == "sq":
            v = 1.0 if math.sin(ph) > 0 else -1.0
        elif kind == "saw":
            v = (ph / math.pi) % 2 - 1
        else:
            v = random.uniform(-1, 1)
        if noise > 0:
            v = v * (1 - noise) + random.uniform(-1, 1) * noise
        e = _env(i, n) * math.exp(-decay * t)
        v *= vol * e
        buf.append(int(max(-1.0, min(1.0, v)) * 32000))
    return _mk(buf)


def _mk(buf):
    try:
        return pygame.mixer.Sound(buffer=buf.tobytes())
    except Exception:
        return None


def _chord(freqs, dur, vol=0.3, decay=2.0):
    n = int(_SR * dur)
    buf = array.array("h")
    phs = [0.0] * len(freqs)
    for i in range(n):
        t = i / _SR
        v = 0.0
        for k, f in enumerate(freqs):
            phs[k] += math.tau * f / _SR
            v += math.sin(phs[k]) / len(freqs)
        e = _env(i, n) * math.exp(-decay * t)
        buf.append(int(max(-1.0, min(1.0, v * vol * e)) * 32000))
    return _mk(buf)


def init():
    global _OK
    try:
        pygame.mixer.init(frequency=_SR, size=-16, channels=1, buffer=512)
    except Exception:
        _OK = False
        return
    _OK = True
    try:
        _SOUNDS["link"] = _tone(520, 0.10, 0.22, "sine", 880, decay=6)
        _SOUNDS["cut"] = _tone(1400, 0.09, 0.20, "saw", 300, noise=0.35, decay=8)
        _SOUNDS["weak"] = _tone(320, 0.12, 0.18, "sine", 420, decay=5)
        _SOUNDS["gc"] = _tone(700, 0.20, 0.18, "sine", 120, noise=0.1, decay=4)
        _SOUNDS["gcstart"] = _chord([220, 330, 440], 0.55, 0.24, 2.2)
        _SOUNDS["boom"] = _tone(90, 0.6, 0.55, "noise", 40, noise=0.9, decay=3.2)
        _SOUNDS["write"] = _tone(240, 0.08, 0.22, "sq", 160, noise=0.4, decay=14)
        _SOUNDS["hurt"] = _tone(140, 0.22, 0.35, "saw", 70, noise=0.3, decay=7)
        _SOUNDS["death"] = _tone(400, 1.1, 0.4, "saw", 50, noise=0.25, decay=1.8)
        _SOUNDS["cast"] = _tone(900, 0.22, 0.22, "sine", 1800, noise=0.25, decay=4)
        _SOUNDS["alias"] = _chord([440, 554, 659], 0.4, 0.26, 3.0)
        _SOUNDS["hijack"] = _chord([660, 880, 1100, 1320], 0.5, 0.24, 2.4)
        _SOUNDS["ui"] = _tone(880, 0.05, 0.12, "sine", 1200, decay=16)
        _SOUNDS["dash"] = _tone(600, 0.14, 0.16, "noise", 1400, noise=0.5, decay=7)
        _SOUNDS["clear"] = _chord([523, 659, 784, 1046], 0.8, 0.26, 1.6)
        _SOUNDS["win"] = _chord([523, 659, 784, 1046, 1318], 1.6, 0.30, 0.8)
        _SOUNDS["glitch"] = _tone(120, 0.18, 0.2, "noise", 1200, noise=0.8, decay=6)
        _SOUNDS["meta"] = _tone(300, 0.18, 0.2, "sine", 760, decay=5)
        _SOUNDS["select"] = _tone(660, 0.08, 0.16, "sine", 990, decay=10)
    except Exception:
        _OK = False


def play(name, vol=1.0):
    if not _OK or _MUTED:
        return
    s = _SOUNDS.get(name)
    if s is not None:
        try:
            s.set_volume(vol)
            s.play()
        except Exception:
            pass


def toggle_mute():
    global _MUTED
    _MUTED = not _MUTED
    return _MUTED
