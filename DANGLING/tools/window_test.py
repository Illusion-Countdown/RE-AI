# -*- coding: utf-8 -*-
"""真实窗口冒烟测试：开窗口跑 180 帧，模拟鼠标拖拽与按键，然后退出。"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame
from dangle.app import App
from dangle.battle import Battle
from dangle.const import *

app = App(fullscreen=False)
print("display size:", pygame.display.get_surface().get_size())
app.start_run(0)
b = app.battle
b.state = "playing"
b.intro_t = 0

# 拖拽建边：从玩家拖到 sentinel
sent = [n for n in b.graph.nodes if n.kind == "SENTINEL"][0]
p0 = (int(b.px), int(b.py))
p1 = (int(sent.x), int(sent.y))
app.mouse = p0
b.on_mouse_down(p0, 1, 0)
app.mouse = p1
b.on_mouse_move(p1)
b.on_mouse_up(p1, 1)

# 切工具、剪线
b.choose_tool(1)
edge = [e for e in b.graph.edges if e.alive][0]
pts = edge.points(10)
mid = pts[5]
app.mouse = (int(mid[0]), int(mid[1]))
b.on_mouse_down(app.mouse, 1, 0)
b.on_mouse_up(app.mouse, 1)

for i in range(180):
    app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_d)) if i == 10 else None
    app.update(1 / 60)
    app.draw()
    pygame.display.flip()
    time.sleep(1 / 120)
print("battle state:", b.state, "nodes:", len(b.graph.nodes), "score:", b.run.score)
pygame.quit()
print("WINDOW OK")
