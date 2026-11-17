# -*- coding: utf-8 -*-
"""内存远征 · 装配 + 战斗入口 (pixel UI, 8x8 grid, warehouse, F5 start battle)."""

from __future__ import annotations

import math
import os
import sys
from dataclasses import dataclass

import pygame

from audio import UIAudio
from cards import BY_KEY, CARDS, CATEGORIES, RARITY, RARITY_COLORS, bbox, rotate

W, H = 1280, 720
CELL = 46
GRID_X, GRID_Y = 44, 154
GRID = pygame.Rect(GRID_X, GRID_Y, CELL * 8, CELL * 8)
LEFT = pygame.Rect(12, 64, 536, 636)
RIGHT = pygame.Rect(560, 64, 708, 636)

CARD_W, CARD_H = 196, 228
CARD_GAP = 12
CARD_X = 578
CARD_Y = 132
VIEW_BOTTOM = 640

INK = (7, 11, 17)
PANEL = (13, 20, 29)
PANEL2 = (17, 26, 37)
GRID_BG = (18, 28, 40)
LINE = (38, 56, 72)
TEXT = (222, 238, 248)
MUTED = (119, 143, 160)
DIM = (71, 91, 108)
GREEN = (114, 230, 160)
RED = (255, 92, 105)

TABS = [("ALL", "全部", None), ("CUT", "断链", "CUT"), ("REF", "引用", "REF"),
        ("TYPE", "类型", "TYPE"), ("MEM", "内存", "MEM")]

# 首战推荐：8 张主动技能，无重叠，占用 37/64，首战 Fidelity Cap ≈ 71
RECOMMENDED_DECK = [
    ("CUT", 2, 6, 0),
    ("CLIP", 2, 3, 0),
    ("SWEEP", 4, 2, 0),
    ("WEAK", 0, 1, 0),
    ("TRUNC", 0, 3, 0),
    ("ECC", 0, 0, 0),
    ("EDGE", 4, 5, 0),
    ("RECLAIM", 0, 6, 0),
    ("OVERCLOCK", 3, 0, 0),
]


@dataclass
class Placed:
    uid: int
    key: str
    row: int
    col: int
    rot: int
    damaged: bool = False

    @property
    def d(self):
        return BY_KEY[self.key]

    def cells(self):
        return [(self.row + r, self.col + c) for r, c in rotate(self.d["cells"], self.rot)]


