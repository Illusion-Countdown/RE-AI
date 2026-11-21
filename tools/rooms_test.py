# -*- coding: utf-8 -*-
"""Clear every fixed room and both boss variants, checking result plumbing."""
import os
import sys

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame

from memory_run.runstate import RunState
from memory_run.ui.battle_factory import create_battle
from memory_run.content import RUN_ROOMS, TUTORIAL_COUNT


def clear_room(step):
    r = RunState(seed=3, body_id="tree")
    r.step = step
    r.begin_room()
    b = create_battle(r)
    b.state = "playing"
    b.intro_t = 0
    room = r.room
    # B1: pylons first, then core
    for n in list(b.graph.nodes):
        if n.alive and n.hostile:
            if n.kind in ("GC_CORE", "AUDITOR", "KERNEL"):
                continue
            b.apply_damage(n, 99999, source="test")
    for n in list(b.graph.nodes):
        if n.alive and n.hostile:
            b.apply_damage(n, 99999, source="test")
    if b.state == "playing":
        b.check_clear()
    for _ in range(300):
        b.update(1 / 60, {"mouse": (800, 400), "mvx": 0, "mvy": 0})
        if b.finished:
            break
    assert b.finished, (room["code"], b.state, [n.name for n in b.graph.nodes if n.alive])
    assert b.result and b.result.get("cleared"), (room["code"], b.result)
    print(room["code"], "ok", b.result["score"])


def main():
    pygame.init()
    pygame.display.set_mode((1600, 900))
    for i in range(TUTORIAL_COUNT, TUTORIAL_COUNT + len(RUN_ROOMS)):
        clear_room(i)
    print("ALL ROOMS OK")


if __name__ == "__main__":
    main()
