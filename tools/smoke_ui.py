# -*- coding: utf-8 -*-
"""界面冒烟测试：无窗口跑一遍所有场景，确保不崩。

    python tools/smoke_ui.py
"""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame

pygame.init()
screen = pygame.display.set_mode((1280, 720))

from ui.app import App  # noqa: E402


def step(app, frames=1, dt=1 / 60):
    for _ in range(frames):
        app.update(dt)
        app.draw()


def main():
    app = App(screen)
    step(app, 3)
    print("menu ok")

    app.start_run("deepquest")
    step(app, 3)
    print("map ok")

    # 直接推进到第一个战斗节点
    err = app.state.map.advance("c1")
    app.enter_node()
    step(app, 120)          # 跑 2 秒战斗
    print("battle ok  敌人数:", len(app.state.enemies),
          " 手牌:", len(app.state.hand))

    # 模拟拖卡：拿第一张卡，直接 cast
    if app.state.hand:
        from core import cards
        cards.cast(app.state, app.state.hand[0])
        step(app, 5)
        print("cast ok")

    # 结算
    app.goto_result(True)
    step(app, 3)
    print("result ok")

    app.back_to_menu()
    step(app, 3)
    print("all scenes ok")
    pygame.quit()


if __name__ == "__main__":
    main()
