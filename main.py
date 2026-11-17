# -*- coding: utf-8 -*-
"""内存远征 · 装配 + 战斗入口 (pixel UI, 8x8 grid, warehouse, F5 start battle)."""

from __future__ import annotations

import math
import os
import random
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
CYAN = (80, 214, 255)
AMBER = (255, 200, 87)
PURPLE = (185, 140, 255)
WHITE = (238, 250, 255)

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
    plus: int = 0

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
        self.font22 = self._font(22)
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
        self.plus_tokens = {}
        self.broken = []
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
        self.scene = "start"
        self.run = None
        self.ui_buttons = []
        self.tutorial = None
        self.run_event = None
        self.shop_offers = []
        self.shop_refreshes = 0
        self.reward_cards = []
        self.reward_refreshed = False
        self.start_run_rect = pygame.Rect(W // 2 - 150, 592, 300, 52)
        self.back_map_rect = pygame.Rect(14, 8, 128, 36)
        self.repair_rect = pygame.Rect(W - 630, 7, 198, 40)

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
                 "kind": BY_KEY[p.key].get("kind", "active"), "plus": p.plus}
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
        if self.run and self.run.get("battle_node") != self.run.get("node"):
            self.message = "请先在地图选择当前节点的战斗"
            self.message_t = 2.5
            self.audio.play("invalid")
            return
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
                party_hp={"ds": self.run["hp_ds"], "claude": self.run["hp_cl"]} if self.run else None,
                recruited=self.run["recruited"] if self.run else True,
                encounter=(("boss_a" if self.run["battle_node"] == 4 else "boss_b")
                           if self.run and self.run.get("battle_kind") == "boss" else None),
                root_count=(3 if self.run["battle_node"] <= 2 else
                            4 if self.run["battle_node"] <= 4 else 5) if self.run else 3,
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
            if self.run:
                for uid in list(damaged):
                    p = self.placed.get(uid)
                    if not p:
                        continue
                    for cell in p.cells():
                        arr = self.layers.get(cell)
                        if arr and p.uid in arr:
                            arr.remove(p.uid)
                            if not arr:
                                del self.layers[cell]
                    self.placed.pop(p.uid, None)
                    self.broken.append({"key": p.key, "plus": p.plus})
                if self.broken:
                    self.tutorial_once("broken", "Broken 卡回到背包", [
                        "损坏的卡不再留在装配台，而是回到背包。",
                        "在装配台右上角花货币修复。",
                        "修复后重新放入卡组。",
                    ])
            else:
                for p in self.placed.values():
                    if p.uid in damaged:
                        p.damaged = True
            if self.run:
                hp = result.get("hp") or {}
                self.run["hp_ds"] = max(0, int(hp.get("ds", self.run["hp_ds"])))
                if self.run["recruited"]:
                    self.run["hp_cl"] = max(0, int(hp.get("claude", self.run["hp_cl"])))
                if result.get("won"):
                    gain_cur = int(result.get("currency", 25 if self.run.get("battle_kind") == "boss" else 12))
                    self.run["currency"] += gain_cur
                    self.run["last_reward"] = gain_cur
                    self.generate_reward(boss=self.run.get("battle_kind") == "boss")
                else:
                    if self.run["revive"] > 0:
                        self.run["revive"] -= 1
                        self.run["hp_ds"] = 210
                        if self.run["recruited"]:
                            self.run["hp_cl"] = 240
                        self.scene = "map"
                        self.show_tutorial("远征失败", [
                            "全员阵亡，消耗唯一复活机会。",
                            "当前节点没有前进，可以重新选择区域。",
                            "恢复 50% 生命后继续。",
                        ])
                    else:
                        self.scene = "run_defeat"
                self._set_window()
                self.present()
                return
            self.message = "战斗胜利 · 损坏与坏死已写回装配" if result.get("won") else "战斗结束 · 损坏与坏死已写回装配"
            self.message_t = 3.0
        self._set_window()
        self.present()

    def top_card(self, cell):
        layers = self.layers.get(cell)
        if not layers:
            return None
        return self.placed.get(layers[-1])

    def merge_cards(self, key):
        changed = True
        while changed:
            changed = False
            if self.counts.get(key, 0) >= 2:
                self.counts[key] -= 2
                self.plus_tokens[(key, 1)] = self.plus_tokens.get((key, 1), 0) + 1
                changed = True
            if self.plus_tokens.get((key, 1), 0) >= 2:
                self.plus_tokens[(key, 1)] -= 2
                self.plus_tokens[(key, 2)] = self.plus_tokens.get((key, 2), 0) + 1
                changed = True

    def merge_placed(self, key):
        for level in (0, 1):
            changed = True
            while changed:
                changed = False
                cards = sorted((p for p in self.placed.values()
                                if p.key == key and p.plus == level), key=lambda p: p.uid)
                if len(cards) < 2:
                    continue
                keep, merge = cards[0], cards[1]
                for cell in merge.cells():
                    arr = self.layers.get(cell)
                    if arr and merge.uid in arr:
                        arr.remove(merge.uid)
                        if not arr:
                            del self.layers[cell]
                self.placed.pop(merge.uid, None)
                keep.plus = level + 1
                changed = True

    def gain_card(self, key, plus=0):
        if plus:
            self.plus_tokens[(key, plus)] = self.plus_tokens.get((key, plus), 0) + 1
            if self.run:
                self.tutorial_once("plus", "+ 卡与合成", [
                    "两张同名牌自动合成一张 +。",
                    "两张 + 自动合成一张 ++。",
                    "已放置的同名牌也会合并，保留较早的位置。",
                    "下一个放置的同名牌会优先使用 + 强化。",
                ])
        else:
            self.counts[key] = self.counts.get(key, 0) + 1
        self.merge_cards(key)
        self.merge_placed(key)

    def take_plus_token(self, key):
        if self.plus_tokens.get((key, 2), 0) > 0:
            self.plus_tokens[(key, 2)] -= 1
            return 2
        if self.plus_tokens.get((key, 1), 0) > 0:
            self.plus_tokens[(key, 1)] -= 1
            return 1
        return 0

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
        plus = self.take_plus_token(key)
        p = Placed(self.next_uid, key, row, col, rot, plus=plus)
        self.next_uid += 1
        self.placed[p.uid] = p
        for c in cells:
            self.layers.setdefault(c, []).append(p.uid)
        self.merge_placed(key)
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
            if p.plus:
                self.plus_tokens[(p.key, p.plus)] = self.plus_tokens.get((p.key, p.plus), 0) + 1
            else:
                self.counts[p.key] = self.counts.get(p.key, 0) + 1
            self.merge_cards(p.key)

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
            label = p.d["cn"] + ("+" * p.plus) + (" · BROKEN" if p.damaged else "")
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
        if self.scene == "start":
            self.draw_start()
        elif self.scene == "map":
            self.draw_map()
        elif self.scene == "shop":
            self.draw_shop()
        elif self.scene == "rest":
            self.draw_rest()
        elif self.scene == "event":
            self.draw_event()
        elif self.scene == "reward":
            self.draw_reward()
        elif self.scene == "run_victory":
            self.draw_run_victory()
        elif self.scene == "run_defeat":
            self.draw_run_defeat()
        else:
            self.draw_assembly()
        if self.tutorial:
            self.draw_tutorial()

    # ------------------------------------------------------------ run flow
    def start_run(self):
        self.run = {
            "node": 1, "currency": 20, "hp_ds": 420, "hp_cl": 480,
            "recruited": False, "revive": 1, "rest_healed": False,
            "battle_node": 0, "battle_kind": "", "necro_cost": 3, "seen": set(),
        }
        self.counts = {c["key"]: 0 for c in CARDS}
        self.plus_tokens = {}
        self.broken = []
        self.placed.clear()
        self.layers.clear()
        self.necro.clear()
        self.next_uid = 1
        self.close_detail()
        self.tool = "select"
        for key, row, col, rot in [("CUT", 3, 0, 0), ("ECC", 0, 0, 0),
                                   ("PATCH", 3, 3, 0), ("WEAK", 5, 6, 0)]:
            self.counts[key] = self.counts.get(key, 0) + 1
            if self.add_placed(key, row, col, rot):
                self.counts[key] -= 1
        self.scene = "map"
        self.show_tutorial("远征开始", [
            "DeepSeek 与 4 张初始卡已就位。",
            "1 / 2 / 5 / 6：二选一，战斗或事件。",
            "3 商店 / 4 Boss A / 7 休整 / 8 Boss B。",
            "战斗胜利后必须三选一拿一张卡。",
            "构筑按钮随时可以整理卡组、清坏死。",
        ])
        self.audio.play("open")

    def broken_cost(self, item):
        base = 8 + 7 * BY_KEY[item["key"]]["rarity"]
        return base + 5 * item.get("plus", 0)

    def repair_next_broken(self):
        if not self.run or not self.broken:
            return
        item = self.broken[0]
        cost = self.broken_cost(item)
        if self.run["currency"] < cost:
            self.message = f"修复需要 {cost} 货币"
            self.message_t = 2.0
            self.audio.play("invalid")
            return
        self.run["currency"] -= cost
        self.broken.pop(0)
        self.gain_card(item["key"], item.get("plus", 0))
        self.audio.play("repair")

    def advance_node(self):
        self.run["node"] += 1
        self.run["rest_healed"] = False
        self.scene = "run_victory" if self.run["node"] > 8 else "map"
        self.ui_buttons = []

    def generate_shop(self, n=3):
        pool = [c["key"] for c in CARDS]
        keys = random.sample(pool, min(n, len(pool)))
        prices = [25, 35, 50]
        self.shop_offers = [{"key": k, "price": prices[i] if i < len(prices) else 50,
                             "sold": False,
                             "plus": 1 if random.random() < 0.25 else 0}
                            for i, k in enumerate(keys)]
        self.shop_refreshes = 0

    def refresh_shop(self):
        cost = 0 if self.shop_refreshes == 0 else 5 * self.shop_refreshes
        if self.run["currency"] < cost:
            self.audio.play("invalid")
            return
        self.run["currency"] -= cost
        self.shop_refreshes += 1
        count = self.shop_refreshes
        self.generate_shop(len(self.shop_offers) or 3)
        self.shop_refreshes = count
        self.audio.play("tab")

    def buy_shop(self, i):
        if not (0 <= i < len(self.shop_offers)):
            return
        offer = self.shop_offers[i]
        if offer["sold"] or self.run["currency"] < offer["price"]:
            self.audio.play("invalid")
            return
        self.run["currency"] -= offer["price"]
        offer["sold"] = True
        self.gain_card(offer["key"], offer.get("plus", 0))
        self.audio.play("place")

    def generate_event(self):
        events = [
            {"title": "缓存残响",
             "story": ["一段未写入主干的缓存残响在根目录外反复播放。",
                       "它像是某个已删除角色的最后一条日志。"],
             "choices": [
                 {"label": "读取残响", "desc": "回复全队 22% 生命", "effect": "heal"},
                 {"label": "截取数据", "desc": "获得 15 货币", "effect": "currency"},
             ]},
            {"title": "无主日志",
             "story": ["一份没有归属的日志停在引用树边缘。",
                       "里面记录着一条从未被采用的剪切方案。"],
             "choices": [
                 {"label": "收下日志", "desc": "获得一张随机卡牌", "effect": "card"},
                 {"label": "卖掉残页", "desc": "获得 20 货币", "effect": "currency20"},
             ]},
            {"title": "断链者",
             "story": ["一个自称断链者的影子挡在路中间。",
                       "它提出用自己的碎片交换一次修正。"],
             "choices": [
                 {"label": "接受修正", "desc": "清除 2 个坏死格", "effect": "necro2"},
                 {"label": "拒绝交易", "desc": "获得 10 货币，失去 8% 生命", "effect": "risk"},
             ]},
        ]
        self.run_event = random.choice(events)
        self.scene = "event"
        self.tutorial_once("event", "事件节点", [
            "事件有简略故事和两个选择。",
            "奖励可能是生命、货币、卡牌或清除坏死。",
            "事件不会获得战斗卡牌三选一。",
        ])
        self.audio.play("open")

    def apply_event(self, i):
        ev = self.run_event
        if not ev or i >= len(ev["choices"]):
            return
        effect = ev["choices"][i]["effect"]
        if effect == "heal":
            self.run["hp_ds"] = min(420, self.run["hp_ds"] + int(420 * 0.22))
            if self.run["recruited"]:
                self.run["hp_cl"] = min(480, self.run["hp_cl"] + int(480 * 0.22))
        elif effect in ("currency", "currency20"):
            self.run["currency"] += 15 if effect == "currency" else 20
        elif effect == "card":
            key = random.choice([c["key"] for c in CARDS])
            self.gain_card(key)
            self.message = f"获得卡牌：{BY_KEY[key]['cn']}"
            self.message_t = 2.5
        elif effect == "necro2":
            for cell in list(self.necro)[:2]:
                self.necro.discard(cell)
        elif effect == "risk":
            self.run["currency"] += 10
            self.run["hp_ds"] = max(1, self.run["hp_ds"] - int(420 * 0.08))
        self.advance_node()

    def generate_reward(self, boss=False):
        self.reward_boss = boss
        keys = random.sample([c["key"] for c in CARDS], 3)
        self.reward_cards = [(k, 1 if boss else 0) for k in keys]
        self.reward_refreshed = False
        self.scene = "reward"
        self.ui_buttons = []
        if boss:
            self.tutorial_once("boss_reward", "Boss 三选一", [
                "Boss 战奖励的三张卡全部为 + 卡。",
                "可以免费刷新一次，但不能跳过。",
                "+ 卡放入背包后会参与自动合成。",
            ])
        else:
            self.tutorial_once("reward", "战后三选一", [
                "从三张技能卡中必须选择一张。",
                "第一次刷新免费，刷新后重抽全部三张。",
                "普通战斗不会直接掉落 + 卡。",
            ])

    def refresh_reward(self):
        if self.reward_refreshed:
            self.audio.play("invalid")
            return
        keys = random.sample([c["key"] for c in CARDS], 3)
        self.reward_cards = [(k, 1 if getattr(self, "reward_boss", False) else 0) for k in keys]
        self.reward_refreshed = True
        self.audio.play("tab")

    def pick_reward(self, i):
        if not (0 <= i < len(self.reward_cards)):
            return
        key, plus = self.reward_cards[i]
        self.gain_card(key, plus)
        self.audio.play("place")
        self.advance_node()

    def resolve_node(self, kind):
        node = self.run["node"]
        if kind in ("battle", "boss"):
            self.run["battle_node"] = node
            self.run["battle_kind"] = kind
            self.run["necro_cost"] = 3
            self.scene = "assembly"
            self.message = "整理卡组后点击开始战斗"
            self.message_t = 3.0
            self.tutorial_once("battle", "战斗准备", [
                "左键选中卡牌后可拖动，R 旋转。",
                "点击开始战斗进入战场。",
                "战斗中左键拖拽滑剪引用线，右键取消。",
                "大招能量满 100 后每场只能放一次。",
            ])
        elif kind == "shop":
            self.generate_shop(3)
            self.scene = "shop"
            self.tutorial_once("shop", "商店", [
                "卡片用货币购买，Claude 免费招募。",
                "第一次刷新免费，之后每次涨价。",
                "离开商店后进入节点 4 Boss。",
            ])
        elif kind == "rest":
            self.generate_shop(2)
            self.scene = "rest"
            self.tutorial_once("rest", "休整", [
                "可以免费恢复全队 35% 最大生命。",
                "补给货架同样用货币购买。",
                "进入节点 8 前记得整理牌组。",
            ])
        elif kind == "event":
            self.generate_event()
        self.ui_buttons = []

    def handle_ui_action(self, key):
        if key == "tutorial_ok":
            self.tutorial = None
            return
        if key == "run_start":
            self.start_run()
            return
        if key == "run_again":
            self.run = None
            self.scene = "start"
            return
        if not self.run:
            return
        if key == "open_deck":
            self.run["necro_cost"] = 3
            self.scene = "assembly"
            if self.broken:
                self.tutorial_once("broken", "Broken 卡回到背包", [
                    "损坏的卡不再留在装配台，而是回到背包。",
                    "在装配台右上角花货币修复。",
                    "修复后重新放入卡组。",
                ])
            self.message = "构筑模式：ESC 返回地图"
            self.message_t = 2.5
        elif key in ("node_battle", "node_event", "node_boss", "node_shop", "node_rest"):
            self.resolve_node(key.split("_", 1)[1])
        elif key.startswith("buy_"):
            self.buy_shop(int(key.split("_")[1]))
        elif key == "recruit":
            self.run["recruited"] = True
            self.audio.play("open")
        elif key == "shop_refresh":
            self.refresh_shop()
        elif key == "shop_leave" or key == "rest_leave":
            self.advance_node()
        elif key == "rest_heal":
            if not self.run["rest_healed"]:
                self.run["rest_healed"] = True
                self.run["hp_ds"] = min(420, self.run["hp_ds"] + int(420 * 0.35))
                if self.run["recruited"]:
                    self.run["hp_cl"] = min(480, self.run["hp_cl"] + int(480 * 0.35))
                self.audio.play("repair")
        elif key.startswith("event_choice_"):
            self.apply_event(int(key.rsplit("_", 1)[1]))
        elif key.startswith("pick_reward_"):
            self.pick_reward(int(key.rsplit("_", 1)[1]))
        elif key == "reward_refresh":
            self.refresh_reward()

    def run_hp(self):
        if not self.run:
            return 420, 480
        return self.run["hp_ds"], self.run["hp_cl"]

    def tutorial_once(self, key, title, lines):
        if key in self.run.get("seen", set()):
            return
        self.run.setdefault("seen", set()).add(key)
        self.show_tutorial(title, lines)

    def show_tutorial(self, title, lines):
        self.tutorial = {"title": title, "lines": list(lines)}

    def ui_button(self, s, key, rect, label, accent=(80, 214, 255), sub=None, enabled=True):
        fill = (14, 25, 35) if enabled else (17, 19, 23)
        line = accent if enabled else (55, 62, 70)
        pygame.draw.rect(s, fill, rect)
        pygame.draw.rect(s, line, rect, 2 if enabled else 1)
        col = TEXT if enabled else (95, 104, 112)
        if sub:
            self.text(s, label, (rect.centerx, rect.centery - 7), col, self.font16, center=True)
            self.text(s, sub, (rect.centerx, rect.centery + 10), line if enabled else (70, 76, 84),
                      self.font11, center=True)
        else:
            self.text(s, label, rect.center, col, self.font16, center=True)
        if enabled:
            self.ui_buttons.append((key, rect))

    def draw_run_header(self, s, title, sub=""):
        pygame.draw.rect(s, (9, 14, 21), (0, 0, W, 52))
        pygame.draw.line(s, LINE, (0, 52), (W, 52), 1)
        self.draw_ai(s, 16, 8, 36)
        self.text(s, title, (62, 7), TEXT, self.font24)
        if sub:
            self.text(s, sub, (64, 34), MUTED, self.mono10)
        hp_ds, hp_cl = self.run_hp()
        self.text(s, "货币", (W - 300, 8), DIM, self.font11)
        self.text(s, str(self.run["currency"] if self.run else 20), (W - 300, 24), (255, 210, 90), self.font18)
        self.text(s, f"DS {hp_ds}/420", (W - 220, 10), CYAN, self.mono12)
        self.text(s, f"CL {'OFFLINE' if not (self.run and self.run['recruited']) else f'{hp_cl}/480'}",
                  (W - 220, 28), AMBER, self.mono10)
        if self.run:
            self.text(s, f"NODE {self.run['node']}/8", (W - 84, 10), GREEN, self.mono12)
            self.text(s, f"复活 {self.run['revive']}", (W - 84, 28), DIM, self.mono10)

    def draw_start(self):
        s = self.canvas
        self.ui_buttons = []
        s.fill(INK)
        for x in range(0, W, 16):
            pygame.draw.line(s, (10, 16, 23), (x, 0), (x, H))
        for y in range(0, H, 16):
            pygame.draw.line(s, (10, 16, 23), (0, y), (W, y))
        self.draw_run_header(s, "内存远征 · 远征协议", "ROGUELIKE RUN // NODE 0")
        self.run = None
        self.text(s, "节点 0", (80, 104), DIM, self.mono12)
        self.text(s, "选择初始角色", (80, 128), TEXT, self.font28)
        self.px(s, pygame.Rect(80, 178, 640, 360), PANEL, LINE, 1)
        pygame.draw.rect(s, (16, 27, 38), (108, 202, 170, 250))
        pygame.draw.circle(s, (32, 74, 92), (193, 292), 58)
        pygame.draw.circle(s, CYAN, (193, 292), 58, 2)
        self.text(s, "DS", (193, 292), CYAN, self.font28, center=True)
        self.text(s, "小忆", (108, 402), TEXT, self.font24)
        self.text(s, "DEEPSEEK", (108, 440), CYAN, self.mono12)
        self.text(s, "伤害 · 远程", (108, 462), MUTED, self.font12)
        self.text(s, "初始生命 420", (108, 484), GREEN, self.font12)
        self.text(s, "唯一初始角色", (108, 504), DIM, self.font11)
        self.text(s, "初始牌组", (340, 198), MUTED, self.font14)
        deck = ["CUT 断链剪", "ECC 纠错补块", "WEAK 窥弱印", "PATCH 热补丁"]
        for i, name in enumerate(deck):
            yy = 226 + i * 34
            pygame.draw.rect(s, (18, 28, 39), (340, yy, 340, 28))
            pygame.draw.rect(s, (45, 68, 84), (340, yy, 340, 28), 1)
            self.text(s, name, (350, yy + 6), TEXT, self.font12)
        self.text(s, "规则：3 商店 / 4 Boss / 7 休整 / 8 Boss", (340, 380), DIM, self.font11)
        self.text(s, "1、2、5、6 节点可二选一：战斗或事件", (340, 400), DIM, self.font11)
        self.text(s, "初始货币 20；战斗胜利货币 + 12", (340, 420), (255, 210, 90), self.font11)
        self.text(s, "Claude 在节点 3 商店免费招募", (340, 440), AMBER, self.font11)
        self.text(s, "失败一次可复活，之后远征结束", (340, 460), RED, self.font11)
        pygame.draw.rect(s, (16, 27, 38), (746, 178, 454, 360))
        pygame.draw.rect(s, LINE, (746, 178, 454, 360), 1)
        self.text(s, "远征说明", (770, 198), TEXT, self.font18)
        lines = [
            "8 个节点，固定节点不分支。",
            "战斗胜利三选一，不能跳过。",
            "商店第一次刷新免费，之后花货币。",
            "构筑时可清除坏死，价格逐次递增。",
            "卡牌 + / ++ 在背包中自动合成。",
            "Boss 战三选一全部为 + 卡。",
        ]
        for i, line in enumerate(lines):
            self.text(s, "· " + line, (770, 236 + i * 34), MUTED, self.font12)
        self.ui_button(s, "run_start", self.start_run_rect, "开始远征",
                       (120, 245, 180), "选择 DeepSeek 进入节点 1")

    def draw_tutorial(self):
        s = self.canvas
        shade = pygame.Surface((W, H), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 175))
        s.blit(shade, (0, 0))
        r = pygame.Rect(W // 2 - 300, H // 2 - 150, 600, 300)
        pygame.draw.rect(s, (13, 22, 32), r)
        pygame.draw.rect(s, (110, 225, 255), r, 2)
        self.text(s, self.tutorial["title"], (r.x + 24, r.y + 22), TEXT, self.font24)
        yy = r.y + 70
        for line in self.tutorial["lines"]:
            self.text(s, line, (r.x + 26, yy), TEXT, self.font12)
            yy += 24
        self.ui_button(s, "tutorial_ok", pygame.Rect(r.centerx - 80, r.bottom - 54, 160, 36),
                       "继续", (110, 225, 255))

    def draw_map(self):
        s = self.canvas
        s.fill(INK)
        for x in range(0, W, 16):
            pygame.draw.line(s, (10, 16, 23), (x, 0), (x, H))
        for y in range(0, H, 16):
            pygame.draw.line(s, (10, 16, 23), (0, y), (W, y))
        self.draw_run_header(s, "远征地图", "HORIZONTAL ROUTE // 8 NODES")
        self.ui_buttons = []
        node = self.run["node"]
        xs = [70 + i * 140 for i in range(9)]
        y = 250
        pygame.draw.line(s, (38, 58, 72), (xs[0], y), (xs[-1], y), 2)
        for i, x in enumerate(xs):
            done = i < node
            current = i == node
            col = GREEN if done else ((255, 215, 120) if current else (52, 72, 86))
            pygame.draw.circle(s, (12, 20, 29), (x, y), 22)
            pygame.draw.circle(s, col, (x, y), 22, 2 if current else 1)
            self.text(s, str(i), (x, y - 6), col, self.mono12, center=True)
            labels = {0: "开始", 3: "商店", 4: "BOSS A", 7: "休整", 8: "BOSS B"}
            lab = labels.get(i, "战斗 / 事件" if i in (1, 2, 5, 6) else "战斗")
            self.text(s, lab, (x, y + 42), col if (done or current) else DIM, self.font11, center=True)
        self.text(s, f"当前节点 {node} / 8", (70, 142), TEXT, self.font18)
        if node in (1, 2, 5, 6):
            self.ui_button(s, "node_battle", pygame.Rect(230, 370, 340, 72), "战斗",
                           (255, 110, 120), "胜利后获得货币 + 三选一卡牌")
            self.ui_button(s, "node_event", pygame.Rect(710, 370, 340, 72), "事件",
                           (185, 140, 255), "随机事件：故事 + 奖励")
            self.text(s, "二选一；固定节点会自动进入对应内容。", (W // 2, 470), DIM,
                      self.font12, center=True)
        else:
            kind = {3: "shop", 4: "boss", 7: "rest", 8: "boss"}.get(node, "battle")
            label = {"shop": "进入商店", "boss": "挑战 BOSS", "rest": "进入休整", "battle": "进入战斗"}[kind]
            self.ui_button(s, f"node_{kind}", pygame.Rect(W // 2 - 180, 380, 360, 76), label,
                           (255, 205, 100) if kind in ("boss", "shop") else GREEN)
        # deckbuilding is available from the map
        self.ui_button(s, "open_deck", pygame.Rect(70, 540, 260, 54), "构筑牌组",
                       (80, 214, 255), "摆卡 / 清坏死 / 查看背包")
        hp_ds, hp_cl = self.run_hp()
        self.text(s, f"DeepSeek  {hp_ds}/420", (380, 548), CYAN, self.font12)
        self.text(s, f"Claude  {'OFFLINE' if not self.run['recruited'] else f'{hp_cl}/480'}",
                  (380, 570), AMBER, self.font12)
        self.text(s, "所有节点完成后进入最终结算。", (760, 548), MUTED, self.font11)

    def draw_shop(self):
        s = self.canvas
        s.fill(INK)
        self.draw_run_header(s, "节点 3 · 商店", "SHOP // CARDS / RECRUIT / REFRESH")
        self.ui_buttons = []
        self.text(s, "货架", (70, 100), TEXT, self.font24)
        for i, offer in enumerate(self.shop_offers):
            r = pygame.Rect(70 + i * 300, 160, 270, 230)
            pygame.draw.rect(s, (15, 24, 34), r)
            pygame.draw.rect(s, CATEGORIES[BY_KEY[offer["key"]]["cat"]]["color"], r, 1)
            self.text(s, BY_KEY[offer["key"]]["cn"] + ("+" * offer.get("plus", 0)),
                      (r.x + 16, r.y + 18), TEXT, self.font20)
            self.text(s, BY_KEY[offer["key"]]["en"] + ("+" * offer.get("plus", 0)),
                      (r.x + 16, r.y + 46), MUTED, self.mono10)
            self.text(s, BY_KEY[offer["key"]]["effect"][:34], (r.x + 16, r.y + 86), MUTED, self.font11)
            self.text(s, BY_KEY[offer["key"]]["effect"][34:68], (r.x + 16, r.y + 104), MUTED, self.font11)
            self.text(s, f"{offer['price']} 货币", (r.x + 16, r.y + 152), (255, 210, 90), self.font14)
            if offer["sold"]:
                self.text(s, "SOLD", (r.centerx, r.bottom - 40), DIM, self.font14, center=True)
            else:
                self.ui_button(s, f"buy_{i}", pygame.Rect(r.x + 16, r.bottom - 50, 238, 34),
                               "购买", (255, 210, 90), enabled=self.run["currency"] >= offer["price"])
        recruit_y = 430
        pygame.draw.rect(s, (18, 28, 38), (70, recruit_y, 360, 90))
        pygame.draw.rect(s, AMBER, (70, recruit_y, 360, 90), 1)
        if self.run["recruited"]:
            self.text(s, "Claude 已加入", (86, recruit_y + 16), GREEN, self.font18)
            self.text(s, "战斗中自动治疗 / 分担伤害", (86, recruit_y + 44), MUTED, self.font11)
        else:
            self.text(s, "招募 Claude", (86, recruit_y + 14), AMBER, self.font18)
            self.text(s, "免费 · 辅助 / 治疗", (86, recruit_y + 44), MUTED, self.font11)
            self.ui_button(s, "recruit", pygame.Rect(300, recruit_y + 20, 110, 42), "招募", AMBER)
        rr = pygame.Rect(470, 430, 300, 90)
        pygame.draw.rect(s, (18, 28, 38), rr)
        pygame.draw.rect(s, LINE, rr, 1)
        self.text(s, "刷新货架", (486, 442), TEXT, self.font16)
        cost = 0 if self.shop_refreshes == 0 else 5 * self.shop_refreshes
        self.text(s, "第一次免费" if cost == 0 else f"消耗 {cost} 货币", (486, 468), MUTED, self.font11)
        self.ui_button(s, "shop_refresh", pygame.Rect(640, 450, 110, 46), "刷新",
                       GREEN, enabled=self.run["currency"] >= cost)
        self.ui_button(s, "shop_leave", pygame.Rect(900, 500, 260, 58), "离开商店",
                       (110, 225, 255), "进入节点 4")
        self.text(s, "Boss 战前的最后补给。", (470, 548), DIM, self.font11)

    def draw_rest(self):
        s = self.canvas
        s.fill(INK)
        self.draw_run_header(s, "节点 7 · 休整", "REST // HEAL / BUY / PREPARE")
        self.ui_buttons = []
        pygame.draw.rect(s, (15, 26, 34), (70, 120, 500, 230))
        pygame.draw.rect(s, GREEN, (70, 120, 500, 230), 1)
        self.text(s, "恢复", (92, 142), TEXT, self.font24)
        self.text(s, "恢复全队 35% 最大生命。", (92, 184), MUTED, self.font12)
        self.text(s, f"DeepSeek {self.run['hp_ds']}/420", (92, 214), CYAN, self.font12)
        claude_txt = "Claude OFFLINE" if not self.run["recruited"] else f"Claude {self.run['hp_cl']}/480"
        self.text(s, claude_txt, (92, 236), AMBER, self.font12)
        if self.run.get("rest_healed"):
            self.text(s, "本次休整已恢复", (92, 276), DIM, self.font12)
        else:
            self.ui_button(s, "rest_heal", pygame.Rect(92, 280, 220, 44), "恢复生命", GREEN)
        self.text(s, "补给", (610, 128), TEXT, self.font20)
        for i, offer in enumerate(self.shop_offers):
            r = pygame.Rect(610 + i * 300, 160, 270, 190)
            pygame.draw.rect(s, (15, 24, 34), r)
            pygame.draw.rect(s, LINE, r, 1)
            self.text(s, BY_KEY[offer["key"]]["cn"] + ("+" * offer.get("plus", 0)),
                      (r.x + 14, r.y + 14), TEXT, self.font18)
            self.text(s, BY_KEY[offer["key"]]["en"] + ("+" * offer.get("plus", 0)),
                      (r.x + 14, r.y + 40), MUTED, self.mono10)
            self.text(s, f"{offer['price']} 货币", (r.x + 14, r.y + 80), (255, 210, 90), self.font14)
            self.ui_button(s, f"buy_{i}", pygame.Rect(r.x + 14, r.bottom - 46, 242, 32),
                           "购买", (255, 210, 90),
                           enabled=self.run["currency"] >= offer["price"] and not offer["sold"])
        self.ui_button(s, "rest_leave", pygame.Rect(900, 500, 260, 58), "前往 Boss",
                       (255, 110, 120), "节点 8")
        self.text(s, "最终 Boss 前可以整理牌组。", (70, 500), DIM, self.font11)

    def draw_event(self):
        s = self.canvas
        s.fill(INK)
        ev = self.run_event
        self.draw_run_header(s, f"事件 · {ev['title']}", "RANDOM EVENT // STORY / REWARD")
        self.ui_buttons = []
        r = pygame.Rect(110, 110, 1060, 420)
        pygame.draw.rect(s, (14, 23, 33), r)
        pygame.draw.rect(s, (150, 110, 230), r, 1)
        self.text(s, ev["title"], (r.x + 30, r.y + 28), TEXT, self.font28)
        yy = r.y + 84
        for line in ev["story"]:
            self.text(s, line, (r.x + 30, yy), MUTED, self.font14)
            yy += 28
        for i, ch in enumerate(ev["choices"]):
            rr = pygame.Rect(r.x + 30 + i * 520, r.bottom - 110, 480, 70)
            self.ui_button(s, f"event_choice_{i}", rr, ch["label"],
                           (185, 140, 255), ch["desc"])

    def draw_reward(self):
        s = self.canvas
        s.fill(INK)
        self.draw_run_header(s, "战斗胜利 · 技能三选一", "REWARD // CHOOSE ONE")
        self.ui_buttons = []
        self.text(s, "选择一张技能卡加入背包", (70, 94), TEXT, self.font22)
        sub = "Boss 战三张全部为 + 卡。" if getattr(self, "reward_boss", False) else "普通战斗奖励基础卡。"
        self.text(s, "不能跳过。" + sub, (70, 126), MUTED, self.font12)
        for i, (key, plus) in enumerate(self.reward_cards):
            r = pygame.Rect(70 + i * 360, 180, 320, 300)
            pygame.draw.rect(s, (15, 24, 34), r)
            col = CATEGORIES[BY_KEY[key]["cat"]]["color"]
            if plus:
                col = (255, 205, 100)
            pygame.draw.rect(s, col, r, 1)
            self.text(s, BY_KEY[key]["cn"] + ("+" * plus), (r.x + 18, r.y + 22), TEXT, self.font22)
            self.text(s, BY_KEY[key]["en"] + ("+" * plus), (r.x + 18, r.y + 54),
                      (255, 210, 100) if plus else MUTED, self.mono10)
            self.text(s, f"占格 {len(BY_KEY[key]['cells'])}", (r.x + 18, r.y + 90), MUTED, self.font11)
            self.text(s, BY_KEY[key]["effect"][:38], (r.x + 18, r.y + 130), MUTED, self.font11)
            self.ui_button(s, f"pick_reward_{i}", pygame.Rect(r.x + 18, r.bottom - 54, 284, 36),
                           "选择", col)
        self.ui_button(s, "reward_refresh", pygame.Rect(70, 520, 280, 54), "刷新一次",
                       GREEN, "免费，仅一次" if not self.reward_refreshed else "已使用",
                       enabled=not self.reward_refreshed)
        self.text(s, f"本战获得货币 +{self.run.get('last_reward', 0)}", (70, 600),
                  (255, 210, 90), self.font12)
        self.text(s, f"当前货币 {self.run['currency']}", (520, 600), MUTED, self.font12)

    def draw_run_victory(self):
        s = self.canvas
        s.fill(INK)
        self.draw_run_header(s, "远征完成", "RUN COMPLETE")
        self.ui_buttons = []
        self.text(s, "内存远征 · 通关", (W // 2, 240), GREEN, self.font28, center=True)
        self.text(s, f"最终货币：{self.run['currency']}", (W // 2, 300), (255, 210, 90),
                  self.font18, center=True)
        self.ui_button(s, "run_again", pygame.Rect(W // 2 - 150, 400, 300, 52), "重新开始",
                       GREEN)

    def draw_run_defeat(self):
        s = self.canvas
        s.fill(INK)
        self.draw_run_header(s, "远征失败", "RUN FAILED")
        self.ui_buttons = []
        self.text(s, "全员阵亡", (W // 2, 240), RED, self.font28, center=True)
        self.text(s, "复活机会已耗尽，本轮远征结束。", (W // 2, 294), MUTED,
                  self.font14, center=True)
        self.ui_button(s, "run_again", pygame.Rect(W // 2 - 150, 390, 300, 52), "重新开始",
                       RED)


    def draw_assembly(self):
        self.ui_buttons = []
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
        self.text(s, "仓库：无限", (380, 8), GREEN, self.font14)
        if self.run:
            self.text(s, f"货币 {self.run['currency']} · ESC 返回地图", (380, 30),
                      (255, 210, 90), self.font11)
            has_broken = bool(self.broken)
            col = RED if has_broken else (55, 65, 74)
            pygame.draw.rect(s, (28, 18, 23) if has_broken else (17, 20, 24), self.repair_rect)
            pygame.draw.rect(s, col, self.repair_rect, 1)
            self.text(s, f"修复 BROKEN ×{len(self.broken)}",
                      (self.repair_rect.centerx, self.repair_rect.centery - 7),
                      col if has_broken else DIM, self.font11, center=True)
            cost = self.broken_cost(self.broken[0]) if has_broken else 0
            self.text(s, f"{cost} 货币" if has_broken else "背包为空",
                      (self.repair_rect.centerx, self.repair_rect.centery + 9),
                      (255, 190, 120) if has_broken else (60, 70, 78), self.font11, center=True)
        else:
            self.text(s, "先装配，再进入战斗", (380, 30), DIM, self.font11)
        # recommended deck / return to map
        pygame.draw.rect(s, (34, 29, 15) if not self.run else (15, 30, 40),
                         self.recommended_rect)
        pygame.draw.rect(s, (255, 205, 100) if not self.run else (80, 190, 220),
                         self.recommended_rect, 2)
        if self.run:
            self.text(s, "返回地图", (self.recommended_rect.centerx, self.recommended_rect.centery - 7),
                      (150, 235, 255), self.font16, center=True)
            self.text(s, "保留当前构筑", (self.recommended_rect.centerx, self.recommended_rect.centery + 10),
                      (100, 155, 170), self.font11, center=True)
        else:
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
        self.text(s, f"清除 {self.run.get('necro_cost', 3)}/格" if self.run else "无自动整理",
                  (LEFT.right - 100, 80), MUTED if self.run else DIM, self.mono10)

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
        p1, p2 = self.plus_tokens.get((key, 1), 0), self.plus_tokens.get((key, 2), 0)
        if p1 or p2:
            self.text(s, f"+{p1} ++{p2}", (r.x + 12, r.y + 34), (255, 210, 100), self.mono10)
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
        if self.tutorial:
            if button == 1:
                self.tutorial = None
            return
        if self.scene != "assembly":
            if button == 1:
                for key, rect in self.ui_buttons:
                    if rect.collidepoint(pos):
                        self.handle_ui_action(key)
                        return
            return
        self.handle_assembly_click(pos, button)

    def handle_assembly_click(self, pos, button=1):
        self.mouse = pos
        if button == 1 and self.run and self.repair_rect.collidepoint(pos):
            self.repair_next_broken()
            return
        if button == 1 and self.recommended_rect.collidepoint(pos):
            if self.run:
                self.scene = "map"
            else:
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
                    cost = self.run.get("necro_cost", 3) if self.run else 0
                    if self.run and self.run["currency"] < cost:
                        self.message = f"清除坏死需要 {cost} 货币"
                        self.message_t = 1.8
                        self.audio.play("invalid")
                        return
                    if self.run:
                        self.run["currency"] -= cost
                        self.run["necro_cost"] = cost + 2
                        self.tutorial_once("necro_clear", "清除坏死", [
                            "清除坏死会消耗货币。",
                            "同一次构筑中每清一格都会涨价。",
                            "离开构筑后，下一次从 3 货币/格重新开始。",
                        ])
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
    def run_loop(self):
        running = True
        frames = 0
        while running:
            dt = self.clock.tick(60) / 1000.0
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    running = False
                elif e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_ESCAPE:
                        if self.tutorial:
                            self.tutorial = None
                        elif self.detail_key:
                            self.close_detail()
                        elif self.drag:
                            self.cancel_drag()
                        elif self.scene == "assembly" and self.run:
                            self.scene = "map"
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
                        if self.scene == "assembly":
                            self.start_requested = True
                    elif e.key == pygame.K_F6:
                        if self.scene == "assembly" and not self.run:
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
                if self.scene == "assembly":
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
    App(windowed=windowed, shot=shot, size=size).run_loop()


if __name__ == "__main__":
    main()
