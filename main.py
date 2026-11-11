# -*- coding: utf-8 -*-
"""入口：`python main.py`

主循环只做四件事：收事件、推进、画、刷新。
游戏逻辑全在 core/，这里不写规则。
"""
import sys

import pygame

import config
from ui.app import App


def main():
    pygame.init()
    pygame.display.set_caption("版本控制 3.2 · 原型")
    screen = pygame.display.set_mode((config.WIDTH, config.HEIGHT))
    clock = pygame.time.Clock()

    app = App(screen)
    while app.running:
        dt = min(clock.tick(config.FPS) / 1000.0, 0.05)

        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                app.running = False
            else:
                app.handle(e)

        app.update(dt)
        app.draw()

    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
