# -*- coding: utf-8 -*-
"""音频层：复用《渐进记号》asymptote 的程序化合成器。

16bit 单声道/立体声自适应，启动时生成音色；不依赖外部素材。
"""
import math
import random
import struct

import pygame

SR = 44100
_enabled = False
_muted = False
_sounds = {}
_last = {}
_freq = SR
_ch = 1
_devices = []
_dev_idx = -1


def output_devices():
    """列出 Windows/SDL 的播放设备，供 F3 切换。"""
    global _devices
    try:
        from pygame._sdl2 import audio as sdl_audio
        _devices = list(sdl_audio.get_audio_device_names(False))
    except Exception:
        _devices = []
    return _devices


def current_device():
    if 0 <= _dev_idx < len(_devices):
        return _devices[_dev_idx]
    return None


def next_device():
    """依次切换输出设备；返回新设备名，失败返回 None。"""
    global _dev_idx
    names = output_devices()
    if not names:
        return None
    for _ in range(len(names)):
        _dev_idx = (_dev_idx + 1) % len(names)
        try:
            if _reinit(names[_dev_idx]):
                _devices = names
                return names[_dev_idx]
        except Exception:
            continue
    # 命名设备都失败时回退默认设备；真的出声了就返回可见提示。
    if _reinit(None):
        return "默认音频设备"
    return None


def _pack(buf, v):
    for _ in range(_ch):
        buf += struct.pack("<h", v)


def _render(dur, fn, vol=0.5, attack=0.004, decay=3.0, curve=1.0):
    n = max(8, int(_freq * dur))
    buf = bytearray()
    a_n = max(1, int(attack * _freq))
    for i in range(n):
        t = i / n
        s = fn(t)
        env = min(1.0, i / a_n) * math.exp(-decay * (t ** curve))
        v = s * env * vol
        if v > 1.0:
            v = 1.0
        elif v < -1.0:
            v = -1.0
        _pack(buf, int(v * 32000))
    return pygame.mixer.Sound(buffer=bytes(buf))


def _sweep(f0, f1, dur, vol=0.4, kind="sine", decay=3.0, noise=0.0, curve=1.0):
    phase = [0.0]

    def fn(t):
        f = f0 * (f1 / f0) ** t
        phase[0] += 2 * math.pi * f / _freq
        p = phase[0]
        if kind == "square":
            s = 1.0 if math.sin(p) > 0 else -1.0
        elif kind == "saw":
            s = 2.0 * ((p / (2 * math.pi)) % 1.0) - 1.0
        elif kind == "tri":
            s = 4.0 * abs((p / (2 * math.pi)) % 1.0 - 0.5) - 1.0
        else:
            s = math.sin(p)
        if noise > 0:
            s = s * (1 - noise) + random.uniform(-1, 1) * noise
        return s

    return _render(dur, fn, vol, decay=decay, curve=curve)


def _chord(freqs, dur, vol=0.4, decay=2.6, gap=0.0):
    total = dur + gap * (len(freqs) - 1)
    n = max(8, int(_freq * total))
    buf = bytearray()
    phases = [0.0] * len(freqs)
    starts = [int(gap * i * _freq) for i in range(len(freqs))]
    for i in range(n):
        s = 0.0
        for k, f in enumerate(freqs):
            j = i - starts[k]
            if j < 0:
                continue
            t = j / _freq
            phases[k] += 2 * math.pi * f / _freq
            env = min(1.0, j / max(1, int(0.004 * _freq))) * math.exp(-decay * t)
            s += math.sin(phases[k]) * env
        s /= max(1, len(freqs)) * 1.4
        _pack(buf, int(max(-1.0, min(1.0, s * vol)) * 32000))
    return pygame.mixer.Sound(buffer=bytes(buf))


def _reinit(devicename=None):
    """强制重建混音器；devicename 非空时只尝试该设备。"""
    global _enabled, _freq, _ch
    last = None
    base = [
        {"frequency": SR, "size": -16, "channels": 1, "buffer": 512},
        {"frequency": SR, "size": -16, "channels": 2, "buffer": 512},
        {"frequency": 48000, "size": -16, "channels": 2, "buffer": 1024},
        {"frequency": SR, "size": -16, "buffer": 1024},
        {},
    ]
    if devicename:
        # 有些设备只接受 48k/单声道；命名设备也要遍历全部格式再放弃。
        base = [dict(kw, devicename=devicename) for kw in base]
    for kw in base:
        try:
            try:
                pygame.mixer.quit()
            except Exception:
                pass
            pygame.mixer.init(**kw)
            got = pygame.mixer.get_init()
            if not got:
                raise RuntimeError("mixer not ready")
            _freq = got[0]
            _ch = got[2]
            try:
                pygame.mixer.set_num_channels(24)
            except Exception:
                pass
            _build()
            _enabled = True
            return True
        except Exception as exc:
            last = exc
            _enabled = False
    try:
        if last:
            print("[audio] disabled:", last)
    except Exception:
        pass
    return False


