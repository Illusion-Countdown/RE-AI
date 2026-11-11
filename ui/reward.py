# -*- coding: utf-8 -*-
"""节点奖励：三选一。"""
import pygame

import config
from core.state import card_shape
from data import CARDS
from ui import draw, theme

CARD_W, CARD_H = 240, 260


class RewardScreen:
    def __init__(self, app, choices):
        self.app = app
        self.choices = choices
        self.rects = {}
        total = len(choices) * (CARD_W + 30) - 30
        x0 = config.WIDTH // 2 - total // 2
        for i, cid in enumerate(choices):
            self.rects[cid] = pygame.Rect(x0 + i * (CARD_W + 30), 220, CARD_W, CARD_H)

    def handle(self, e):
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            for cid, rect in self.rects.items():
                if rect.collidepoint(e.pos):
                    self.app.take_card(cid)

    def update(self, dt):
        pass

    def draw(self, screen):
        screen.fill(theme.BG)
        draw.text(screen, "选择一张算法卡", 30, theme.TEXT, (640, 100), "center", True)
        draw.text(screen, "放进内存才会成为你的牌库", 15, theme.MUTED,
                  (640, 140), "center")

        for cid, rect in self.rects.items():
            card = CARDS[cid]
            hover = rect.collidepoint(pygame.mouse.get_pos())
            draw.panel(screen, rect, (40, 36, 22) if hover else (26, 24, 18),
                       theme.CARD if hover else (90, 76, 40), 12)

            draw.text(screen, card["name"], 24, theme.CARD,
                      (rect.centerx, rect.y + 48), "center", True)
            draw.text(screen, f"{card['cells']} 格", 16, theme.MUTED,
                      (rect.centerx, rect.y + 84), "center")
            draw.text(screen, f"CD {card['cd']:g}s", 16, theme.MUTED,
                      (rect.centerx, rect.y + 108), "center")

            desc = card["desc"]
            f = theme.font(14)
            line, y = "", rect.y + 146
            for ch in desc:
                if f.size(line + ch)[0] > rect.w - 40:
                    draw.text(screen, line, 14, theme.TEXT,
                              (rect.centerx, y), "center")
                    line, y = ch, y + 22
                else:
                    line += ch
            if line:
                draw.text(screen, line, 14, theme.TEXT, (rect.centerx, y), "center")

            draw.text(screen, "点击选择", 13,
                      theme.ACCENT if hover else theme.MUTED,
                      (rect.centerx, rect.bottom - 20), "center")
