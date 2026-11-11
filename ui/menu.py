# -*- coding: utf-8 -*-
"""选人界面：两个角色，点一个开始。"""
import pygame

import config
from data import CHARACTERS, ENGINES, LANGUAGES
from ui import draw, theme

CARD_W, CARD_H = 420, 300


class MenuScreen:
    def __init__(self, app):
        self.app = app
        self.rects = {}
        ids = list(CHARACTERS)
        total = len(ids) * (CARD_W + 40) - 40
        x0 = config.WIDTH // 2 - total // 2
        for i, cid in enumerate(ids):
            self.rects[cid] = pygame.Rect(x0 + i * (CARD_W + 40), 200, CARD_W, CARD_H)

    def handle(self, e):
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            for cid, rect in self.rects.items():
                if rect.collidepoint(e.pos):
                    self.app.start_run(cid)

    def update(self, dt):
        pass

    def draw(self, screen):
        screen.fill(theme.BG)
        draw.text(screen, "版本控制", 52, theme.TEXT, (640, 80), "center", True)
        draw.text(screen, "你打不过任何人。你只能改写历史。", 18, theme.MUTED,
                  (640, 132), "center")

        for cid, rect in self.rects.items():
            ch = CHARACTERS[cid]
            hover = rect.collidepoint(pygame.mouse.get_pos())
            draw.panel(screen, rect, (26, 32, 42) if hover else theme.PANEL,
                       theme.ACCENT if hover else theme.LINE, 12)

            draw.text(screen, ch["name"], 28, theme.TEXT, (rect.centerx, rect.y + 50),
                      "center", True)
            draw.text(screen, ch["desc"], 15, theme.MUTED, (rect.centerx, rect.y + 86),
                      "center")

            lang = LANGUAGES[ch["lang"]]
            eng = ENGINES[ch["engine"]]
            rows = [
                ("语言", f"{lang['name']}  （伤害 ×{lang['atk']:g}，攻速 ×{lang['rate']:g}）"),
                ("引擎", f"{eng['name']}  {eng['desc']}"),
                ("生命", str(ch["hp"])),
                ("移速", str(ch["speed"])),
            ]
            y = rect.y + 130
            for k, v in rows:
                draw.text(screen, k, 15, theme.MUTED, (rect.x + 40, y))
                draw.text(screen, v, 15, theme.TEXT, (rect.x + 110, y))
                y += 34

            draw.text(screen, "点击选择", 14,
                      theme.ACCENT if hover else theme.MUTED,
                      (rect.centerx, rect.bottom - 24), "center")
