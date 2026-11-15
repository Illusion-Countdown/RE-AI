# -*- coding: utf-8 -*-
"""性能测试：无头渲染若干帧，统计平均帧时间。"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame
pygame.init()

from dangle.app import App
from dangle.battle import Battle
from dangle.content import BODIES
from dangle.const import *


def bench(room, frames=240):
    app = App(fullscreen=False, headless=True)
    app.start_run(0)
    app.run.room_index = room
    app.battle = Battle(app.run, room)
    app.battle.state = "playing"
    app.battle.intro_t = 0
    app.state = "play"
    app.fade = 0
    b = app.battle
    # 预热
    for _ in range(30):
        b.update(1 / 60, {"mvx": 0, "mvy": 0, "plan": False, "dash": False})
        app.draw()
    t0 = time.perf_counter()
    for i in range(frames):
        b.update(1 / 60, {"mvx": 1 if i % 60 < 30 else -1, "mvy": 0,
                          "plan": False, "dash": False})
        app.draw()
    dt = (time.perf_counter() - t0) / frames
    print(f"room {room+1}: {dt*1000:.2f} ms/frame  ({1/dt:.0f} fps)  nodes={len(b.graph.nodes)} edges={len(b.graph.edges)}")
    return dt


for r in (0, 5, 7, 8):
    bench(r)

# 标题/奖励
app = App(fullscreen=False, headless=True)
t0 = time.perf_counter()
for _ in range(120):
    app.update(1 / 60)
    app.draw()
dt = (time.perf_counter() - t0) / 120
print(f"title: {dt*1000:.2f} ms/frame ({1/dt:.0f} fps)")
