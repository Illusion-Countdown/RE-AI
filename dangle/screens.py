# -*- coding: utf-8 -*-
"""标题、选身体、重构奖励、暂停与结局界面。"""
import math
import random
import pygame
from .const import *
from .content import BODIES, MODULES, ROOMS
from .battle import TOOL_NAMES


# ================================================================ 背景图
class TitleBG:
    def __init__(self):
        self.t = 0.0
        self.nodes = []
        for i in range(16):
            self.nodes.append({
                "x": random.uniform(60, W - 60),
                "y": random.uniform(60, H - 60),
                "vx": random.uniform(-12, 12),
                "vy": random.uniform(-12, 12),
                "r": random.uniform(2.5, 7),
                "c": random.choice([CYAN, CYAN, PURPLE, DIM2]),
                "ph": random.uniform(0, 6.28),
            })
        self.edges = [(i, random.randrange(len(self.nodes))) for i in range(10)]

    def update(self, dt):
        self.t += dt
        for n in self.nodes:
            n["x"] += n["vx"] * dt
            n["y"] += n["vy"] * dt
            if n["x"] < 40 or n["x"] > W - 40:
                n["vx"] *= -1
            if n["y"] < 40 or n["y"] > H - 40:
                n["vy"] *= -1

    def draw(self, screen):
        for a, b in self.edges:
            na, nb = self.nodes[a % len(self.nodes)], self.nodes[b % len(self.nodes)]
            d = math.hypot(na["x"] - nb["x"], na["y"] - nb["y"])
            if d > 460:
                continue
            k = 1 - d / 460
            pygame.draw.line(screen, mix(BG, CYAN, 0.18 + 0.25 * k),
                             (na["x"], na["y"]), (nb["x"], nb["y"]), 1)
        for n in self.nodes:
            p = 0.5 + 0.5 * math.sin(self.t * 1.6 + n["ph"])
            glow(screen, n["x"], n["y"], 16 + p * 8, n["c"], 0.20)
            pygame.draw.circle(screen, n["c"], (int(n["x"]), int(n["y"])),
                               int(n["r"]))


# ================================================================ 通用
BODY_CARD_Y = 176
BODY_CARD_W = 330
BODY_CARD_H = 566
BODY_CARD_GAP = 28

REWARD_Y = 224
REWARD_CW = 372
REWARD_CH = 356
REWARD_GAP = 28


def body_card_rect(i):
    return pygame.Rect(84 + i * (BODY_CARD_W + BODY_CARD_GAP), BODY_CARD_Y,
                       BODY_CARD_W, BODY_CARD_H)


def reward_card_rect(i, n=3):
    total = REWARD_CW * n + REWARD_GAP * (n - 1)
    sx = (W - total) // 2
    return pygame.Rect(sx + i * (REWARD_CW + REWARD_GAP), REWARD_Y,
                       REWARD_CW, REWARD_CH)


def card(screen, rect, color, hover, t, seed=0):
    rr = pygame.Rect(rect)
    if hover:
        rr.y -= 6
    sh = pygame.Surface((rr.w + 40, rr.h + 40), pygame.SRCALPHA)
    s2 = pygame.Surface((rr.w, rr.h), pygame.SRCALPHA)
    pygame.draw.rect(s2, (0, 0, 0, 110), (0, 0, rr.w, rr.h), border_radius=8)
    screen.blit(s2, (rr.x + 6, rr.y + 10))
    fill = (15, 19, 26) if not hover else (20, 26, 36)
    pygame.draw.rect(screen, fill, rr, border_radius=8)
    line = mix(color, WHITE, 0.15) if hover else dim(color, 0.45)
    pygame.draw.rect(screen, line, rr, 2 if hover else 1, border_radius=8)
    # 顶部色条
    pygame.draw.rect(screen, color, (rr.x + 1, rr.y + 1, rr.w - 2, 3),
                     border_radius=0)
    if hover:
        glow(screen, rr.centerx, rr.y + 2, rr.w * 0.55, color, 0.12)
        bracket(screen, rr, color, 16, 2, 200)
    return rr