class App:
    def __init__(self, windowed=False, shot=None, size=None):
        pygame.init()
        self.audio = UIAudio()
        self.windowed = windowed
        self.shot = shot
        self.size = size
        self.window = None
        self.view_rect = pygame.Rect(0, 0, W, H)
        self._set_window()

        self.canvas = pygame.Surface((W, H)).convert()
        self.clock = pygame.time.Clock()
        self.font20 = self._font(20)
        self.font18 = self._font(18)
        self.font16 = self._font(16)
        self.font14 = self._font(14)
        self.font12 = self._font(12)
        self.font11 = self._font(11)
        self.font24 = self._font(24, bold=True)
        self.font28 = self._font(28, bold=True)
        self.mono12 = self._mono(12)
        self.mono10 = self._mono(10)

        self.counts = {c["key"]: 10 for c in CARDS}
        self.placed: dict[int, Placed] = {}
        self.layers: dict[tuple[int, int], list[int]] = {}
        self.necro: set[tuple[int, int]] = set()
        self.next_uid = 1
        self.overlap_cap = 3
        self.tool = "select"
        self.drag = None
        self.detail_key = None
        self.detail_rect = None
        self.detail_close = None
        self.tab = "ALL"
        self.scroll = 0
        self.max_scroll = 0
        self.mouse = (0, 0)
        self.hover_key = None
        self.flash = 0.0
        self.shake = 0.0
        self.time = 0.0
        self.start_rect = pygame.Rect(W - 210, 7, 194, 40)
        self.recommended_rect = pygame.Rect(W - 420, 7, 190, 40)
        self.start_requested = False
        self.message = ""
        self.message_t = 0.0
        self.last_result = None

        # hit zones rebuilt while drawing
        self.card_hits = []
        self.tab_hits = []
        self.tool_hits = []
        self.expand_hits = []
        self.reset_hit = None
        self.panel_rects = []

    # ------------------------------------------------------------ window
    def _set_window(self):
        if self.windowed:
            size = self.size or (W, H)
            self.window = pygame.display.set_mode(size)
        else:
            self.window = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        pygame.display.set_caption("内存远征 · 装配台")
        self._update_view()

    def _update_view(self):
        ww, wh = self.window.get_size()
        scale = min(ww / W, wh / H)
        if not self.windowed:
            scale = max(0.5, scale)
        dw, dh = int(W * scale), int(H * scale)
        self.view_rect = pygame.Rect((ww - dw) // 2, (wh - dh) // 2, dw, dh)
        self.scale = scale
        self.offset = self.view_rect.topleft

    def to_logical(self, pos):
        x = (pos[0] - self.view_rect.x) / max(0.001, self.view_rect.w / W)
        y = (pos[1] - self.view_rect.y) / max(0.001, self.view_rect.h / H)
        return int(x), int(y)

    def present(self):
        self.canvas.fill(INK)
        self.draw()
        if self.view_rect.w != W or self.view_rect.h != H:
            frame = pygame.transform.scale(self.canvas, self.view_rect.size)
        else:
            frame = self.canvas
        self.window.fill((0, 0, 0))
        self.window.blit(frame, self.view_rect.topleft)
        pygame.display.flip()

    # ------------------------------------------------------------ fonts
    def _font(self, size, bold=False):
        try:
            path = r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc"
            return pygame.font.Font(path, size)
        except Exception:
            return pygame.font.Font(None, size)

    def _mono(self, size):
        try:
            return pygame.font.Font(r"C:\Windows\Fonts\consola.ttf", size)
        except Exception:
            return pygame.font.Font(None, size)

    def text(self, surf, s, pos, col=TEXT, font=None, center=False):
        f = font or self.font16
        img = f.render(str(s), False, col)
        r = img.get_rect()
        if center:
            r.center = pos
        else:
            r.topleft = pos
        surf.blit(img, r)
        return r

    # ------------------------------------------------------------ graph state
    def overlap_cells(self):
        return sum(1 for v in self.layers.values() if len(v) >= 2)

    def load_cells(self):
        return len(self.layers)

    def free_cells(self):
        return 64 - len(set(self.layers) | self.necro)

    def quality(self):
        used = len(set(self.layers) | self.necro)
        return max(0, min(100, round(100 - 50 * used / 64)))

    def battle_loadout(self):
        return {
            "cards": [
                {"uid": p.uid, "key": p.key, "cells": p.cells(), "damaged": p.damaged,
                 "kind": BY_KEY[p.key].get("kind", "active")}
                for p in sorted(self.placed.values(), key=lambda q: q.uid)
            ],
            "necro": [list(c) for c in sorted(self.necro)],
        }

    def apply_recommended_deck(self):
        # Validate the preset against the current necrosed board before replacing anything.
        for key, row, col, rot in RECOMMENDED_DECK:
            cells = [(row + r, col + c) for r, c in rotate(BY_KEY[key]["cells"], rot)]
            for rr, cc in cells:
                if not (0 <= rr < 8 and 0 <= cc < 8) or (rr, cc) in self.necro:
                    self.message = "推荐布局被坏死格阻挡，请先清理坏死"
                    self.message_t = 2.5
                    self.audio.play("invalid")
                    return
        self.placed.clear()
        self.layers.clear()
        self.counts = {c["key"]: 10 for c in CARDS}
        self.next_uid = 1
        self.drag = None
        self.close_detail()
        for key, row, col, rot in RECOMMENDED_DECK:
            p = self.add_placed(key, row, col, rot)
            if p:
                self.counts[key] = max(0, self.counts.get(key, 0) - 1)
        self.message = f"已换上推荐牌组 · {len(RECOMMENDED_DECK)} 张 · 保真上限 {self.quality()}"
        self.message_t = 3.0
        self.audio.play("place")

    def start_battle(self):
        active = [p for p in self.placed.values() if not p.damaged]
        if not active:
            self.message = "至少放置一张未损坏的技能牌"
            self.message_t = 2.0
            self.audio.play("invalid")
            return
        snapshot = self.battle_loadout()
        try:
            from battle_demo import Battle
            battle = Battle(
                windowed=self.windowed,
                size=self.size if self.windowed else None,
                loadout=snapshot,
                embedded=True,
            )
            result = battle.run()
        except Exception as exc:
            self.message = f"战斗启动失败：{exc}"
            self.message_t = 4.0
            self.audio.play("invalid")
            return
        finally:
            self._set_window()
            self.audio = UIAudio()
        if result:
            self.last_result = result
            self.necro |= {tuple(c) for c in result.get("necro", [])}
            damaged = set(result.get("damaged", []))
            for p in self.placed.values():
                if p.uid in damaged:
                    p.damaged = True
            self.message = "战斗胜利 · 损坏与坏死已写回装配" if result.get("won") else "战斗结束 · 损坏与坏死已写回装配"
            self.message_t = 3.0
        self._set_window()
        self.present()

    def top_card(self, cell):
        layers = self.layers.get(cell)
        if not layers:
            return None
        return self.placed.get(layers[-1])

    def add_placed(self, key, row, col, rot):
        defn = BY_KEY[key]
        cells = [(row + r, col + c) for r, c in rotate(defn["cells"], rot)]
        for rr, cc in cells:
            if not (0 <= rr < 8 and 0 <= cc < 8):
                return None
            if (rr, cc) in self.necro:
                return None
            if len(self.layers.get((rr, cc), [])) >= 2:
                return None
        new_overlap = sum(1 for c in cells if len(self.layers.get(c, [])) == 1)
        if self.overlap_cells() + new_overlap > self.overlap_cap:
            return None
        p = Placed(self.next_uid, key, row, col, rot)
        self.next_uid += 1
        self.placed[p.uid] = p
        for c in cells:
            self.layers.setdefault(c, []).append(p.uid)
        return p

    def remove_placed(self, p, give_back=True):
        for c in p.cells():
            arr = self.layers.get(c)
            if arr and p.uid in arr:
                arr.remove(p.uid)
                if not arr:
                    del self.layers[c]
        self.placed.pop(p.uid, None)
        if give_back:
            self.counts[p.key] = self.counts.get(p.key, 0) + 1

    def restore(self, p):
        self.placed[p.uid] = p
        for c in p.cells():
            self.layers.setdefault(c, []).append(p.uid)

    def can_place(self, key, row, col, rot):
        defn = BY_KEY[key]
        cells = [(row + r, col + c) for r, c in rotate(defn["cells"], rot)]
        for rr, cc in cells:
            if not (0 <= rr < 8 and 0 <= cc < 8):
                return False
            if (rr, cc) in self.necro:
                return False
            if len(self.layers.get((rr, cc), [])) >= 2:
                return False
        new_overlap = sum(1 for c in cells if len(self.layers.get(c, [])) == 1)
        return self.overlap_cells() + new_overlap <= self.overlap_cap

    def drag_anchor(self, key, rot):
        d = BY_KEY[key]
        cells = rotate(d["cells"], rot)
        h, w = bbox(cells)
        gx = (self.mouse[0] - GRID_X) // CELL
        gy = (self.mouse[1] - GRID_Y) // CELL
        return int(gy - h // 2), int(gx - w // 2)

    # ------------------------------------------------------------ drawing helpers
    def px(self, surf, rect, fill=None, border=None, width=2):
        if fill:
            pygame.draw.rect(surf, fill, rect)
        if border:
            pygame.draw.rect(surf, border, rect, width)

    def icon(self, surf, cat, x, y, size=22):
        c = CATEGORIES[cat]["color"]
        s = size
        if cat == "CUT":
            pygame.draw.line(surf, c, (x + 3, y + 3), (x + s - 4, y + s - 4), 2)
            pygame.draw.line(surf, c, (x + s - 4, y + 3), (x + 3, y + s - 4), 2)
            pygame.draw.circle(surf, c, (x + 3, y + 3), 2)
            pygame.draw.circle(surf, c, (x + s - 4, y + 3), 2)
        elif cat == "REF":
            r1 = pygame.Rect(x + 2, y + 4, s - 7, s - 10)
            r2 = pygame.Rect(x + 6, y + 8, s - 7, s - 10)
            pygame.draw.rect(surf, c, r1, 2)
            pygame.draw.rect(surf, c, r2, 2)
        elif cat == "TYPE":
            pygame.draw.line(surf, c, (x + 8, y + 3), (x + 3, y + s // 2), 2)
            pygame.draw.line(surf, c, (x + 3, y + s // 2), (x + 8, y + s - 3), 2)
            pygame.draw.line(surf, c, (x + s - 8, y + 3), (x + s - 3, y + s // 2), 2)
            pygame.draw.line(surf, c, (x + s - 3, y + s // 2), (x + s - 8, y + s - 3), 2)
            pygame.draw.rect(surf, c, (x + s // 2 - 1, y + s // 2 - 1, 2, 2))
        else:
            r = pygame.Rect(x + 4, y + 4, s - 8, s - 8)
            pygame.draw.rect(surf, c, r, 2)
            pygame.draw.rect(surf, c, (x + 8, y + 8, s - 16, s - 16), 1)
            for i in range(3):
                yy = y + 6 + i * 4
                pygame.draw.line(surf, c, (x + 1, yy), (x + 3, yy), 1)
                pygame.draw.line(surf, c, (x + s - 3, yy), (x + s - 1, yy), 1)

    def shape_preview(self, surf, cells, cx, cy, cell=16, color=None, empty=True):
        if not cells:
            return
        if color is None:
            color = (80, 214, 255)
        h, w = bbox(cells)
        ox = cx - w * cell // 2
        oy = cy - h * cell // 2
        if empty:
            for r in range(3):
                for c in range(3):
                    rr = pygame.Rect(ox + c * cell, oy + r * cell, cell - 1, cell - 1)
                    pygame.draw.rect(surf, (20, 29, 40), rr)
                    pygame.draw.rect(surf, (31, 44, 57), rr, 1)
        for r, c in cells:
            rr = pygame.Rect(ox + c * cell, oy + r * cell, cell - 1, cell - 1)
            pygame.draw.rect(surf, color, rr)
            pygame.draw.rect(surf, (235, 250, 255), rr, 1)

    def shape_preview_fit(self, surf, cells, rect, color=None):
        cell = min(rect.w // 3, rect.h // 3)
        self.shape_preview(surf, cells, rect.centerx, rect.centery, max(8, cell), color, True)

    def wrap(self, s, font, width):
        lines = []
        cur = ""
        for ch in s:
            if font.size(cur + ch)[0] > width and cur:
                lines.append(cur)
                cur = ch
            else:
                cur += ch
        if cur:
            lines.append(cur)
        return lines

    # ------------------------------------------------------------ draw
    def _draw_placed_block(self, s, p):
        cells = set(p.cells())
        col = CATEGORIES[p.d["cat"]]["color"]
        dark = CATEGORIES[p.d["cat"]]["dim"]
        if p.damaged:
            col = (255, 92, 105)
            dark = (58, 18, 25)
        # a dark silhouette around every card keeps same-colour cards apart
        for r, c in cells:
            rr = pygame.Rect(GRID_X + c * CELL, GRID_Y + r * CELL, CELL, CELL)
            pygame.draw.rect(s, (3, 6, 10), (rr.x - 3, rr.y - 3, CELL + 6, CELL + 6))
        for r, c in cells:
            rr = pygame.Rect(GRID_X + c * CELL, GRID_Y + r * CELL, CELL, CELL)
            pygame.draw.rect(s, dark, (rr.x + 2, rr.y + 2, CELL - 4, CELL - 4))
            pygame.draw.rect(s, (233, 249, 255), (rr.x + 7, rr.y + 7, 3, 3))
            for dr, dc, edge in (
                (-1, 0, "top"), (1, 0, "bottom"), (0, -1, "left"), (0, 1, "right")
            ):
                nb = (r + dr, c + dc)
                if nb in cells:
                    # internal seam: the card is one object, but its cells remain readable
                    if edge == "bottom":
                        pygame.draw.line(s, (4, 8, 12), (rr.x + 2, rr.bottom - 2), (rr.right - 2, rr.bottom - 2), 2)
                    elif edge == "right":
                        pygame.draw.line(s, (4, 8, 12), (rr.right - 2, rr.y + 2), (rr.right - 2, rr.bottom - 2), 2)
                else:
                    if edge == "top":
                        pygame.draw.line(s, col, (rr.x, rr.y), (rr.right, rr.y), 3)
                    elif edge == "bottom":
                        pygame.draw.line(s, col, (rr.x, rr.bottom - 1), (rr.right, rr.bottom - 1), 3)
                    elif edge == "left":
                        pygame.draw.line(s, col, (rr.x, rr.y), (rr.x, rr.bottom), 3)
                    else:
                        pygame.draw.line(s, col, (rr.right - 1, rr.y), (rr.right - 1, rr.bottom), 3)

    def _draw_placed_labels(self, s):
        used = []
        for p in sorted(self.placed.values(), key=lambda q: q.uid):
            cells = sorted(p.cells())
            if not cells:
                continue
            r0, c0 = cells[0]
            x0 = GRID_X + c0 * CELL
            y0 = GRID_Y + r0 * CELL
            max_r = max(r for r, c in cells)
            max_c = max(c for r, c in cells)
            label = p.d["cn"] + (" · BROKEN" if p.damaged else "")
            lw = self.font11.size(label)[0] + 10
            lh = 16
            candidates = [
                (x0 + 3, y0 + 3),
                (x0 + 3, y0 - lh - 3),
                (x0 + 3, GRID_Y + (max_r + 1) * CELL + 3),
                (GRID_X + (max_c + 1) * CELL + 3, y0 + 3),
            ]
            chosen = None
            for cx, cy in candidates:
                cx = max(GRID.x + 2, min(GRID.right - lw - 2, cx))
                cy = max(GRID.y + 2, min(GRID.bottom - lh - 2, cy))
                rr = pygame.Rect(cx, cy, lw, lh)
                if not any(rr.colliderect(u) for u in used):
                    chosen = rr
                    break
            if chosen is None:
                chosen = pygame.Rect(
                    max(GRID.x + 2, min(GRID.right - lw - 2, x0 + 3)),
                    max(GRID.y + 2, min(GRID.bottom - lh - 2, y0 + 3)),
                    lw, lh,
                )
            used.append(chosen)
            pygame.draw.rect(s, (4, 8, 13), (chosen.x + 1, chosen.y + 1, chosen.w, chosen.h))
            pygame.draw.rect(s, (8, 13, 19), chosen)
            pygame.draw.rect(s, RED if p.damaged else CATEGORIES[p.d["cat"]]["color"], chosen, 1)
            self.text(s, label, (chosen.x + 5, chosen.y + 2),
                      (255, 220, 220) if p.damaged else (238, 250, 255), self.font11)

    def draw(self):
        s = self.canvas
        self.time += 1 / 60
        self.message_t = max(0.0, self.message_t - 1 / 60)
        s.fill(INK)
        # pixel background
        for x in range(0, W, 16):
            pygame.draw.line(s, (10, 16, 23), (x, 0), (x, H))
        for y in range(0, H, 16):
            pygame.draw.line(s, (10, 16, 23), (0, y), (W, y))
        # header
        pygame.draw.rect(s, (9, 14, 21), (0, 0, W, 52))
        pygame.draw.line(s, LINE, (0, 52), (W, 52), 1)
        self.draw_ai(s, 16, 8, 36)
        self.text(s, "内存远征 · 装配台", (64, 7), TEXT, self.font24)
        self.text(s, "MEMORY ASSEMBLY // PIXEL BUILD 0.1", (66, 34), MUTED, self.mono10)
        self.text(s, "仓库：无限", (520, 8), GREEN, self.font14)
        self.text(s, "先装配，再进入战斗", (520, 30), DIM, self.font11)
        # recommended deck
        pygame.draw.rect(s, (34, 29, 15), self.recommended_rect)
        pygame.draw.rect(s, (255, 205, 100), self.recommended_rect, 2)
        self.text(s, "推荐牌组", (self.recommended_rect.centerx, self.recommended_rect.centery - 7),
                  (255, 220, 120), self.font16, center=True)
        self.text(s, "第一次玩不知道怎么选可以点这个",
                  (self.recommended_rect.centerx, self.recommended_rect.centery + 10),
                  (185, 160, 105), self.font11, center=True)
        active = sum(1 for p in self.placed.values() if not p.damaged)
        pygame.draw.rect(s, (17, 38, 30) if active else (30, 20, 24), self.start_rect)
        pygame.draw.rect(s, GREEN if active else (95, 52, 58), self.start_rect, 2)
        self.text(s, "开始战斗", (self.start_rect.centerx, self.start_rect.centery - 7),
                  (170, 255, 210) if active else (120, 80, 86), self.font16, center=True)
        self.text(s, f"F5  ·  {active} 张可用", (self.start_rect.centerx, self.start_rect.centery + 10),
                  (90, 150, 118) if active else (95, 65, 70), self.mono10, center=True)

        # left panel
        self.px(s, LEFT, PANEL, LINE, 1)
        self.text(s, "装配台", (26, 76), TEXT, self.font18)
        self.text(s, "8 × 8 / FIXED", (110, 80), MUTED, self.mono10)
        self.text(s, "无自动整理", (LEFT.right - 100, 80), DIM, self.mono10)

        # stats
        sx = 26
        labels = [
            ("负载", f"{self.load_cells()}/64", CATEGORIES["CUT"]["color"]),
            ("空闲", str(self.free_cells()), GREEN),
            ("重叠格", f"{self.overlap_cells()}/{self.overlap_cap}", CATEGORIES["REF"]["color"]),
            ("保真上限", str(self.quality()), CATEGORIES["TYPE"]["color"]),
            ("坏死", str(len(self.necro)), RED),
        ]
        x = 26
        for label, val, col in labels:
            self.text(s, label, (x, 104), DIM, self.font11)
            self.text(s, val, (x, 119), col, self.font18)
            x += 100
        # fidelity cap bar
        qr = pygame.Rect(26, 145, 504, 4)
        pygame.draw.rect(s, (28, 40, 54), qr)
        pygame.draw.rect(s, CATEGORIES["TYPE"]["color"], (qr.x, qr.y, int(qr.w * self.quality() / 100), qr.h))

        # grid
        pygame.draw.rect(s, (10, 17, 25), GRID.inflate(8, 8))
        for r in range(8):
            for c in range(8):
                cell = (r, c)
                rr = pygame.Rect(GRID_X + c * CELL, GRID_Y + r * CELL, CELL, CELL)
                base = GRID_BG if (r + c) % 2 == 0 else (16, 25, 36)
                pygame.draw.rect(s, base, rr)
                pygame.draw.rect(s, (28, 41, 54), rr, 1)
                if cell in self.necro:
                    pygame.draw.rect(s, (52, 18, 26), rr)
                    pygame.draw.line(s, (190, 55, 68), (rr.x + 10, rr.y + 10), (rr.right - 10, rr.bottom - 10), 2)
                    pygame.draw.line(s, (190, 55, 68), (rr.right - 10, rr.y + 10), (rr.x + 10, rr.bottom - 10), 2)
        if not self.placed and not self.drag and not self.necro:
            self.text(s, "拖拽右侧卡牌到这里", (GRID.centerx, GRID.centery - 8), (54, 76, 94), self.font18, center=True)
            self.text(s, "8 × 8  ·  手动装配  ·  无自动整理", (GRID.centerx, GRID.centery + 20), (42, 60, 75), self.font11, center=True)

        # draw placed cards, bottom-up
        for p in sorted(self.placed.values(), key=lambda q: q.uid):
            self._draw_placed_block(s, p)

        # layer badges
        for cell, arr in self.layers.items():
            if len(arr) >= 2:
                r, c = cell
                rr = pygame.Rect(GRID_X + c * CELL, GRID_Y + r * CELL, CELL, CELL)
                pygame.draw.rect(s, (255, 220, 100), (rr.right - 13, rr.y + 2, 11, 11))
                self.text(s, "2", (rr.right - 10, rr.y + 1), (20, 20, 10), self.mono10)

        # names are drawn last, so a higher card can never hide a lower card's name
        self._draw_placed_labels(s)

        # hover cell
        cell = self.grid_cell_at(self.mouse)
        if cell and not self.drag:
            r, c = cell
            rr = pygame.Rect(GRID_X + c * CELL, GRID_Y + r * CELL, CELL, CELL)
            pygame.draw.rect(s, (220, 245, 255), rr, 1)

        # ghost
        if self.drag:
            key = self.drag["key"]
            rot = self.drag["rot"]
            rr, cc = self.drag_anchor(key, rot)
            ok = self.can_place(key, rr, cc, rot)
            cells = rotate(BY_KEY[key]["cells"], rot)
            color = (90, 230, 145) if ok else (255, 80, 95)
            for r, c in cells:
                x = GRID_X + (cc + c) * CELL
                y = GRID_Y + (rr + r) * CELL
                if x < GRID_X or y < GRID_Y or x >= GRID.right or y >= GRID.bottom:
                    continue
                ghost = pygame.Surface((CELL - 2, CELL - 2), pygame.SRCALPHA)
                ghost.fill((*color, 80))
                s.blit(ghost, (x + 1, y + 1))
                pygame.draw.rect(s, color, (x + 1, y + 1, CELL - 2, CELL - 2), 2)

        # side legend
        lx = 430
        self.text(s, "内存规则", (lx, 154), MUTED, self.font12)
        rules = [
            ("单格", "最多 2 层"),
            ("全盘", "最多 3 格重叠"),
            ("重叠", "不计画质惩罚"),
            ("坏死", "手动标记"),
            ("ECC", "手动选格"),
        ]
        yy = 174
        for k, v in rules:
            self.text(s, k, (lx, yy), DIM, self.font10 if hasattr(self, "font10") else self.font11)
            self.text(s, v, (lx + 44, yy), TEXT if k != "坏死" else RED, self.font11)
            yy += 22

        # toolbar
        tools = [
            ("select", "选择", "移动卡牌"),
            ("necro", "坏死 +", "手动添加"),
            ("clear", "清除", "移除坏死"),
            ("ecc", "ECC 修复", "手动点格"),
            ("reset", "清空", "全部收回"),
        ]
        self.tool_hits = []
        tx = 24
        for key, label, sub in tools:
            r = pygame.Rect(tx, 548, 98, 54)
            active = self.tool == key
            pygame.draw.rect(s, (23, 48, 65) if active else (16, 25, 35), r)
            pygame.draw.rect(s, CATEGORIES["CUT"]["color"] if active else LINE, r, 2 if active else 1)
            self.text(s, label, (r.x + 8, r.y + 7), TEXT if active else MUTED, self.font14)
            self.text(s, sub, (r.x + 8, r.y + 31), DIM, self.font11)
            self.tool_hits.append((key, r))
            tx += 102
        self.text(s, "R 旋转 · 右键收回 · 拖拽装配", (24, 612), DIM, self.font11)
        self.text(s, "演示：ECC 不消耗 · 仓库无上限", (24, 630), DIM, self.font11)

        # right panel
        self.px(s, RIGHT, PANEL, LINE, 1)
        self.text(s, "仓库", (576, 76), TEXT, self.font18)
        self.text(s, "INFINITE / DEMO", (630, 80), MUTED, self.mono10)
        self.text(s, f"卡牌 {sum(self.counts.values())} 张", (RIGHT.right - 100, 80), DIM, self.font11)
        self.draw_tabs(s)
        self.draw_warehouse(s)

        # detail overlay
        if self.detail_key:
            self.draw_detail(s)

        # footer
        pygame.draw.line(s, LINE, (16, 674), (W - 16, 674), 1)
        self.text(s, "左：8×8 装配台", (24, 684), DIM, self.font11)
        self.text(s, "右：仓库 / 10 张每种", (210, 684), DIM, self.font11)
        self.text(s, "点击卡牌右下角展开键查看详情", (430, 684), MUTED, self.font11)
        if self.message_t > 0:
            self.text(s, self.message, (430, 684), (255, 220, 100), self.font11)

    def draw_ai(self, s, x, y, size):
        # tiny pixel assistant: cyan hair, dark uniform, one eye
        pygame.draw.rect(s, (20, 30, 42), (x, y, size, size))
        pygame.draw.rect(s, (38, 52, 67), (x, y, size, size), 1)
        pygame.draw.rect(s, (45, 140, 180), (x + 9, y + 7, 18, 20))
        pygame.draw.rect(s, (80, 210, 245), (x + 6, y + 9, 6, 22))
        pygame.draw.rect(s, (80, 210, 245), (x + 24, y + 9, 6, 20))
        pygame.draw.rect(s, (242, 205, 186), (x + 12, y + 14, 12, 11))
        pygame.draw.rect(s, (28, 52, 70), (x + 15, y + 18, 2, 2))
        pygame.draw.rect(s, (28, 52, 70), (x + 21, y + 18, 2, 2))
        pygame.draw.rect(s, (230, 245, 255), (x + 9, y + 6, 18, 3))
        pygame.draw.rect(s, (34, 60, 80), (x + 10, y + 28, 16, 3))

    def draw_tabs(self, s):
        self.tab_hits = []
        x = 576
        for key, label, cat in TABS:
            r = pygame.Rect(x, 104, 78, 24)
            active = self.tab == key
            pygame.draw.rect(s, (25, 43, 58) if active else (16, 25, 35), r)
            pygame.draw.rect(s, CATEGORIES[cat]["color"] if active and cat else (LINE if not active else (80, 210, 245)), r, 1)
            if cat:
                self.icon(s, cat, x + 6, 108, 15)
                self.text(s, label, (x + 24, 108), TEXT if active else MUTED, self.font12)
            else:
                self.text(s, label, (x + 20, 108), TEXT if active else MUTED, self.font12)
            self.tab_hits.append((key, r))
            x += 82

    def draw_warehouse(self, s):
        cards = [c for c in CARDS if self.tab == "ALL" or c["cat"] == self.tab]
        view = pygame.Rect(570, 132, 688, 508)
        rows = max(1, math.ceil(len(cards) / 3))
        content_h = rows * (CARD_H + CARD_GAP)
        self.max_scroll = max(0, content_h - view.h)
        self.scroll = max(0, min(self.max_scroll, self.scroll))
        self.card_hits = []
        self.expand_hits = []
        clip = s.get_clip()
        s.set_clip(view)
        for i, card in enumerate(cards):
            col = i % 3
            row = i // 3
            x = CARD_X + col * (CARD_W + CARD_GAP)
            y = CARD_Y + row * (CARD_H + CARD_GAP) - self.scroll
            if y + CARD_H < view.y or y > view.bottom:
                continue
            r = pygame.Rect(x, y, CARD_W, CARD_H)
            self.draw_card_face(s, card, r)
            self.card_hits.append((card["key"], r))
        s.set_clip(clip)
        # scrollbar
        if self.max_scroll > 0:
            track = pygame.Rect(RIGHT.right - 8, 136, 4, 496)
            pygame.draw.rect(s, (27, 40, 52), track)
            h = max(28, int(track.h * view.h / content_h))
            y = track.y + int((track.h - h) * self.scroll / self.max_scroll)
            pygame.draw.rect(s, CATEGORIES["CUT"]["color"], (track.x, y, 4, h))

    def draw_card_face(self, s, card, r):
        key = card["key"]
        cat = CATEGORIES[card["cat"]]
        count = self.counts[key]
        hover = r.collidepoint(self.mouse)
        if count <= 0:
            fill = (14, 18, 24)
            border = (44, 52, 62)
        else:
            fill = (21, 32, 44) if hover else (17, 25, 35)
            border = cat["color"] if hover else (45, 61, 76)
        # shadow
        pygame.draw.rect(s, (5, 8, 12), (r.x + 3, r.y + 3, r.w, r.h))
        pygame.draw.rect(s, fill, r)
        pygame.draw.rect(s, border, r, 2)
        pygame.draw.rect(s, cat["color"], (r.x, r.y, r.w, 3))
        self.icon(s, card["cat"], r.x + 9, r.y + 12, 22)
        self.text(s, f"×{count}", (r.right - 42, r.y + 11), MUTED if count else RED, self.font12)
        self.text(s, card["cn"], (r.centerx, r.y + 48), TEXT if count else DIM, self.font20, center=True)
        self.text(s, card["en"], (r.centerx, r.y + 72), cat["color"], self.mono10, center=True)
        # shape area
        pygame.draw.rect(s, (11, 18, 26), (r.x + 16, r.y + 88, r.w - 32, 74))
        pygame.draw.rect(s, (27, 40, 53), (r.x + 16, r.y + 88, r.w - 32, 74), 1)
        self.shape_preview(s, card["cells"], r.centerx, r.y + 125, 16, cat["color"], False)
        pygame.draw.line(s, (38, 52, 66), (r.x + 14, r.y + 172), (r.right - 14, r.y + 172), 1)
        self.text(s, f"Mb {card['mb']}", (r.x + 14, r.y + 180), MUTED, self.font12)
        # rarity pips
        for i in range(3):
            col = RARITY_COLORS[card["rarity"]] if i <= card["rarity"] else (43, 55, 68)
            pygame.draw.rect(s, col, (r.x + 80 + i * 9, r.y + 183, 6, 6))
        # expand button
        er = pygame.Rect(r.right - 30, r.bottom - 28, 22, 22)
        pygame.draw.rect(s, (25, 41, 55), er)
        pygame.draw.rect(s, (70, 100, 120), er, 1)
        pygame.draw.line(s, TEXT, (er.x + 6, er.y + 16), (er.x + 16, er.y + 6), 1)
        pygame.draw.line(s, TEXT, (er.x + 11, er.y + 6), (er.x + 16, er.y + 6), 1)
        pygame.draw.line(s, TEXT, (er.x + 16, er.y + 6), (er.x + 16, er.y + 11), 1)
        self.expand_hits.append((key, er, r))
        if hover:
            pygame.draw.rect(s, (210, 245, 255), r, 1)

    # ------------------------------------------------------------ detail
    def open_detail(self, key, tile_rect):
        self.detail_key = key
        w, h = 334, 406
        x = tile_rect.right + 10
        if x + w > RIGHT.right - 8:
            x = tile_rect.left - w - 10
        x = max(RIGHT.x + 6, min(RIGHT.right - w - 8, x))
        y = max(72, min(H - h - 24, tile_rect.y - 20))
        self.detail_rect = pygame.Rect(x, y, w, h)
        self.detail_close = pygame.Rect(x + w - 30, y + 10, 20, 20)
        self.audio.play("open")

    def close_detail(self):
        if self.detail_key:
            self.detail_key = None
            self.detail_rect = None
            self.detail_close = None
            self.audio.play("close")

    def draw_detail(self, s):
        card = BY_KEY[self.detail_key]
        cat = CATEGORIES[card["cat"]]
        r = self.detail_rect
        pygame.draw.rect(s, (5, 8, 12), (r.x + 4, r.y + 4, r.w, r.h))
        pygame.draw.rect(s, (15, 23, 33), r)
        pygame.draw.rect(s, cat["color"], r, 2)
        pygame.draw.rect(s, cat["color"], (r.x, r.y, r.w, 5))
        self.icon(s, card["cat"], r.x + 14, r.y + 14, 24)
        self.text(s, CATEGORIES[card["cat"]]["cn"] + "类", (r.x + 46, r.y + 13), cat["color"], self.font12)
        self.text(s, card["cn"], (r.x + 16, r.y + 46), TEXT, self.font24)
        self.text(s, card["en"], (r.x + 16, r.y + 74), cat["color"], self.mono12)
        # close
        pygame.draw.rect(s, (35, 24, 30), self.detail_close)
        pygame.draw.rect(s, (95, 55, 62), self.detail_close, 1)
        self.text(s, "X", (self.detail_close.centerx, self.detail_close.centery - 1), (255, 180, 185),
                  self.font12, center=True)
        # shape
        self.text(s, "形状", (r.x + 16, r.y + 102), DIM, self.font11)
        self.shape_preview(s, card["cells"], r.x + 80, r.y + 136, 24, cat["color"], True)
        self.text(s, f"占格 {len(card['cells'])}", (r.x + 150, r.y + 112), MUTED, self.font11)
        self.text(s, f"Mb {card['mb']}", (r.x + 150, r.y + 130), MUTED, self.font11)
        self.text(s, f"工作 {card['work']}", (r.x + 150, r.y + 148), MUTED, self.font11)
        self.text(s, f"稀有度 {RARITY[card['rarity']]}", (r.x + 16, r.y + 176), RARITY_COLORS[card["rarity"]], self.font11)
        self.text(s, f"目标：{card['target']}", (r.x + 150, r.y + 176), MUTED, self.font11)
        pygame.draw.line(s, (43, 58, 72), (r.x + 14, r.y + 196), (r.right - 14, r.y + 196), 1)
        effect_label = "被动效果" if card.get("kind") == "passive" else "主动技能效果"
        self.text(s, effect_label, (r.x + 16, r.y + 208), cat["color"], self.font12)
        yy = r.y + 228
        for line in self.wrap(card["effect"], self.font12, r.w - 32)[:5]:
            self.text(s, line, (r.x + 16, yy), TEXT, self.font12)
            yy += 19
        yy += 6
        self.text(s, "++ 升级", (r.x + 16, yy), (255, 205, 100), self.font12)
        yy += 20
        for line in self.wrap(card["up"], self.font11, r.w - 32)[:3]:
            self.text(s, line, (r.x + 16, yy), MUTED, self.font11)
            yy += 17
        self.text(s, f"仓库剩余 ×{self.counts[card['key']]}", (r.x + 16, r.bottom - 28), DIM, self.font11)

    # ------------------------------------------------------------ interaction
    def grid_cell_at(self, pos):
        if not GRID.collidepoint(pos):
            return None
        return ((pos[1] - GRID_Y) // CELL, (pos[0] - GRID_X) // CELL)

    def start_drag(self, key, source, old=None, rot=0):
        self.drag = {"key": key, "source": source, "old": old, "rot": rot}
        self.audio.play("pick")

    def cancel_drag(self):
        if not self.drag:
            return
        if self.drag["source"] == "grid" and self.drag["old"]:
            self.restore(self.drag["old"])
        self.drag = None

    def drop_drag(self):
        if not self.drag:
            return
        key = self.drag["key"]
        rot = self.drag["rot"]
        row, col = self.drag_anchor(key, rot)
        if self.can_place(key, row, col, rot):
            if self.drag["source"] == "warehouse":
                if self.counts.get(key, 0) <= 0:
                    self.drag = None
                    self.audio.play("invalid")
                    return
                self.counts[key] -= 1
            p = self.add_placed(key, row, col, rot)
            if p:
                self.audio.play("place")
                self.drag = None
                return
        # failed. restore card dragged out of the grid
        if self.drag["source"] == "grid" and self.drag["old"]:
            self.restore(self.drag["old"])
        self.drag = None
        self.audio.play("invalid")

    def handle_click(self, pos, button=1):
        self.mouse = pos
        if button == 1 and self.recommended_rect.collidepoint(pos):
            self.apply_recommended_deck()
            return
        if button == 1 and self.start_rect.collidepoint(pos):
            self.start_requested = True
            self.audio.play("open")
            return
        if button == 3:
            cell = self.grid_cell_at(pos)
            if cell and self.tool == "select":
                p = self.top_card(cell)
                if p:
                    self.remove_placed(p, give_back=True)
                    self.audio.play("drop")
            return

        # detail close / outside
        if self.detail_key:
            if self.detail_close and self.detail_close.collidepoint(pos):
                self.close_detail()
                return
            if self.detail_rect and self.detail_rect.collidepoint(pos):
                return
            self.close_detail()

        for key, r in self.tab_hits:
            if r.collidepoint(pos):
                if self.tab != key:
                    self.tab = key
                    self.scroll = 0
                    self.audio.play("tab")
                return

        for key, r in self.tool_hits:
            if r.collidepoint(pos):
                if key == "reset":
                    self.reset_all()
                else:
                    self.tool = key
                    self.audio.play("tab")
                return

        for key, er, _ in self.expand_hits:
            if er.collidepoint(pos):
                self.open_detail(key, _)
                return

        for key, r in self.card_hits:
            if r.collidepoint(pos):
                if self.counts.get(key, 0) > 0:
                    self.start_drag(key, "warehouse")
                return

        cell = self.grid_cell_at(pos)
        if cell:
            if self.tool == "necro":
                if cell in self.necro:
                    self.audio.play("invalid")
                elif cell in self.layers:
                    self.audio.play("invalid")
                else:
                    self.necro.add(cell)
                    self.audio.play("necro")
                return
            if self.tool == "clear":
                if cell in self.necro:
                    self.necro.discard(cell)
                    self.audio.play("clear")
                else:
                    self.audio.play("invalid")
                return
            if self.tool == "ecc":
                if cell in self.necro:
                    self.necro.discard(cell)
                    for p in self.placed.values():
                        if p.damaged and cell in p.cells():
                            p.damaged = False
                    self.audio.play("repair")
                else:
                    self.audio.play("invalid")
                return
            if self.tool == "select":
                p = self.top_card(cell)
                if p:
                    self.remove_placed(p, give_back=False)
                    self.start_drag(p.key, "grid", p, p.rot)
                return

    def reset_all(self):
        for p in list(self.placed.values()):
            self.counts[p.key] = self.counts.get(p.key, 0) + 1
        self.placed.clear()
        self.layers.clear()
        self.necro.clear()
        self.close_detail()
        self.drag = None
        self.audio.play("reset")

    # ------------------------------------------------------------ loop
    def run(self):
        running = True
        frames = 0
        while running:
            dt = self.clock.tick(60) / 1000.0
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    running = False
                elif e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_ESCAPE:
                        if self.detail_key:
                            self.close_detail()
                        elif self.drag:
                            self.cancel_drag()
                        else:
                            running = False
                    elif e.key == pygame.K_r:
                        if self.drag:
                            self.drag["rot"] = (self.drag["rot"] + 1) % 4
                            self.audio.play("rotate")
                    elif e.key == pygame.K_n:
                        self.tool = "necro"
                        self.audio.play("tab")
                    elif e.key == pygame.K_c:
                        self.tool = "clear"
                        self.audio.play("tab")
                    elif e.key == pygame.K_e:
                        self.tool = "ecc"
                        self.audio.play("tab")
                    elif e.key == pygame.K_F11:
                        self.windowed = not self.windowed
                        self._set_window()
                    elif e.key == pygame.K_F5:
                        self.start_requested = True
                    elif e.key == pygame.K_F6:
                        self.apply_recommended_deck()
                elif e.type == pygame.MOUSEMOTION:
                    self.mouse = self.to_logical(e.pos)
                elif e.type == pygame.MOUSEBUTTONDOWN:
                    self.handle_click(self.to_logical(e.pos), e.button)
                elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
                    if self.drag:
                        self.mouse = self.to_logical(e.pos)
                        self.drop_drag()
                elif e.type == pygame.MOUSEWHEEL:
                    mx, my = self.to_logical(pygame.mouse.get_pos())
                    if RIGHT.collidepoint(mx, my) and not self.detail_key:
                        self.scroll = max(0, min(self.max_scroll, self.scroll - e.y * 52))

            self.mouse = self.to_logical(pygame.mouse.get_pos())
            if self.start_requested:
                self.start_requested = False
                self.start_battle()
                continue
            self.present()
            frames += 1
            if self.shot and frames >= 4:
                os.makedirs(os.path.dirname(self.shot) or ".", exist_ok=True)
                pygame.image.save(self.window, self.shot)
                break
        pygame.quit()


def main():
    windowed = "--windowed" in sys.argv
    shot = None
    if "--shot" in sys.argv:
        try:
            shot = sys.argv[sys.argv.index("--shot") + 1]
        except Exception:
            shot = None
    size = None
    if "--size" in sys.argv:
        try:
            ww, hh = sys.argv[sys.argv.index("--size") + 1].lower().split("x")
            size = (int(ww), int(hh))
        except Exception:
            size = None
    App(windowed=windowed, shot=shot, size=size).run()


if __name__ == "__main__":
    main()
