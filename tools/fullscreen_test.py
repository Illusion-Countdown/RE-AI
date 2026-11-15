# -*- coding: utf-8 -*-
"""全屏冒烟测试：真实全屏 120 帧。"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame
from dangle.app import App

app = App(fullscreen=True)
print("fullscreen surface:", pygame.display.get_surface().get_size(),
      "driver:", pygame.display.get_driver())
app.start_run(0)
app.battle.intro_t = 0
app.fade = 0
for i in range(120):
    app.update(1 / 60)
    app.draw()
    pygame.display.flip()
print("state:", app.state, "fps:", round(app.clock.get_fps(), 1))
pygame.quit()
print("FULLSCREEN OK")