def body_glyph(screen, kind, cx, cy, size, color):
    if kind == "list":
        for i in range(4):
            x = cx - size * 0.75 + i * size * 0.5
            pygame.draw.circle(screen, color, (int(x), int(cy)), int(size * 0.16), 2)
            if i < 3:
                pygame.draw.line(screen, color, (x + size * 0.16, cy),
                                 (x + size * 0.34, cy), 2)
    elif kind == "array":
        n = 5
        w = size * 0.9
        for i in range(n):
            r = pygame.Rect(cx - w / 2 + i * w / n, cy - size * 0.3, w / n - 4,
                            size * 0.6)
            pygame.draw.rect(screen, color, r, 2, border_radius=2)
        pygame.draw.line(screen, color, (cx - w / 2 - 10, cy + size * 0.45),
                         (cx + w / 2 + 10, cy + size * 0.45), 1)
    elif kind == "hash":
        for i in range(4):
            for j in range(3):
                x = cx - size * 0.45 + i * size * 0.3
                y = cy - size * 0.3 + j * size * 0.3
                if (i + j) % 3 == 0:
                    pygame.draw.rect(screen, color, (x, y, size * 0.2, size * 0.2))
                else:
                    pygame.draw.rect(screen, dim(color, 0.6),
                                     (x, y, size * 0.2, size * 0.2), 1)
    else:
        pts = [(cx, cy - size * 0.42), (cx - size * 0.42, cy + size * 0.1),
               (cx + size * 0.42, cy + size * 0.1), (cx - size * 0.22, cy + size * 0.42),
               (cx + size * 0.22, cy + size * 0.42)]
        for a, b in ((0, 1), (0, 2), (1, 3), (2, 4)):
            pygame.draw.line(screen, dim(color, 0.7), pts[a], pts[b], 1)
        for p in pts:
            pygame.draw.circle(screen, color, (int(p[0]), int(p[1])), 4)


# ================================================================ 标题
def draw_title(screen, app):
    bg = app.title_bg
    screen.fill(BG)
    bg.draw(screen)
    # 上下渐暗
    ov = pygame.Surface((W, H), pygame.SRCALPHA)
    for i in range(0, H, 2):
        a = int(120 * abs(i / H - 0.5) ** 1.4)
        pygame.draw.line(ov, (5, 7, 10, a), (0, i), (W, i))
    screen.blit(ov, (0, 0))

    # 左侧装饰线
    pygame.draw.line(screen, dim(CYAN, 0.5), (96, 168), (96, 700), 1)
    for y in (168, 700):
        pygame.draw.circle(screen, CYAN, (96, y), 3)
    for i in range(12):
        pygame.draw.line(screen, dim(CYAN, 0.25), (90, 200 + i * 40),
                         (96, 200 + i * 40), 1)

    x = 140
    blit_text(screen, "CS 概念对抗四部曲 · 之二", (x, 150), 11, DIM, mono=False)
    blit_text(screen, "ROGUELIKE / TOPOLOGY / REAL-TIME", (x, 172), 9, dim(CYAN, 0.7),
              mono=True)
    # 大标题
    t = bg.t
    blit_text(screen, "悬垂", (x + 10, 222), 128, with_alpha(CYAN, 40), bold=True)
    blit_text(screen, "悬垂", (x, 222), 128, WHITE, bold=True)
    # 英文
    letters = "DANGLING"
    lx = x + 4
    for ch in letters:
        blit_text(screen, ch, (lx, 366), 30, CYAN, mono=True, bold=True)
        lx += text_w(ch, 30, True, True) + 8
    pygame.draw.line(screen, dim(CYAN, 0.5), (x + 4, 410), (lx, 410), 1)
    blit_text(screen, "DANG LING · 悬空指针", (x + 4, 418), 10, dim(DIM, 0.8), mono=True)

    blit_text(screen, "你操作的从来不是物体，是引用。", (x + 4, 456), 22, (206, 220, 236))
    blit_text(screen, "击杀不是清零血量，是让引用计数归零。", (x + 4, 492), 14, DIM)
    blit_text(screen, "在 GC 停顿的那 2 秒里，整张图属于你。", (x + 4, 516), 14, dim(CYAN, 0.85))

    # 关键词
    kw = ["LINK", "UNLINK", "WEAK", "ALIAS", "CAST", "MOVE"]
    kx = x + 4
    for i, k in enumerate(kw):
        w = text_w(k, 11, False, True) + 18
        r = pygame.Rect(kx, 548, w, 24)
        pygame.draw.rect(screen, (13, 18, 25), r, border_radius=3)
        pygame.draw.rect(screen, dim(CYAN, 0.35), r, 1, border_radius=3)
        blit_text(screen, k, r.center, 11, dim(CYAN, 0.9), anchor="center", mono=True)
        kx += w + 8

    # 进入
    blink = (math.sin(t * 4) + 1) / 2
    r = pygame.Rect(x + 4, 620, 260, 46)
    pygame.draw.rect(screen, (16, 22, 30), r, border_radius=4)
    pygame.draw.rect(screen, mix(CYAN, WHITE, 0.2), r, 1, border_radius=4)
    blit_text(screen, "ENTER  进入引用图", (r.centerx, r.centery), 15,
              mix(WHITE, CYAN, 0.25 + 0.4 * blink), anchor="center", bold=True)
    blit_text(screen, "F11 全屏 · M 静音 · 建议戴耳机", (x + 4, 682), 10, dim(DIM, 0.7))

    # 右侧实时演示图
    draw_title_demo(screen, app)

    blit_text(screen, "DEMO BUILD 1.0 · pygame", (W - 24, H - 30), 10,
              dim(DIM, 0.6), anchor="bottomright", mono=True)


