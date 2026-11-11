# -*- coding: utf-8 -*-
"""把四个场景各渲染一帧存成 PNG，用来检查布局。

    python tools/shots.py
"""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame

pygame.init()
screen = pygame.display.set_mode((1280, 720))

from core import battle, cards  # noqa: E402
from ui.app import App  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "shots")


def shot(app, name):
    app.draw()
    os.makedirs(OUT, exist_ok=True)
    pygame.image.save(screen, os.path.join(OUT, name))
    print("saved", name)


def main():
    app = App(screen)

    # 1 菜单
    for _ in range(2):
        app.update(1 / 60)
    shot(app, "01-menu.png")

    # 2 地图
    app.start_run("deepquest")
    for _ in range(2):
        app.update(1 / 60)
    shot(app, "02-map.png")

    # 3 战斗
    app.state.map.advance("c1")
    app.enter_node()
    st = app.state
    for i in range(600):                     # 跑 10 秒
        app.update(1 / 60)
    for kind in ("bug", "bug", "beast"):
        battle.spawn_enemy(st, kind)
    while len(st.hand) < 4:
        if not cards.draw_one(st):
            break
    for _ in range(2):
        app.update(1 / 60)
    shot(app, "03-battle.png")

    # 4 奖励
    app.goto_reward()
    for _ in range(2):
        app.update(1 / 60)
    shot(app, "04-reward.png")

    # 5 结算
    app.goto_result(True)
    for _ in range(2):
        app.update(1 / 60)
    shot(app, "05-result.png")

    pygame.quit()


if __name__ == "__main__":
    main()