def init():
    global _enabled, _freq, _ch
    # 如果 App 在 pygame.init() 前 pre_init 过低延迟缓冲区，直接复用
    try:
        got = pygame.mixer.get_init()
        if got:
            _freq = got[0]
            _ch = got[2]
            try:
                pygame.mixer.set_num_channels(24)
            except Exception:
                pass
            _build()
            _enabled = True
            return True
    except Exception:
        pass
    return _reinit()


def _build():
    s = _sounds
    s["link"] = _chord([520, 780, 1046], 0.28, 0.30, decay=4.6, gap=0.025)
    s["cut"] = _sweep(1400, 240, 0.12, 0.32, "saw", decay=7.0, noise=0.30)
    s["weak"] = _sweep(320, 460, 0.16, 0.28, "tri", decay=4.6)
    s["gc"] = _sweep(720, 120, 0.22, 0.28, "sine", decay=4.0, noise=0.10)
    s["gcstart"] = _chord([220, 330, 440], 0.42, 0.34, decay=2.4, gap=0.08)
    s["boom"] = _sweep(92, 38, 0.60, 0.52, "saw", decay=2.8, noise=0.78)
    s["write"] = _sweep(240, 150, 0.08, 0.26, "square", decay=9.0, noise=0.32)
    s["hurt"] = _sweep(160, 78, 0.20, 0.34, "sine", decay=4.6, noise=0.30)
    s["death"] = _sweep(320, 36, 1.05, 0.44, "saw", decay=1.4, noise=0.15)
    s["cast"] = _chord([620, 880, 1180, 1560], 0.30, 0.34, decay=3.6, gap=0.018)
    s["alias"] = _chord([440, 554, 659, 880], 0.42, 0.30, decay=2.6, gap=0.04)
    s["hijack"] = _chord([660, 880, 1100, 1320], 0.48, 0.28, decay=2.4, gap=0.04)
    s["ui"] = _sweep(1100, 1100, 0.04, 0.16, "square", decay=10.0)
    s["dash"] = _sweep(600, 1500, 0.14, 0.20, "sine", decay=6.0, noise=0.48)
    s["clear"] = _chord([523, 659, 784, 1046], 0.56, 0.34, decay=2.4, gap=0.065)
    s["win"] = _chord([523, 659, 784, 1046, 1318], 1.2, 0.38, decay=1.4, gap=0.08)
    s["glitch"] = _sweep(120, 1200, 0.18, 0.28, "square", decay=5.0, noise=0.75)
    s["meta"] = _sweep(300, 760, 0.18, 0.24, "sine", decay=5.0)
    s["select"] = _sweep(660, 990, 0.06, 0.18, "square", decay=9.0)
    s["place"] = _sweep(300, 620, 0.14, 0.24, "sine", decay=5.0, noise=0.06)
    s["deny"] = _sweep(220, 108, 0.20, 0.30, "square", decay=3.4, noise=0.25)
    s["corehit"] = _sweep(90, 45, 0.30, 0.42, "saw", decay=3.4, noise=0.42)
    s["corebreak"] = _sweep(70, 28, 1.25, 0.56, "saw", decay=1.6, noise=0.55)
    s["battle"] = _chord([110, 165, 220, 330], 0.90, 0.38, decay=1.8, gap=0.10)
    s["hover"] = _sweep(1200, 1500, 0.03, 0.08, "sine", decay=12.0)
    s["anchor"] = _chord([392, 523, 659], 0.42, 0.30, decay=2.6, gap=0.05)
    s["warn"] = _sweep(220, 180, 0.32, 0.30, "square", decay=2.4, noise=0.10)


def toggle_mute():
    global _muted
    _muted = not _muted
    if _muted:
        try:
            pygame.mixer.stop()
        except Exception:
            pass
    return _muted


def is_muted():
    return _muted


def play(name, vol=1.0, gap=0.045):
    if not _enabled or _muted:
        return
    snd = _sounds.get(name)
    if snd is None:
        return
    now = pygame.time.get_ticks() / 1000.0
    if now - _last.get(name, -9) < gap:
        return
    _last[name] = now
    try:
        ch = pygame.mixer.find_channel()
        if ch is None:
            snd.play()
            return
        ch.set_volume(max(0.0, min(1.0, vol)))
        ch.play(snd)
    except Exception:
        pass


def play_cast(sig, strength=0.6):
    play("cast", 0.55 + 0.45 * strength, gap=0.03)