DEMO_NODES = [
    # (x, y, kind, name)
    (1230, 250, "MINION", "0x1A"),
    (1390, 330, "SENTINEL", "0x2C"),
    (1150, 400, "MINION", "0x2D"),
    (1310, 500, "BOMB", "0x3F"),
    (1430, 620, "MINION", "0x4A"),
]
DEMO_EDGES = [(0, 1), (1, 2), (3, 4), (0, 2)]


def draw_title_demo(screen, app):
    t = app.title_bg.t
    cx, cy = 1290, 420
    # 外框
    r = pygame.Rect(1070, 190, 430, 520)
    pygame.draw.rect(screen, (10, 14, 20), r, border_radius=6)
    pygame.draw.rect(screen, dim(CYAN, 0.3), r, 1, border_radius=6)
    bracket(screen, r, dim(CYAN, 0.6), 14, 1)
    blit_text(screen, "LIVE GRAPH", (r.x + 14, r.y + 10), 9, dim(CYAN, 0.7), mono=True)
    # 根节点
    rootx, rooty = 1285, 620
    pygame.draw.circle(screen, (60, 76, 92), (rootx, rooty), 4)
    for i, (x, y, kind, name) in enumerate(DEMO_NODES):
        if i < len(DEMO_EDGES) or True:
            pass
    # 边
    for a, b in DEMO_EDGES:
        x1, y1 = DEMO_NODES[a][0], DEMO_NODES[a][1]
        x2, y2 = DEMO_NODES[b][0], DEMO_NODES[b][1]
        pygame.draw.line(screen, dim(CYAN, 0.22), (x1, y1), (x2, y2), 4)
        pygame.draw.line(screen, dim(CYAN, 0.65), (x1, y1), (x2, y2), 1)
    # 节点
    for i, (x, y, kind, name) in enumerate(DEMO_NODES):
        col = {"MINION": RED, "SENTINEL": AMBER, "BOMB": GOLD}[kind]
        ph = t * 1.5 + i
        glow(screen, x, y, 44 + math.sin(ph) * 6, col, 0.22)
        rad = {"MINION": 24, "SENTINEL": 30, "BOMB": 22}[kind]
        if kind == "SENTINEL":
            pts = hex_points(x, y, rad, math.pi / 6)
            pygame.draw.polygon(screen, (26, 20, 12), pts)
            pygame.draw.polygon(screen, col, pts, 2)
        elif kind == "BOMB":
            pts = hex_points(x, y, rad, math.pi / 6)
            pygame.draw.polygon(screen, (26, 22, 10), pts)
            pygame.draw.polygon(screen, GOLD, pts, 2)
        else:
            pygame.draw.circle(screen, (20, 14, 18), (x, y), rad)
            pygame.draw.circle(screen, col, (x, y), rad, 2)
        # refcount 环
        rc = [1, 1, 2, 1, 2][i]
        for k in range(rc):
            a0 = -math.pi / 2 + k * 0.8
            pygame.draw.arc(screen, CYAN, (x - rad - 6, y - rad - 6,
                                           (rad + 6) * 2, (rad + 6) * 2),
                            a0, a0 + 0.5, 2)
        blit_text(screen, name, (x, y + rad + 6), 9, dim(col, 0.8), anchor="midtop", mono=True)
    # 玩家
    px, py = 1200, 660
    pulse = 0.5 + 0.5 * math.sin(t * 3)
    glow(screen, px, py, 40, CYAN, 0.3 + pulse * 0.15)
    pts = [(px, py - 14), (px + 12, py), (px, py + 14), (px - 12, py)]
    pygame.draw.polygon(screen, (10, 24, 30), pts)
    pygame.draw.polygon(screen, CYAN, pts, 2)
    # 一条正在剪辑的边
    k = (t * 0.35) % 1.0
    x1, y1 = DEMO_NODES[0][0], DEMO_NODES[0][1]
    x2, y2 = DEMO_NODES[1][0], DEMO_NODES[1][1]
    ex = x1 + (x2 - x1) * k
    ey = y1 + (y2 - y1) * k
    glow(screen, ex, ey, 22, WHITE, 0.5 + 0.5 * math.sin(t * 12))
    pygame.draw.circle(screen, WHITE, (int(ex), int(ey)), 3)
    blit_text(screen, "CUT", (ex + 10, ey - 16), 9, WHITE, mono=True)
    # 状态
    blit_text(screen, f"refcount  {3 - int(t * 0.4) % 3}", (r.x + 14, r.bottom - 46), 10,
              dim(DIM, 0.8), mono=True)
    blit_text(screen, "GC in  12.0s", (r.x + 14, r.bottom - 30), 10, dim(CYAN, 0.7), mono=True)


