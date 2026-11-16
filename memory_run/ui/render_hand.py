# -*- coding: utf-8 -*-
import math
import random
import pygame
from memory_run.const import *
from memory_run.core.model import STRONG, WEAK, DANGLING
from memory_run.core.cards import CARD_DEFS, SHAPE_NAMES, RARITY_CN
from memory_run.content import GIRLS
from memory_run.ui.fx import ScreenPost, draw_rings, draw_sparks, draw_floaters
from .render_common import *

class HandMixin:
    def draw_hand(self, screen, b):
        y = 798
        h = 84
        # 5 槽
        for i in range(5):
            rect = pygame.Rect(20 + i * 158, y, 150, h)
            card = b.hand.slots[i]
            selected = bool(b.aim and b.aim.get("card") is card)
            self.draw_slot(screen, rect, card, selected, i, "slot")
        # 备用
        rect = pygame.Rect(820, y + 14, 74, h - 28)
        card = b.hand.reserve[0] if b.hand.reserve else None
        self.draw_slot(screen, rect, card, bool(b.aim and b.aim.get("card") is card),
                       None, "reserve")
        blit_text(screen, "备用", (rect.centerx, rect.bottom + 3), 9, DIM,
                  anchor="midtop")
        # 溢出
        rect = pygame.Rect(906, y + 14, 74, h - 28)
        card = next((c for c in b.hand.overflow if c), None)
        self.draw_slot(screen, rect, card, bool(b.aim and b.aim.get("card") is card),
                       None, "overflow")
        blit_text(screen, "溢出", (rect.centerx, rect.bottom + 3), 9,
                  RED if card else DIM, anchor="midtop")
        # 垃圾桶
        rect = pygame.Rect(992, y + 14, 60, h - 28)
        panel(screen, rect, (16, 12, 16), (60, 34, 42), 5)
        blit_text(screen, "弃", (rect.centerx, rect.centery - 8), 18, RED,
                  bold=True, anchor="center")
        blit_text(screen, "X", (rect.centerx, rect.centery + 13), 11, DIM,
                  mono=True, anchor="center")
        # 计时 / 抽牌
        blit_text(screen, "DRAW", (1070, y + 6), 9, DIM, mono=True)
        bar(screen, pygame.Rect(1070, y + 20, 120, 7),
            1 - b.draw_timer / 3.5, CYAN)
        blit_text(screen, f"{b.draw_timer:.1f}s", (1196, y + 16), 11,
                  DIM, mono=True)
        blit_text(screen, f"牌堆 {len(b.pile)}  ·  已用 {len(b.used)}",
                  (1070, y + 34), 11, DIM)
        # 级联
        blit_text(screen, f"CASCADE x{b.erase_streak}", (1070, y + 52), 15,
                  GREEN if b.erase_streak else DIM, mono=True)
        # 焦点
        blit_text(screen, "FOCUS", (1270, y + 6), 9, DIM, mono=True)
        bar(screen, pygame.Rect(1270, y + 20, 90, 7), b.focus / b.focus_max, PURPLE)
        # 槽编号
        blit_text(screen, "按住卡拖到目标，松手使用", (1490, y + 8), 10, DIM,
                  anchor="topright", mono=True)
        blit_text(screen, f"HP {int(b.hp)}  REF {b.run.refs}", (1490, y + 26), 12,
                  WHITE, anchor="topright", mono=True)
        blit_text(screen, "右键 WRITE · 左键目标", (1490, y + 44), 10, DIM2,
                  anchor="topright")

    def draw_slot(self, screen, rect, card, selected, idx, where):
        hover = bool(card) and rect.collidepoint(pygame.mouse.get_pos())
        pygame.draw.rect(screen, (17, 22, 31) if hover else (12, 15, 22),
                         rect, border_radius=6)
        border = PANEL_LINE
        if selected:
            border = GOLD
        elif card:
            border = dim(card.color, 0.8)
        pygame.draw.rect(screen, border, rect, 2 if selected or hover else 1,
                         border_radius=6)
        if selected or hover:
            glow(screen, rect.centerx, rect.centery, rect.w * 0.62,
                 card.color if card else border, 0.18)
        if idx is not None:
            blit_text(screen, str(idx + 1), (rect.x + 6, rect.y + 4), 10,
                      WHITE if hover else DIM, mono=True)
        if card:
            # 小卡面
            icon = pygame.Rect(rect.x + 8, rect.y + 18, 40, 40)
            draw_card_mini(screen, icon, card.key, card.up)
            blit_text(screen, card.name, (rect.x + 54, rect.y + 14), 14,
                      GOLD if card.up else WHITE, bold=True)
            blit_text(screen, CARD_DEFS[card.key]["en"], (rect.x + 54, rect.y + 33),
                      8, dim(card.color, 0.9), mono=True)
            tag = {"edge": "划边", "two": "双目标", "node": "点对象",
                   "area": "区域", "self": "自身", "dead": "修复"}[card.d["target"]]
            blit_text(screen, tag, (rect.x + 54, rect.y + 54), 10, DIM)
            if selected:
                glow(screen, rect.centerx, rect.centery, rect.w * 0.65,
                     card.color, 0.3)
        else:
            blit_text(screen, "EMPTY", (rect.centerx, rect.centery), 11,
                      (36, 46, 58), mono=True, anchor="center")
        self.hand_rects.append((rect, (where, idx), card))

    def draw_banner(self, screen, b):
        if b.banner_t > 0 and b.banner:
            a = int(255 * min(1.0, b.banner_t / 0.5))
            draw_center(screen, b.banner, W // 2, 180, 26, WHITE, a)
        if b.toast_t > 0 and b.toast_msg and b.state in ("playing", "intro"):
            y = ARENA.bottom - 58
            box = pygame.Rect(W // 2 - 420, y, 840, 42)
            panel(screen, box, (8, 12, 18), (36, 52, 66), 5, alpha=210)
            blit_text(screen, b.toast_msg, (W // 2, y + 21), 15, WHITE,
                      anchor="center")
        if b.state == "clear":
            draw_center(screen, "ROOM CLEARED", W // 2, 300, 52, GREEN, 240,
                        bold=True)
            if b.result:
                draw_center(screen, f"SCORE {b.result.get('score', 0)}   "
                                    f"PERFECT" if False else
                            f"SCORE {b.result.get('score', 0)}", W // 2, 356,
                            18, WHITE, 220)
        if b.state == "dead":
            draw_center(screen, "SEGFAULT", W // 2, 300, 56, RED, 240, bold=True)
            draw_center(screen, "引用还在，进程没了。", W // 2, 360, 18, DIM, 220)

    def draw_intro(self, screen, b):
        a = int(255 * min(1.0, b.intro_t / 0.4))
        box = pygame.Rect(W // 2 - 400, 210, 800, 250)
        panel(screen, box, (8, 11, 17), (40, 56, 72), 8, alpha=235)
        draw_center(screen, b.room["title"], W // 2, 250, 38, WHITE, a, bold=True)
        draw_center(screen, b.room.get("cn", ""), W // 2, 300, 20, DIM, a)
        y = 340
        for line in wrap(b.room.get("hint", ""), 16, 700)[:3]:
            blit_text(screen, line, (W // 2, y), 16, WHITE, anchor="midtop",
                      alpha=a)
            y += 24
        draw_center(screen, "即将开始", W // 2, 430, 12, DIM2, a, mono=True)


def draw_center(screen, s, x, y, size, color, alpha=255, bold=False, mono=False):
    blit_text(screen, s, (x, y), size, color, bold=bold, mono=mono,
              anchor="center", alpha=alpha, shadow=2)


def dashed_circle(surf, color, cx, cy, r, dash=5, gap=4, width=2, alpha=255):
    n = max(8, int(math.tau * r / (dash + gap)))
    for i in range(n):
        a0 = i * math.tau / n
        a1 = a0 + (math.tau / n) * dash / (dash + gap)
        p0 = (cx + math.cos(a0) * r, cy + math.sin(a0) * r)
        p1 = (cx + math.cos(a1) * r, cy + math.sin(a1) * r)
        pygame.draw.line(surf, with_alpha(color, alpha), p0, p1, width)
