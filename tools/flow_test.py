# -*- coding: utf-8 -*-
"""流程集成测试：标题→选身体→战斗→奖励→下一关→死亡/胜利。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame
pygame.init()

from dangle.app import App
from dangle.battle import Battle
from dangle.const import *
from dangle.model import STRONG

OK, BAD = [], []


def check(c, m):
    (OK if c else BAD).append(m)
    print(("  [ok] " if c else "  [FAIL] ") + m)


def step(app, n=1, dt=1 / 60):
    for _ in range(n):
        app.update(dt)
        app.draw()


def force_clear(b):
    """用最优解把当前房间清空。"""
    for _ in range(40):
        if b.state in ("clear", "done", "victory"):
            return
        moved = False
        for e in list(b.graph.edges):
            if not e.alive or e.kind != STRONG:
                continue
            if e.src.kind == "BOMB" or e.dst.kind == "BOMB":
                continue
            if b.cut_edge(e):
                moved = True
                break
        if b.gc_active > 0:
            pass
        b.update(1 / 60, {"mvx": 0, "mvy": 0, "plan": False, "dash": False})
        if not moved:
            b.slices = 99


def main():
    app = App(fullscreen=False, headless=True)
    check(app.state == "title", "初始在标题")
    app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
    check(app.state == "body", "标题 -> 选身体")
    app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_2))
    check(app.state == "play", "选身体 -> 战斗")
    check(app.run.body["id"] == "array", "选择了数组身体")
    check(app.battle.room_index == 0, "第一关")

    # 打到清关
    b = app.battle
    b.intro_t = 0
    b.state = "playing"
    force_clear(b)
    check(b.state in ("clear", "done"), "第一关清空")
    step(app, 240)
    check(app.state == "reward", "进入奖励界面 state=%s" % app.state)
    check(len(app.reward_options) == 3, "三个奖励选项")
    before = len(app.run.modules)
    app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
    check(len(app.run.modules) == before + 1, "获得模块")
    check(app.state == "play", "进入第二关")
    check(app.run.room_index == 1, "room_index=1")
    check(app.battle.room_index == 1, "battle room=1")
    check(app.battle.body is app.run.body, "身体继承")

    # 暂停
    app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
    check(app.paused, "ESC 暂停")
    app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
    check(not app.paused, "ESC 恢复")

    # 死亡
    app.battle.hp = 0.5
    app.battle.lives = 1
    app.battle.damage_player(99, force=True)
    check(app.battle.state == "dead", "生命归零 -> dead")
    step(app, 140)
    check(app.state == "gameover", "进入 gameover state=%s" % app.state)

    # 胜利
    app.start_run(0)
    app.run.room_index = 8
    app.battle = Battle(app.run, 8)
    app.battle.state = "playing"
    app.battle.intro_t = 0
    app.battle.hp = 9999
    b = app.battle
    for _ in range(60):
        if b.state == "victory":
            break
        for e in list(b.graph.edges):
            if e.alive and e.kind == STRONG or (b.boss_phase == 2 and e.alive):
                if e.kind == "STRONG" and (e.dst.kind == "CORE" or b.boss_phase == 2):
                    b.cut_edge(e)
        b.slices = 99
        b.update(1 / 60, {"mvx": 0, "mvy": 0, "plan": False, "dash": False})
    check(b.state == "victory" or b.boss_phase == 2, "Boss 可以被推进")
    step(app, 200)
    check(app.state == "victory", "胜利界面 state=%s" % app.state)

    print("\nPASS %d / FAIL %d" % (len(OK), len(BAD)))
    return 1 if BAD else 0


sys.exit(main())