# ================================================================ 选身体
def draw_body_select(screen, app):
    screen.fill(BG)
    for i in range(0, H, 3):
        pygame.draw.line(screen, (12, 15, 21), (0, i), (W, i))
    blit_text(screen, "选择你的身体", (W // 2, 54), 34, WHITE, anchor="center", bold=True)
    blit_text(screen, "你的数据结构 = 你的移动方式、脆弱点和灾难。",
              (W // 2, 102), 13, DIM, anchor="center")
    blit_text(screen, "CHOOSE YOUR BODY // 4 OPTIONS", (W // 2, 126), 9,
              dim(CYAN, 0.6), anchor="center", mono=True)

    hint = BODIES[app.body_idx]
    for i, bd in enumerate(BODIES):
        r = body_card_rect(i)
        hov = (i == app.body_idx)
        rr = card(screen, r, bd["color"], hov, app.t)
        blit_text(screen, bd["en"], (rr.x + 20, rr.y + 20), 9, dim(bd["color"], 0.75), mono=True)
        blit_text(screen, bd["name"], (rr.x + 20, rr.y + 36), 32, bd["color"], bold=True)
        # 图形
        glyph_r = pygame.Rect(rr.x + 20, rr.y + 92, rr.w - 40, 110)
        pygame.draw.rect(screen, (10, 13, 19), glyph_r, border_radius=4)
        pygame.draw.rect(screen, dim(bd["color"], 0.25), glyph_r, 1, border_radius=4)
        body_glyph(screen, bd["id"], glyph_r.centerx, glyph_r.centery, 80, bd["color"])
        # 数值
        y = glyph_r.bottom + 14
        blit_text(screen, "HP", (rr.x + 20, y), 10, DIM, mono=True)
        blit_text(screen, str(bd["hp"]), (rr.x + 56, y - 2), 12, WHITE, mono=True)
        blit_text(screen, "SPD", (rr.x + 112, y), 10, DIM, mono=True)
        blit_text(screen, str(bd["speed"]), (rr.x + 152, y - 2), 12, WHITE, mono=True)
        blit_text(screen, "SLICE", (rr.x + 212, y), 10, DIM, mono=True)
        blit_text(screen, f"{bd['slices']} / {bd['regen']:.2f}s", (rr.x + 258, y - 1), 10,
                  WHITE, mono=True)
        y += 24
        for name, val in bd["stats"].items():
            blit_text(screen, name, (rr.x + 20, y + 1), 10, DIM)
            for k in range(5):
                cc = bd["color"] if k < val else (34, 40, 50)
                pygame.draw.rect(screen, cc, (rr.x + 64 + k * 17, y + 2, 13, 7))
            y += 18
        # 被动
        y += 2
        pygame.draw.line(screen, dim(bd["color"], 0.3), (rr.x + 20, y),
                         (rr.right - 20, y), 1)
        y += 10
        blit_text(screen, "被动 PASSIVE", (rr.x + 20, y), 9, dim(bd["color"], 0.85), mono=True)
        y += 16
        y = wrap_text(screen, bd["passive"], (rr.x + 20, y), rr.w - 40, 11,
                      (176, 190, 208), max_lines=3)
        y += 10
        blit_text(screen, "灾难 DISASTER", (rr.x + 20, y), 9, dim(RED, 0.9), mono=True)
        y += 16
        y = wrap_text(screen, bd["disaster"], (rr.x + 20, y), rr.w - 40, 11,
                      (190, 150, 156), max_lines=3)
        # 风味
        pygame.draw.line(screen, dim(bd["color"], 0.18), (rr.x + 20, rr.bottom - 62),
                         (rr.right - 20, rr.bottom - 62), 1)
        blit_text(screen, "“" + bd["flavor"] + "”", (rr.x + 20, rr.bottom - 52), 10,
                  dim(bd["color"], 0.6))
        if hov:
            blit_text(screen, "SELECTED", (rr.right - 20, rr.y + 20), 9, bd["color"],
                      anchor="topright", mono=True, bold=True)

    blit_text(screen, "← → 或 1-4 切换 · ENTER 确认 · ESC 返回标题",
              (W // 2, 788), 12, DIM, anchor="center")
    blit_text(screen, "四种身体决定四种玩法：瞬移、站桩、洗牌、范围失效。",
              (W // 2, 818), 11, dim(DIM, 0.55), anchor="center")


def wrap_text(screen, s, pos, maxw, size, col, max_lines=99, lh=None):
    x, y = pos
    lines = []
    cur = ""
    for ch in s:
        if ch == "\n":
            lines.append(cur)
            cur = ""
            continue
        if ch in "，。、；：！？）》」』%":
            cur += ch
            continue
        if text_w(cur + ch, size) > maxw and cur:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    lh = lh or size + 5
    for i, ln in enumerate(lines[:max_lines]):
        blit_text(screen, ln, (x, y + i * lh), size, col)
    return y + min(len(lines), max_lines) * lh


# ================================================================ 奖励
def draw_reward(screen, app):
    screen.fill(BG)
    for i in range(0, H, 3):
        pygame.draw.line(screen, (12, 15, 21), (0, i), (W, i))
    run = app.run
    blit_text(screen, "重构", (W // 2, 62), 40, WHITE, anchor="center", bold=True)
    blit_text(screen, "ROOM CLEARED · 选择一项模块，它会改变你处理这张图的方式",
              (W // 2, 116), 13, DIM, anchor="center")
    blit_text(screen, f"ROOM {run.room_index + 1} 完成   ·   SCORE {run.score}",
              (W // 2, 142), 10, dim(CYAN, 0.7), anchor="center", mono=True)

    opts = app.reward_options
    for i, m in enumerate(opts):
        r = reward_card_rect(i, len(opts))
        hov = (i == app.reward_idx)
        rr = card(screen, r, m["color"], hov, app.t)
        blit_text(screen, m["tag"], (rr.x + 22, rr.y + 22), 10, dim(m["color"], 0.8))
        # 记号
        gc = pygame.Rect(rr.x + 22, rr.y + 48, rr.w - 44, 112)
        pygame.draw.rect(screen, (10, 13, 19), gc, border_radius=4)
        pygame.draw.rect(screen, dim(m["color"], 0.3), gc, 1, border_radius=4)
        draw_module_sigil(screen, m, gc.centerx, gc.centery, m["color"])
        blit_text(screen, m["name"], (rr.x + 22, gc.bottom + 16), 26, m["color"], bold=True)
        blit_text(screen, m["en"], (rr.x + 22, gc.bottom + 48), 10,
                  dim(m["color"], 0.65), mono=True)
        wrap_text(screen, m["desc"], (rr.x + 22, gc.bottom + 74), rr.w - 44, 12,
                  (186, 200, 218), max_lines=3)
        pygame.draw.line(screen, dim(m["color"], 0.18), (rr.x + 22, rr.bottom - 62),
                         (rr.right - 22, rr.bottom - 62), 1)
        blit_text(screen, "构筑提示", (rr.x + 22, rr.bottom - 52), 9, dim(m["color"], 0.7))
        wrap_text(screen, m.get("why", ""), (rr.x + 22, rr.bottom - 38), rr.w - 44, 10,
                  dim(DIM, 0.95), max_lines=2)
        if hov:
            blit_text(screen, "选择", (rr.right - 22, rr.y + 20), 11, m["color"],
                      anchor="topright", bold=True)

    # 当前构筑
    blit_text(screen, "当前构筑 / BUILD", (60, 648), 10, DIM, mono=True)
    x = 60
    if not run.modules:
        blit_text(screen, "（空）", (x, 668), 12, dim(DIM, 0.6))
    for m in run.modules:
        w = text_w(m["name"], 11) + 22
        r = pygame.Rect(x, 666, w, 24)
        pygame.draw.rect(screen, (14, 18, 25), r, border_radius=3)
        pygame.draw.rect(screen, dim(m["color"], 0.6), r, 1, border_radius=3)
        blit_text(screen, m["name"], r.center, 11, m["color"], anchor="center")
        x += w + 8
        if x > W - 200:
            break

    # 下一关预告
    nxt = ROOMS[run.room_index + 1] if run.room_index + 1 < len(ROOMS) else None
    if nxt:
        blit_text(screen, f"NEXT  {nxt['code']}  {nxt['title']}", (W - 60, 648), 10,
                  dim(AMBER, 0.8), anchor="topright", mono=True)
        blit_text(screen, nxt["cn"], (W - 60, 666), 12, DIM, anchor="topright")
    blit_text(screen, "← → 选择 · ENTER 确认", (W // 2, 760), 12, DIM, anchor="center")


def draw_module_sigil(screen, m, cx, cy, color):
    mid = m["id"]
    if mid in ("alias_e", "leak_cover"):
        pygame.draw.circle(screen, color, (cx - 22, cy), 20, 2)
        pygame.draw.circle(screen, color, (cx + 22, cy), 20, 2)
        blit_text(screen, "∞", (cx, cy), 26, color, anchor="center", bold=True)
    elif mid == "weak_f":
        for i in range(3):
            pygame.draw.line(screen, dim(color, 0.3 + i * 0.25),
                             (cx - 40 + i * 8, cy + 24), (cx + 40 - i * 8, cy - 24), 2)
    elif mid == "gc_bat":
        pygame.draw.rect(screen, color, (cx - 24, cy - 30, 48, 60), 2, border_radius=4)
        pygame.draw.line(screen, color, (cx - 10, cy - 38), (cx - 10, cy - 30), 3)
        pygame.draw.line(screen, color, (cx + 10, cy - 38), (cx + 10, cy - 30), 3)
        blit_text(screen, "GC", (cx, cy + 2), 16, color, anchor="center", mono=True, bold=True)
    elif mid == "heap_x":
        for i in range(3):
            pygame.draw.rect(screen, color if i < 2 else dim(color, 0.35),
                             (cx - 34 + i * 24, cy - 20, 18, 40), 2, border_radius=2)
    elif mid == "ptr_prec":
        pygame.draw.circle(screen, color, (cx, cy), 34, 2)
        for a in (0, 90, 180, 270):
            r = math.radians(a)
            pygame.draw.line(screen, color, (cx, cy),
                             (cx + math.cos(r) * 34, cy + math.sin(r) * 34), 2)
        pygame.draw.circle(screen, color, (cx, cy), 4)
    elif mid == "overclock":
        for i in range(12):
            a = i * math.tau / 12
            pygame.draw.line(screen, color,
                             (cx + math.cos(a) * 26, cy + math.sin(a) * 26),
                             (cx + math.cos(a) * 36, cy + math.sin(a) * 36), 2)
        blit_text(screen, "×1.25", (cx, cy), 13, color, anchor="center", mono=True)
    elif mid == "null_shield":
        pts = [(cx, cy - 34), (cx + 28, cy - 18), (cx + 22, cy + 22),
               (cx, cy + 34), (cx - 22, cy + 22), (cx - 28, cy - 18)]
        pygame.draw.polygon(screen, color, pts, 2)
        blit_text(screen, "NULL", (cx, cy), 11, color, anchor="center", mono=True)
    elif mid == "bomb_cache":
        pts = hex_points(cx, cy, 30, math.pi / 6)
        pygame.draw.polygon(screen, color, pts, 2)
        pygame.draw.circle(screen, color, (cx, cy), 6)
    elif mid == "dead_code":
        for i in range(4):
            pygame.draw.line(screen, dim(color, 0.35), (cx - 40, cy - 24 + i * 16),
                             (cx + 40, cy - 24 + i * 16), 2)
        pygame.draw.line(screen, color, (cx - 44, cy - 40), (cx + 44, cy + 34), 3)
    elif mid == "vamp":
        pygame.draw.circle(screen, color, (cx, cy), 22, 2)
        pygame.draw.polygon(screen, color, [(cx, cy - 4), (cx - 12, cy + 10),
                                            (cx, cy + 22), (cx + 12, cy + 10)])
    elif mid == "cascade":
        for i in range(3):
            pygame.draw.circle(screen, dim(color, 0.4 + i * 0.3), (cx - 30 + i * 30, cy), 12, 2)
    else:
        pygame.draw.circle(screen, color, (cx, cy), 28, 2)
        blit_text(screen, "?", (cx, cy), 22, color, anchor="center", bold=True)


# ================================================================ 暂停
def draw_pause(screen, app):
    ov = pygame.Surface((W, H), pygame.SRCALPHA)
    ov.fill((4, 6, 10, 205))
    screen.blit(ov, (0, 0))
    blit_text(screen, "PAUSED", (W // 2, 120), 46, WHITE, anchor="center", bold=True, mono=True)
    blit_text(screen, "已暂停 · 世界时间冻结", (W // 2, 180), 13, DIM, anchor="center")
    items = ["继续", "重新开始这一局", "返回标题", "退出游戏"]
    for i, it in enumerate(items):
        r = pygame.Rect(W // 2 - 170, 240 + i * 58, 340, 44)
        hov = (i == app.pause_idx)
        pygame.draw.rect(screen, (18, 24, 33) if hov else (11, 15, 21), r, border_radius=4)
        pygame.draw.rect(screen, CYAN if hov else dim(CYAN, 0.25), r, 1, border_radius=4)
        if hov:
            pygame.draw.rect(screen, CYAN, (r.x, r.y + 8, 2, r.h - 16))
        blit_text(screen, it, (r.centerx, r.centery), 15,
                  WHITE if hov else DIM, anchor="center", bold=hov)

    # 机制速查
    x = W // 2 + 230
    y = 232
    blit_text(screen, "机制速查 / REFERENCE", (x, y), 11, dim(CYAN, 0.8), mono=True)
    y += 26
    refs = [
        ("refcount", "= 入边中 STRONG 的数量。归零即被 GC 擦除。"),
        ("LINK", "从 SELF 出发的引用会「持有」目标：它停火，你受伤它分摊 40%。"),
        ("UNLINK", "1 时间片。剪断一条边，是最高效的击杀。"),
        ("WEAK", "不计入 refcount。破环，以及保留悬垂指针。"),
        ("ALIAS", "2 时间片 + 1 堆。共享血条，伤害与死亡同步。"),
        ("CAST", "3 时间片。NULL = 眩晕并让出边悬空；int = 截断行为。"),
        ("GC PAUSE", "周期性冻结全世界 2.2 秒，期间拓扑操作免费。"),
        ("UAF", "弱引用指向已回收槽位，新对象分配进来时被你劫持。"),
        ("LEAK", "直接写入击杀会留下泄漏：挡子弹，也逼近 OOM。"),
        ("OFF-BY-ONE", "走到竞技场边界外一格，可读写关卡元数据。"),
    ]
    for k, v in refs:
        blit_text(screen, k, (x, y), 10, CYAN, mono=True, bold=True)
        wrap_text(screen, v, (x + 96, y), 430, 10, (150, 166, 186), max_lines=2)
        y += 34
    blit_text(screen, "ESC 继续游戏", (W // 2, 760), 12, DIM, anchor="center")


# ================================================================ 结局
def draw_endgraph(screen, t, color, alive=True, seed=3):
    """结局背景里的引用图。"""
    rnd = random.Random(seed)
    pts = [(rnd.randint(150, W - 150), rnd.randint(120, H - 120)) for _ in range(16)]
    for i in range(13):
        a, b = pts[i], pts[(i * 5 + 3) % len(pts)]
        pygame.draw.line(screen, dim(color, 0.17), a, b, 1)
    for i, p in enumerate(pts):
        if i < 4 and not alive:
            continue
        c = color if i % 3 else dim(color, 0.6)
        glow(screen, p[0], p[1], 30, c, 0.13)
        pygame.draw.circle(screen, dim(c, 0.7), (int(p[0]), int(p[1])), 3 + i % 3, 1)
        if not alive and i % 4 == 0:
            pygame.draw.line(screen, dim(RED, 0.5),
                             (p[0] - 6, p[1] - 6), (p[0] + 6, p[1] + 6), 1)
            pygame.draw.line(screen, dim(RED, 0.5),
                             (p[0] + 6, p[1] - 6), (p[0] - 6, p[1] + 6), 1)


def draw_gameover(screen, app, t):
    screen.fill(BG)
    draw_endgraph(screen, t, RED, alive=False)
    # 故障条
    for i in range(10):
        yy = random.randint(0, H)
        hh = random.randint(2, 12)
        if random.random() < 0.28:
            s = pygame.Surface((W, hh), pygame.SRCALPHA)
            s.fill((255, 40, 60, random.randint(8, 28)))
            screen.blit(s, (random.randint(-30, 30), yy))
    ov = pygame.Surface((W, H), pygame.SRCALPHA)
    ov.fill((6, 4, 6, 120))
    screen.blit(ov, (0, 0))
    blit_text(screen, "SEGFAULT", (W // 2 + 3, 152), 96, (60, 8, 14), anchor="center",
              bold=True, mono=True)
    blit_text(screen, "SEGFAULT", (W // 2, 148), 96, RED, anchor="center", bold=True, mono=True)
    blit_text(screen, "核心已转储 / CORE DUMPED", (W // 2, 238), 16, dim(RED, 0.85),
              anchor="center", mono=True)
    blit_text(screen, "你的引用图在「" + app.run.body["name"] + "」上崩塌了。",
              (W // 2, 272), 14, DIM, anchor="center")
    blit_text(screen, "引用计数没有归零——归零的是你。", (W // 2, 296), 12,
              dim(DIM, 0.65), anchor="center")

    # 进度
    r = pygame.Rect(W // 2 - 380, 348, 760, 210)
    panel(screen, r, (12, 8, 11), (60, 26, 32), 6, 1, 230)
    bracket(screen, r, RED, 14, 2, 150)
    blit_text(screen, "RUN TERMINATED", (r.x + 18, r.y + 12), 10, dim(RED, 0.8), mono=True)
    blit_text(screen, f"ROOM {min(app.run.room_index + 1, 9)} / 9", (r.right - 18, r.y + 12),
              10, dim(RED, 0.8), anchor="topright", mono=True)
    draw_stats_block(screen, app, r.x + 24, r.y + 44, w=712)
    # 构筑
    blit_text(screen, "最终构筑 / FINAL BUILD", (r.x + 18, r.y + 156), 9, DIM, mono=True)
    x = r.x + 170
    if not app.run.modules:
        blit_text(screen, "（空）—— 你什么也没重构。", (x, r.y + 154), 10, dim(DIM, 0.6))
    for m in app.run.modules[:7]:
        w = text_w(m["name"], 10) + 18
        rr = pygame.Rect(x, r.y + 150, w, 22)
        pygame.draw.rect(screen, (18, 14, 18), rr, border_radius=3)
        pygame.draw.rect(screen, dim(m["color"], 0.55), rr, 1, border_radius=3)
        blit_text(screen, m["name"], rr.center, 10, m["color"], anchor="center")
        x += w + 6

    blink = 0.5 + 0.5 * math.sin(t * 4)
    blit_text(screen, "R  重新开始      ESC  返回标题", (W // 2, 620), 15,
              mix(WHITE, RED, 0.3 + 0.3 * blink), anchor="center")


def draw_victory(screen, app, t):
    screen.fill(BG)
    draw_endgraph(screen, t, GREEN, alive=True, seed=11)
    for i in range(0, H, 3):
        pygame.draw.line(screen, (12, 18, 20), (0, i), (W, i))
    ov = pygame.Surface((W, H), pygame.SRCALPHA)
    ov.fill((4, 10, 10, 110))
    screen.blit(ov, (0, 0))
    # 光
    k = 0.5 + 0.5 * math.sin(t * 1.5)
    glow(screen, W // 2, 200, 460, CYAN, 0.10)
    blit_text(screen, "TOPOLOGY REWRITTEN", (W // 2, 118), 62,
              mix(GREEN, WHITE, 0.25 + 0.2 * k), anchor="center", bold=True, mono=True)
    blit_text(screen, "引用图已重写", (W // 2, 190), 26, GREEN, anchor="center", bold=True)
    blit_text(screen, "GC BOSS 的引用计数归零了。世界没有被杀死，只是不再被引用。",
              (W // 2, 232), 13, DIM, anchor="center")

    r = pygame.Rect(W // 2 - 400, 280, 800, 300)
    panel(screen, r, (9, 16, 14), (30, 80, 60), 6, 1, 220)
    bracket(screen, r, GREEN, 16, 2, 160)
    blit_text(screen, "RUN COMPLETE", (r.x + 20, r.y + 12), 10, dim(GREEN, 0.85), mono=True)
    blit_text(screen, "9 / 9", (r.right - 20, r.y + 12), 10, dim(GREEN, 0.85),
              anchor="topright", mono=True)
    draw_stats_block(screen, app, r.x + 28, r.y + 44, w=744, cols=4)
    blit_text(screen, "最终构筑 / FINAL BUILD", (r.x + 20, r.y + 170), 9, DIM, mono=True)
    x = r.x + 20
    y = r.y + 188
    for i, m in enumerate(app.run.modules):
        w = text_w(m["name"], 11) + 22
        if x + w > r.right - 20:
            x = r.x + 20
            y += 30
        rr = pygame.Rect(x, y, w, 24)
        pygame.draw.rect(screen, (14, 20, 18), rr, border_radius=3)
        pygame.draw.rect(screen, dim(m["color"], 0.65), rr, 1, border_radius=3)
        blit_text(screen, m["name"], rr.center, 11, m["color"], anchor="center")
        x += w + 8
    blit_text(screen, app.run.body["name"] + "  ·  " + app.run.body["en"],
              (r.x + 20, r.bottom - 30), 11, app.run.body["color"])

    blink = 0.5 + 0.5 * math.sin(t * 3)
    blit_text(screen, "R  再来一局      ESC  返回标题", (W // 2, 640), 15,
              mix(WHITE, GREEN, 0.2 + 0.35 * blink), anchor="center")
    blit_text(screen, "你击败的不是血量，是引用。", (W // 2, 690), 12,
              dim(GREEN, 0.5), anchor="center")


def draw_stats_block(screen, app, x, y, w=760, cols=4):
    run = app.run
    st = run.stats
    rows = [
        ("SCORE", f"{run.score}", GOLD),
        ("GC 擦除", f"{st['gc']}", CYAN),
        ("直接击杀", f"{st['hp_kill']}", AMBER),
        ("UAF 劫持", f"{st['hijack']}", GREEN),
        ("泄漏制造", f"{st['leaks']}", DIM),
        ("剪断引用", f"{st['cuts']}", WHITE),
        ("别名", f"{st['alias']}", MAGENTA),
        ("受伤", f"{int(st['dmg'])}", RED),
    ]
    step = w // cols
    for i, (k, v, c) in enumerate(rows):
        col = i % cols
        row = i // cols
        bx = x + col * step
        by = y + row * 56
        blit_text(screen, k, (bx, by), 10, DIM)
        val = v
        blit_text(screen, val, (bx, by + 15), 25, c, bold=True, mono=True)
