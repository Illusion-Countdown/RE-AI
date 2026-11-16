# -*- coding: utf-8 -*-
"""回归：所有“边列表”工具不得因 list target 抛异常。"""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame

from memory_run.app import App
from memory_run.cards import Card

for key in ("STEAL", "REFLECT", "WEAKEN", "DELAY"):
    app = App(fullscreen=False, headless=True)
    app.new_run(False)
    app.start_battle()
    b = app.battle
    edge = next(e for e in b.graph.edges if e.alive and e.src.kind == "ROOT")
    try:
        b.apply_card(Card(key), [edge])
    except Exception as exc:
        raise AssertionError(f"{key} list target crashed: {exc}") from exc
    print(key, "list target ok")
    pygame.quit()

print("TOOL TARGET OK")
