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

class HudMixin:
    def draw_ui(self, screen, b, mouse):
        self.draw_top(screen, b)
        self.draw_left(screen, b)
        self.draw_right(screen, b)
        self.draw_hand(screen, b)
        self.draw_banner(screen, b)
        if b.state == "intro":
            self.draw_intro(screen, b)

    def draw_top(self, screen, b):
        r = b.room
        zone = b.run.zone_name
        blit_text(screen, f"{zone}  /  {r['code']}  {r['title']}", (20, 16),
                  20, WHITE, bold=True)
        blit_text(screen, r.get("cn", ""), (20, 42), 13, DIM)
        # 中间：计时 / 房间进度
        blit_text(screen, "TIME", (630, 12), 10, DIM, mono=True, anchor="midtop")
        blit_text(screen, f"{int(b.time // 60):02d}:{int(b.time % 60):02d}",
                  (630, 26), 22, WHITE, mono=True, anchor="midtop")
        blit_text(screen, f"ROOM {b.run.step + 1:02d}/16", (700, 33), 11,
                  DIM, mono=True, anchor="midleft")
        # 画质
        q = b.quality()
        qcol = GREEN if q >= 75 else (AMBER if q >= 50 else RED)
        x = 840
        blit_text(screen, "QUALITY", (x, 10), 9, DIM, mono=True)
        bar(screen, pygame.Rect(x, 24, 190, 12), q / 100, qcol,
            border=(40, 52, 64))
        blit_text(screen, f"{int(q)}%", (x + 198, 22), 14, qcol, mono=True)
        # 工作内存
        free = max(1, b.deck.grid.free_count())
        blit_text(screen, "WORK MEM", (x, 42), 9, DIM, mono=True)
        bar(screen, pygame.Rect(x, 55, 190, 7), 1 - b.work_used / free,
            CYAN if b.work_used < free * 0.5 else AMBER)
        # 画质档位
        rd = ("HI-FI", "BALANCED", "LOW-BIT")[b.run.rd_choice]
        blit_text(screen, f"R-D {rd}", (x + 198, 48), 11, DIM, mono=True)
        # 级联
        cx = 1100
        blit_text(screen, "CASCADE", (cx, 10), 9, DIM, mono=True)
        bar(screen, pygame.Rect(cx, 25, 150, 10), min(1, b.erase_streak / 8),
            GREEN if b.erase_streak else (30, 40, 50))
        blit_text(screen, f"x{b.erase_streak}", (cx + 158, 22), 16,
                  GREEN if b.erase_streak else DIM, mono=True)
        blit_text(screen, f"HP {int(b.hp)}/{b.max_hp}", (cx, 45), 13,
                  RED if b.hp < b.max_hp * 0.35 else WHITE, mono=True)
        # 右侧 REF
        blit_text(screen, "REF", (1480, 12), 9, DIM, mono=True)
        for i in range(3):
            c = CYAN if i < b.run.refs else (30, 40, 50)
            pygame.draw.circle(screen, c, (1488 + i * 20, 43), 6)
        # Boss 血条
        boss = next((n for n in b.graph.nodes if n.alive and n.data.get("boss")), None)
        if boss:
            bw = 520
            br = pygame.Rect(W // 2 - bw // 2, 88, bw, 12)
            pygame.draw.rect(screen, (20, 14, 24), br.inflate(4, 4), border_radius=4)
            f = clamp(boss.hp / boss.max_hp, 0, 1)
            pygame.draw.rect(screen, MAGENTA, (br.x, br.y, max(1, int(br.w * f)), br.h),
                             border_radius=4)
            if boss.data.get("boss") == "gc" and boss.data.get("invuln"):
                blit_text(screen, "IMMUNE — 拆掉三根塔架", (W // 2, 108), 11,
                          AMBER, anchor="midtop")
            else:
                blit_text(screen, f"{boss.name}  {int(boss.hp)}/{int(boss.max_hp)}",
                          (W // 2, 108), 11, WHITE, anchor="midtop")

    def draw_left(self, screen, b):
        x = 20
        blit_text(screen, "PROCESS", (x, 90), 10, DIM, mono=True)
        hpcol = RED if b.hp < b.max_hp * 0.35 else GREEN
        blit_text(screen, f"{int(b.hp)}", (x, 106), 44, WHITE, bold=True, mono=True)
        blit_text(screen, f"/{b.max_hp}", (x + 88, 128), 14, DIM, mono=True)
        bar(screen, pygame.Rect(x, 158, 208, 8), b.hp / b.max_hp, hpcol)
        blit_text(screen, "REF", (x, 178), 9, DIM, mono=True)
        for i in range(3):
            c = CYAN if i < b.run.refs else (28, 36, 46)
            pygame.draw.rect(screen, c, (x + i * 26, 192, 18, 8), border_radius=2)
        # 画质
        q = b.quality()
        qcol = GREEN if q >= 75 else (AMBER if q >= 50 else RED)
        blit_text(screen, "QUALITY", (x, 216), 9, DIM, mono=True)
        bar(screen, pygame.Rect(x, 230, 208, 12), q / 100, qcol,
            border=(40, 52, 64))
        blit_text(screen, f"{int(q)}%  {['CLEAR','DITHER','BLOCKY','CRASH'][b.quality_band()]}",
                  (x, 246), 12, qcol, mono=True)
        # 工作内存
        free = max(1, b.deck.grid.free_count())
        blit_text(screen, "WORK MEMORY", (x, 270), 9, DIM, mono=True)
        blit_text(screen, f"{b.work_used:.0f} / {free}", (x + 208, 268), 13,
                  CYAN, mono=True, anchor="topright")
        bar(screen, pygame.Rect(x, 286, 208, 7),
            max(0.0, 1 - b.work_used / free),
            CYAN if b.work_used < free * 0.5 else AMBER)
        # 网格
        blit_text(screen, "MEMORY GRID", (x, 310), 9, DIM, mono=True)
        self.mini_grid(screen, pygame.Rect(x, 324, 208, 130), b.deck.grid)
        # 整个卡组（画质/抽牌池）
        blit_text(screen, "DECK / 抽牌池", (x, 470), 9, DIM, mono=True)
        y = 486
        pool = {}
        for c in b.deck.cards:
            if c.anchor:
                pool[c.key] = pool.get(c.key, 0) + 1
        for key, n in list(pool.items())[:6]:
            col = CARD_DEFS[key]["color"]
            pygame.draw.rect(screen, dim(col, 0.25), (x, y, 6, 20))
            blit_text(screen, CARD_DEFS[key]["cn"], (x + 14, y + 1), 15, WHITE)
            blit_text(screen, f"x{n}", (x + 208, y + 2),
                      13, col, mono=True, anchor="topright")
            y += 25
        # 模块
        y += 8
        blit_text(screen, "MODULES", (x, y), 9, DIM, mono=True)
        y += 16
        for m in b.run.modules[-5:]:
            blit_text(screen, m["name"], (x, y), 12, m["color"])
            y += 17
        if not b.run.modules:
            blit_text(screen, "—", (x, y), 12, DIM2)
        # Boss 规则
        if b.run.rules:
            y += 8
            blit_text(screen, "BOSS RULES", (x, y), 9, DIM, mono=True)
            y += 15
            for rr in b.run.rules[-3:]:
                blit_text(screen, rr["name"], (x, y), 11, GOLD)
                y += 15

    def mini_grid(self, screen, rect, grid):
        cw = rect.w / grid.w
        ch = rect.h / grid.h
        pygame.draw.rect(screen, (8, 10, 14), rect)
        for r in range(grid.h):
            for c in range(grid.w):
                cell = pygame.Rect(rect.x + c * cw + 1, rect.y + r * ch + 1,
                                   cw - 2, ch - 2)
                if (r, c) in grid.dead:
                    pygame.draw.rect(screen, (70, 20, 28), cell)
                    for _ in range(3):
                        pygame.draw.circle(screen, (130, 40, 50),
                                           (int(cell.centerx + random.randint(-4, 4)),
                                            int(cell.centery + random.randint(-3, 3))), 1)
                elif (r, c) in grid.owner:
                    card = grid.owner[(r, c)]
                    pygame.draw.rect(screen, dim(card.color, 0.45), cell)
                    pygame.draw.rect(screen, dim(card.color, 0.85), cell, 1)
                else:
                    pygame.draw.rect(screen, (16, 22, 30), cell, 1)
        pygame.draw.rect(screen, (40, 54, 70), rect, 1)

    def draw_right(self, screen, b):
        x = 1322
        girl = GIRLS[0]
        # 全息头像
        draw_girl(screen, x + 130, 196, 1.25, CYAN, girl["hair"],
                  mood=-1 if b.hp < b.max_hp * 0.3 or b.quality() < 25 else 0,
                  t=self.t, portrait=True)
        blit_text(screen, "小忆", (x + 130, 268), 20, CYAN, bold=True,
                  anchor="midtop")
        blit_text(screen, "DEEPSEEK / 向导", (x + 130, 292), 10, DIM,
                  mono=True, anchor="midtop")
        # 说话
        msg = b.toast_msg if b.toast_t > 0 else b.room.get("hint", "")
        if b.state == "clear":
            msg = "这一页内存干净了。"
        if b.state == "dead":
            msg = "进程没了。回滚快照，别停在原地。"
        if b.quality() < 50:
            msg = "画质在掉。工作内存、坏死格、还是卡太重？"
        box = pygame.Rect(x, 320, 264, 150)
        panel(screen, box, (12, 16, 23), (30, 42, 56), 5)
        draw_wrap(screen, msg, (box.x + 12, box.y + 12), 14, WHITE, box.w - 24, 20)
        # 卡牌详情
        card = None
        if b.aim:
            card = b.aim["card"]
        for rect, where, c in self.hand_rects:
            if c and rect.collidepoint(pygame.mouse.get_pos()):
                card = c
        if card:
            self.draw_card_detail(screen, card, pygame.Rect(x, 484, 264, 210))
        else:
            self.draw_room_info(screen, b, pygame.Rect(x, 484, 264, 210))
        # 操作
        blit_text(screen, "WASD 移动   SHIFT 冲刺   SPACE 规划", (x, 708), 10,
                  DIM, mono=True)
        blit_text(screen, "按住卡拖到目标 / 松手   右键 WRITE", (x, 724), 10,
                  DIM, mono=True)
        blit_text(screen, "Q 重抽   G 免费GC   R 坏死引爆   T 停火", (x, 740), 9,
                  DIM2, mono=True)

    def draw_card_detail(self, screen, card, rect):
        d = card.d
        panel(screen, rect, (13, 17, 25), dim(card.color, 0.7), 5)
        blit_text(screen, d["cn"] + ("++" if card.up else ""),
                  (rect.x + 12, rect.y + 10), 20, GOLD if card.up else WHITE,
                  bold=True)
        blit_text(screen, d["en"], (rect.right - 12, rect.y + 14), 10,
                  dim(card.color, 0.9), mono=True, anchor="topright")
        y = rect.y + 40
        blit_text(screen, f"{RARITY_CN[d['rarity']]} · {SHAPE_NAMES[d['shape']]} · 工作 {d['work']}",
                  (rect.x + 12, y), 11, DIM, mono=True)
        y += 24
        y += draw_wrap(screen, d["desc"], (rect.x + 12, y), 13, WHITE, rect.w - 24, 18)
        if card.up:
            y += 8
            blit_text(screen, "++", (rect.x + 12, y), 12, GOLD, bold=True)
            draw_wrap(screen, d["up"], (rect.x + 28, y), 12, GOLD, rect.w - 40, 17)
        y += 34
        blit_text(screen, f"目标：{ {'edge':'划一条边','two':'拖两个对象','node':'点一个对象','area':'点一块区域','self':'自己','dead':'自动修复'}[d['target']] }",
                  (rect.x + 12, y), 11, DIM2)

    def draw_room_info(self, screen, b, rect):
        panel(screen, rect, (12, 16, 23), (28, 38, 50), 5)
        blit_text(screen, "THIS ROOM", (rect.x + 12, rect.y + 10), 10, DIM, mono=True)
        y = rect.y + 30
        y += draw_wrap(screen, b.room.get("hint", ""), (rect.x + 12, y), 12,
                       WHITE, rect.w - 24, 17)
        y += 14
        if b.run.last_room:
            blit_text(screen, f"完美条件：无伤 / 画质≥75 / 无新坏死",
                      (rect.x + 12, y), 10, DIM2)
            y += 18
        blit_text(screen, f"卡组 {sum(1 for c in b.deck.cards if c.anchor)} 张  ·  重抽 {'已用' if b.redraw_used else '可用'}",
                  (rect.x + 12, y), 10, DIM2)
        y += 17
        blit_text(screen, f"洗回 {'已用' if b.reshuffled else '未用'}  ·  溢出 {len([c for c in b.hand.overflow if c])}/2",
                  (rect.x + 12, y), 10, DIM2)
