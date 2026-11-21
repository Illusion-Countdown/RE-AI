# -*- coding: utf-8 -*-
"""无头流程测试：教程、12 场战斗、奖励、模块、Boss 规则、安全屋、结局。"""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame

from memory_run.app import App
from memory_run.content import TUTORIAL_COUNT


def tick(app, n=1, dt=1 / 60):
    for _ in range(n):
        app.update(dt)


def clear_battle(app):
    b = app.battle
    b.state = "playing"
    b.intro_t = 0
    for n in list(b.graph.nodes):
        if n.alive and n.hostile:
            b.kill_node(n, source="test")
    b.state = "playing"
    b.check_clear()
    for _ in range(200):
        app.update(1 / 60)
        if app.state != "battle":
            break


def test_tutorial(app):
    app.new_run(True)
    assert app.state == "deck"
    app.deck_start()
    for step in range(TUTORIAL_COUNT):
        assert app.state == "battle", (step, app.state)
        clear_battle(app)
        assert app.state == "tutorial_clear", (step, app.state)
        app.tutorial_next()
        if step < TUTORIAL_COUNT - 1:
            assert app.state == "battle"
    assert app.state == "tutorial_end", app.state
    app.enter_main_run()
    assert app.state == "deck"
    print("tutorial ok, step", app.run.step)


def test_main(app):
    app.state = "title"
    app.new_run(False)
    app.deck_start()
    guard = 0
    while app.run.room is not None and guard < 30:
        guard += 1
        assert app.state == "battle", (app.run.step, app.state)
        room = app.run.room
        clear_battle(app)
        if app.state == "reward":
            app.choose_card(0)
        if app.state == "module":
            app.choose_module(0)
        if app.state == "rule":
            app.choose_rule(0)
        if app.state == "deck":
            # 奖励后整备：自动整理，继续
            app.editor.auto_arrange()
            app.deck_start()
        if app.state == "battle":
            continue
    assert app.state == "end", app.state
    assert app.run.victory, app.run.step
    print("main ok, rooms", app.run.rooms_cleared, "score", app.run.score,
          "modules", [m["id"] for m in app.run.modules])


def main():
    app = App(fullscreen=False, headless=True)
    test_tutorial(app)
    test_main(app)
    print("FLOW OK")


if __name__ == "__main__":
    main()
