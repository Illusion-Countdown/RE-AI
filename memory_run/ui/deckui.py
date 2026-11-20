# -*- coding: utf-8 -*-
"""整备界面：网格装箱、BENCH、画质档位、免费升级、修复与商店。"""
import math

import pygame

from memory_run.const import *
from memory_run.core.cards import CARD_DEFS, SHAPE_NAMES
from memory_run.ui.render import draw_card_mini, draw_wrap, wrap


class DeckEditor:
    def __init__(self, run):
        self.run = run
        self.held = None
        self.held_was_placed = False
        self.origin = None
        self.origin_anchor = None
        self.origin_rot = 0
        self.rot = 0
        self.msg = ""
        self.msg_t = 0.0
        self.grid_rect = pygame.Rect(30, 170, 400, 400)
        self.cell = 80
        self.tray_rects = []
        self.buttons = {}
        self.reg_rects = {}
        self.rd_rects = []
        self.tray_scroll = 0
        self.sell_rect = pygame.Rect(1320, 690, 220, 64)
        self._layout()

    def _layout(self):
        g = self.run.deck.grid
        self.cell = int(min(76, 560 / max(1, max(g.w, g.h))))
        self.grid_rect = pygame.Rect(40, 175, self.cell * g.w, self.cell * g.h)

    def say(self, s):
        self.msg = s
        self.msg_t = 2.4

    def _grid_cell(self, pos):
        if not self.grid_rect.collidepoint(pos):
            return None
        c = int((pos[0] - self.grid_rect.x) // self.cell)
        r = int((pos[1] - self.grid_rect.y) // self.cell)
        if 0 <= r < self.run.deck.grid.h and 0 <= c < self.run.deck.grid.w:
            return (r, c)
        return None

    def _pick(self, card):
        g = self.run.deck.grid
        self.held_was_placed = bool(card.anchor)
        self.origin = "grid" if card.anchor else "vault"
        self.origin_anchor = card.anchor
        self.origin_rot = card.rot
        if card.anchor:
            g.remove(card)
        elif card in self.run.deck.vault:
            self.run.deck.vault.remove(card)
        self.held = card
        self.rot = card.rot
        self.say(f"拿起 {card.name}：按住拖到格子，松开放下；R 旋转")

    def click(self, pos, button):
        run = self.run
        g = run.deck.grid
        if button == 3:
            if self.held:
                self._drop()
            return
        if button != 1:
            return
        if self.held is not None:
            return
        # 卡牌托盘
        for rect, card in self.tray_rects:
            if rect.collidepoint(pos) and card is not None:
                self._pick(card)
                return
        # 网格
        cell = self._grid_cell(pos)
        if cell is not None:
            card = g.at(cell[0], cell[1])
            if card is not None:
                self._pick(card)
            return
        # 未入网格的卡在右侧 CARD POOL 中点击/拖拽；这里只做说明
        # 画质档位
        for i, rect in enumerate(self.rd_rects):
            if rect.collidepoint(pos):
                run.set_rd(i)
                self.say(["高保真：100% 上限", "平衡：75% 上限",
                          "低码率：50% 上限"][i])
                return

    def _drop(self):
        card = self.held
        self.held = None
        self.origin = None
        if card is None:
            return
        if not self.run.deck.grid.auto_place(card):
            if card not in self.run.deck.vault:
                self.run.deck.vault.append(card)
        self.say("已放回")

    def _over_tray(self, pos):
        for rect, _card in self.tray_rects:
            if rect.collidepoint(pos):
                return True
        return pygame.Rect(690, 100, 580, 450).collidepoint(pos)

    def release(self, pos):
        """鼠标松开：落点决定放置/回仓库/回原位。"""
        if self.held is None:
            return
        card = self.held
        self.held = None
        g = self.run.deck.grid
        if self.sell_rect.collidepoint(pos):
            price = self.run.sell_card(card)
            self.say(f"卖出 {card.name}：+{price} 碎片")
            self.origin = None
            return
        cell = self._grid_cell(pos)
        if cell is not None:
            r, c = cell
            target = g.at(r, c)
            if target is not None and target is not card and \
                    target.key == card.key and not target.up and not card.up:
                tr, tc = target.anchor
                trot = target.rot
                g.remove(target)
                if target in self.run.deck.cards:
                    self.run.deck.cards.remove(target)
                card.up = True
                if g.place(card, tr, tc, trot):
                    self.say(f"{card.name} ++ 升级完成（拖动合成，不花碎片）")
                    self.origin = None
                    return
            if g.place(card, r, c, self.rot):
                self.say("已放置")
                self.origin = None
                return
            self.say("放不下：越界、重叠或坏死格")
        elif self._over_tray(pos):
            if card not in self.run.deck.vault:
                self.run.deck.vault.append(card)
            self.say("已放回仓库")
            self.origin = None
            return
        # 无效落点：网格牌回原位，仓库牌留在仓库
        if self.origin == "grid" and self.origin_anchor is not None:
            r, c = self.origin_anchor
            if g.place(card, r, c, self.origin_rot):
                self.say("放回原位")
                self.origin = None
                return
        if self.origin == "vault":
            if card not in self.run.deck.vault:
                self.run.deck.vault.append(card)
            self.say("已放回仓库")
        elif not g.auto_place(card):
            if card not in self.run.deck.vault:
                self.run.deck.vault.append(card)
            self.say("放不下，已进仓库")
        else:
            self.say("已自动放置")
        self.origin = None

    def key(self, key):
        if key == pygame.K_r and self.held:
            self.rot = 1 - self.rot
            self.say("旋转 90°")
        elif key == pygame.K_ESCAPE and self.held:
            self._drop()

    def auto_arrange(self):
        run = self.run
        g = run.deck.grid
        self.held = None
        self.origin = None
        for card in list(run.deck.cards):
            if card.anchor:
                g.remove(card)
        run.deck.vault = [c for c in run.deck.cards if not c.anchor]
        # 大卡优先，塞不下的进仓库
        for card in sorted(list(run.deck.cards),
                           key=lambda c: -(c.d["shape"][0] * c.d["shape"][1])):
            if g.auto_place(card):
                if card in run.deck.vault:
                    run.deck.vault.remove(card)
        # 至少留 1 格工作内存：把最小的一张放回仓库
        placed = [c for c in run.deck.cards if c.anchor]
        placed.sort(key=lambda c: c.d["shape"][0] * c.d["shape"][1])
        while g.free_count() < 1 and placed:
            card = placed.pop(0)
            g.remove(card)
            if card not in run.deck.vault:
                run.deck.vault.append(card)
        self.say("自动整理完成：大卡优先；至少留 1 格，放不下的进仓库")

    def draw(self, screen, t=0.0):
        run = self.run
        g = run.deck.grid
        self._layout()
        self.tray_rects = []
        self.buttons = {}
        self.reg_rects = {}
        self.rd_rects = []

        blit_text(screen, "整备 // LOADOUT", (40, 86), 28, WHITE, bold=True)
        blit_text(screen, f"{run.zone_name}  ·  下一步 {run.room['code'] if run.room else '—'}  ·  碎片 {run.shards}",
                  (40, 122), 13, DIM)
        blit_text(screen, "按住卡牌拖进网格，松开放下；拖到右侧 SELL 卖碎片；同名卡互拖免费 ++。",
                  (40, 144), 12, DIM2)

        self.draw_grid(screen, g)

        # ---------------------------------------------------- 右侧卡牌
        x = 690
        blit_text(screen, "CARD POOL", (x, 84), 10, DIM, mono=True)
        blit_text(screen, "点击拿起；金色边框是 ++", (x + 150, 84), 10, DIM2)
        cards = sorted(list(run.deck.cards), key=lambda c: (c.key, c.up, c.uid))
        cols = 5
        cw, ch = 108, 66
        for i, card in enumerate(cards):
            r = pygame.Rect(x + (i % cols) * (cw + 8),
                            108 + (i // cols) * (ch + 8), cw, ch)
            placed = bool(card.anchor)
            pygame.draw.rect(screen, (14, 18, 26), r, border_radius=5)
            pygame.draw.rect(screen, GOLD if card.up else
                             (dim(card.color, 0.8) if placed else (50, 42, 34)),
                             r, 2 if card is self.held else 1, border_radius=5)
            draw_card_mini(screen, pygame.Rect(r.x + 6, r.y + 6, 34, 34),
                           card.key, card.up, dimmed=not placed)
            blit_text(screen, card.name, (r.x + 44, r.y + 8), 11,
                      GOLD if card.up else (WHITE if placed else DIM))
            blit_text(screen, SHAPE_NAMES[card.d["shape"]],
                      (r.x + 44, r.y + 24), 9, DIM2, mono=True)
            blit_text(screen, "在场" if placed else "仓库",
                      (r.right - 5, r.bottom - 12), 8,
                      GREEN if placed else AMBER, anchor="topright")
            self.tray_rects.append((r, card))

        # ---------------------------------------------------- 未入网格
        y = 560
        bench = list(run.deck.vault)
        blit_text(screen, f"BENCH  {len(bench)} 张未入网格",
                  (x, y), 10, AMBER, mono=True)
        blit_text(screen, "拖进网格才会进入战斗牌堆", (x + 200, y), 10, DIM2)
        y += 24
        for i, card in enumerate(bench[:12]):
            col = CARD_DEFS[card.key]["color"]
            r = pygame.Rect(x + (i % 3) * 196, y + (i // 3) * 30, 188, 26)
            pygame.draw.rect(screen, dim(col, 0.12), r, border_radius=4)
            pygame.draw.rect(screen, col, r, 1, border_radius=4)
            blit_text(screen, f"{card.name}  {SHAPE_NAMES[card.d['shape']]}",
                      (r.x + 7, r.y + 5), 10, WHITE)
        if not bench:
            blit_text(screen, "所有卡都在卡组里。", (x + 8, y + 4), 11, DIM2)

        # ---------------------------------------------------- 画质档位
        y = 690
        blit_text(screen, "R-D WORK POINT", (x, y), 10, DIM, mono=True)
        labels = [("高保真", "100%", GREEN), ("平衡", "75%", AMBER),
                  ("低码率", "50%", RED)]
        for i, (nm, cap, col) in enumerate(labels):
            r = pygame.Rect(x + i * 150, y + 20, 138, 48)
            on = run.rd_choice == i
            pygame.draw.rect(screen, dim(col, 0.20 if on else 0.08), r,
                             border_radius=5)
            pygame.draw.rect(screen, col if on else (42, 50, 60), r,
                             2 if on else 1, border_radius=5)
            blit_text(screen, nm, (r.x + 10, r.y + 7), 14, WHITE)
            blit_text(screen, cap, (r.right - 10, r.y + 8), 14, col,
                      mono=True, anchor="topright")
            blit_text(screen, "画质上限", (r.x + 10, r.y + 28), 9, DIM2)
            self.rd_rects.append(r)

        # ---------------------------------------------------- 卖卡区
        self.sell_rect = pygame.Rect(1320, 690, 220, 64)
        hov = self.held is not None and self.sell_rect.collidepoint(
            pygame.mouse.get_pos())
        pygame.draw.rect(screen, (30, 18, 18) if hov else (16, 14, 18),
                         self.sell_rect, border_radius=6)
        pygame.draw.rect(screen, GOLD if hov else (72, 54, 44),
                         self.sell_rect, 2, border_radius=6)
        blit_text(screen, "SELL / 卖卡", (self.sell_rect.x + 12, self.sell_rect.y + 8),
                  11, GOLD, mono=True)
        if self.held:
            price = self.run.card_sell_price(self.held)
            blit_text(screen, f"拖到这里 +{price} 碎片",
                      (self.sell_rect.x + 12, self.sell_rect.y + 30), 12, WHITE)
        else:
            blit_text(screen, "拖不要的卡过来", (self.sell_rect.x + 12,
                                              self.sell_rect.y + 30), 11, DIM2)

        # ---------------------------------------------------- 数据
        self.draw_stats(screen, x, 770)
        self.draw_buttons(screen)

        if self.msg_t > 0:
            self.msg_t -= 1 / 60
            panel(screen, pygame.Rect(40, 800, 620, 48), (12, 16, 23),
                  (44, 60, 76), 5)
            blit_text(screen, self.msg, (56, 817), 14, WHITE)

        if self.held:
            mx, my = pygame.mouse.get_pos()
            self.draw_held(screen, mx, my)

    def draw_grid(self, screen, g):
        r = self.grid_rect
        panel(screen, r.inflate(12, 12), (9, 12, 18), (36, 48, 62), 4)
        for y in range(g.h):
            for x in range(g.w):
                cell = pygame.Rect(r.x + x * self.cell, r.y + y * self.cell,
                                   self.cell, self.cell)
                if (y, x) in g.dead:
                    pygame.draw.rect(screen, (52, 16, 22), cell)
                    for i in range(4):
                        pygame.draw.circle(
                            screen, (120, 36, 46),
                            (cell.centerx + ((i * 17) % 30) - 15,
                             cell.centery + ((i * 23) % 26) - 13), 2)
                else:
                    pygame.draw.rect(screen, (13, 18, 25), cell)
                pygame.draw.rect(screen, (36, 48, 62), cell, 1)
        # 卡片整体描边
        done = set()
        for card in g.all_cards():
            if card in done or not card.anchor:
                continue
            done.add(card)
            cells = card.cells()
            rows = [c[0] for c in cells]
            cols = [c[1] for c in cells]
            rr = pygame.Rect(r.x + min(cols) * self.cell,
                             r.y + min(rows) * self.cell,
                             (max(cols) - min(cols) + 1) * self.cell,
                             (max(rows) - min(rows) + 1) * self.cell)
            col = card.color
            surf = pygame.Surface(rr.size, pygame.SRCALPHA)
            surf.fill((*col, 44))
            screen.blit(surf, rr.topleft)
            pygame.draw.rect(screen, GOLD if card.up else col, rr, 2)
            corroded = g.card_corroded(card)
            label = card.name
            blit_text(screen, label, (rr.centerx, rr.centery - 7), 13,
                      GOLD if card.up else WHITE, bold=True, anchor="center")
            blit_text(screen, SHAPE_NAMES[card.d["shape"]],
                      (rr.centerx, rr.centery + 10), 8, dim(col, 0.9),
                      mono=True, anchor="center")
            if corroded:
                pygame.draw.line(screen, RED, (rr.x + 5, rr.y + 5),
                                 (rr.right - 5, rr.bottom - 5), 3)
                blit_text(screen, "CORRODED", (rr.centerx, rr.bottom + 4), 8,
                          RED, mono=True, anchor="midtop")
        # 悬停高亮
        cell = self._grid_cell(pygame.mouse.get_pos())
        if cell and self.held:
            r0, c0 = cell
            w, h = self.held.shape
            rr = pygame.Rect(r.x + c0 * self.cell, r.y + r0 * self.cell,
                             w * self.cell, h * self.cell)
            ok = g.can_place(self.held, r0, c0, self.rot)
            pygame.draw.rect(screen, GREEN if ok else RED, rr, 2)
            gl = pygame.Surface(rr.size, pygame.SRCALPHA)
            gl.fill((*GREEN, 40) if ok else (*RED, 40))
            screen.blit(gl, rr.topleft)

    def draw_held(self, screen, mx, my):
        card = self.held
        g = self.run.deck.grid
        cw, ch = card.shape
        cell = 46
        rr = pygame.Rect(mx - cw * cell / 2, my - ch * cell / 2,
                         cw * cell, ch * cell)
        col = card.color
        s = pygame.Surface(rr.size, pygame.SRCALPHA)
        s.fill((*col, 90))
        screen.blit(s, rr.topleft)
        pygame.draw.rect(screen, GOLD if card.up else col, rr, 2)
        blit_text(screen, card.name, rr.center, 14, WHITE, bold=True,
                  anchor="center")

    def draw_stats(self, screen, x, y):
        run = self.run
        g = run.deck.grid
        total = g.w * g.h
        occ = len(g.owner)
        dead = len(g.dead)
        free = g.free_count()
        q = run.deck.quality(0)
        blit_text(screen, f"GRID {g.w}×{g.h}", (x, y), 11, WHITE, mono=True)
        blit_text(screen, f"占用 {occ}  坏死 {dead}  空闲 {free}", (x + 130, y),
                  11, DIM, mono=True)
        blit_text(screen, f"CONFIRM FREE ≥ 3", (x + 430, y), 11,
                  GREEN if free >= 3 else RED, mono=True)
        y += 22
        qcol = GREEN if q >= 75 else (AMBER if q >= 50 else RED)
        bar(screen, pygame.Rect(x, y, 300, 10), q / 100, qcol,
            border=(40, 52, 64))
        blit_text(screen, f"BASELINE QUALITY {int(q)}%", (x + 310, y - 2), 11,
                  qcol, mono=True)

    def draw_buttons(self, screen):
        specs = [
            ("start", (40, 852, 230, 38), "开始战斗", CYAN),
            ("auto", (286, 852, 150, 38), "自动整理", DIM),
            ("repair", (452, 852, 150, 38), "修 1 格 (2)", GREEN),
            ("shop", (618, 852, 150, 38), "商店", GOLD),
            ("back", (784, 852, 130, 38), "返回", DIM),
        ]
        for key, rect, label, col in specs:
            r = pygame.Rect(*rect)
            pygame.draw.rect(screen, (14, 18, 26), r, border_radius=5)
            pygame.draw.rect(screen, col, r, 1, border_radius=5)
            blit_text(screen, label, r.center, 14, WHITE, anchor="center")
            self.buttons[key] = r


def draw_option_cards(screen, options, y=260, w=350, h=330, gap=36, start_x=None):
    rects = []
    if start_x is None:
        start_x = (W - (len(options) * w + (len(options) - 1) * gap)) // 2
    for i, key in enumerate(options):
        r = pygame.Rect(start_x + i * (w + gap), y, w, h)
        pygame.draw.rect(screen, (13, 17, 25), r, border_radius=8)
        d = CARD_DEFS[key]
        col = d["color"]
        pygame.draw.rect(screen, col, r, 2, border_radius=8)
        # 大形状
        gw, gh = d["shape"]
        cell = min(58, 240 / max(gw, gh))
        ox = r.centerx - gw * cell / 2
        oy = r.y + 34
        for yy in range(gh):
            for xx in range(gw):
                cr = pygame.Rect(ox + xx * cell, oy + yy * cell, cell - 4, cell - 4)
                pygame.draw.rect(screen, dim(col, 0.45), cr, border_radius=3)
                pygame.draw.rect(screen, col, cr, 1, border_radius=3)
        blit_text(screen, d["cn"], (r.centerx, r.y + 12), 24, WHITE,
                  bold=True, anchor="midtop")
        blit_text(screen, d["en"], (r.centerx, r.y + h - 118), 11,
                  dim(col, 0.9), mono=True, anchor="midtop")
        draw_wrap(screen, d["desc"], (r.x + 18, r.y + h - 96), 12, WHITE,
                  r.w - 36, 16)
        blit_text(screen, f"工作 {d['work']} · {SHAPE_NAMES[d['shape']]}",
                  (r.centerx, r.bottom - 24), 10, DIM, mono=True,
                  anchor="midtop")
        rects.append(r)
    return rects
