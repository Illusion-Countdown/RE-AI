# -*- coding: utf-8 -*-
"""单人音频自检：初始化、设备、音量、实际播放。"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame

pygame.mixer.pre_init(44100, -16, 2, 512)
pygame.init()
print("SDL audio driver:", os.environ.get("SDL_AUDIODRIVER", "(default)"))
print("mixer:", pygame.mixer.get_init())
try:
    from pygame._sdl2 import audio as sdl_audio
    print("output devices:", sdl_audio.get_audio_device_names(False))
except Exception as exc:
    print("device list unavailable:", exc)

from memory_run import audio

ok = audio.init()
print("audio.init:", ok, "enabled:", audio._enabled,
      "muted:", audio.is_muted(), "sounds:", len(audio._sounds))
if not ok:
    print("音频设备初始化失败；请检查 Windows 输出设备/音量合成器。")
    pygame.quit()
    sys.exit(1)

for name in ("select", "cut", "weak", "alias", "win"):
    audio.play(name, 1.0, gap=0)
    time.sleep(0.12)
    print(name, "busy:", pygame.mixer.get_busy())

print("如果这里仍然没有声音，但 busy=True，说明游戏已送到系统混音器；")
print("请检查 Windows 音量合成器里 Python 的独立音量、默认输出设备和蓝牙延迟。")
time.sleep(0.8)
pygame.quit()
