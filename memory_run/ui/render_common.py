# -*- coding: utf-8 -*-
"""战斗渲染：引用图、AI 娘、卡牌 HUD、画质降级与全屏特效。"""
import math
import random

import pygame

from memory_run.const import *
from memory_run.core.model import STRONG, WEAK, DANGLING
from memory_run.core.cards import CARD_DEFS, SHAPE_NAMES, RARITY_CN
from memory_run.content import GIRLS
from memory_run.ui.fx import ScreenPost, draw_rings, draw_sparks, draw_floaters

NODE_COLOR = {
    "MINION": RED, "SENTINEL": AMBER, "CYCLER": PURPLE,
    "ALLOCATOR": TEAL, "WARD": BLUE, "BOMB": GOLD, "PYLON": MAGENTA,
    "QUANTIZER": GREEN, "GLITCH": PURPLE, "TEAR": RED,
    "CRAWLER": AMBER, "ERASER": WHITE, "GC_CORE": MAGENTA,
    "AUDITOR": AMBER, "KERNEL": CYAN, "ROOT": (96, 112, 132),
    "PLAYER": CYAN,
}


def wrap(s, size, maxw, mono=False):
    """按像素宽度贪心换行，支持中文。"""
    lines = []
    cur = ""
    for ch in str(s):
        if ch == "\n":
            lines.append(cur)
            cur = ""
            continue
        test = cur + ch
        if text_w(test, size, mono=mono) > maxw and cur:
            lines.append(cur)
            cur = ch
        else:
            cur = test
    if cur:
        lines.append(cur)
    return lines


def draw_wrap(dst, s, pos, size, color, maxw, lh=None, bold=False,
              anchor="topleft", alpha=255):
    lh = lh or size + 6
    lines = wrap(s, size, maxw)
    x, y = pos
    for i, line in enumerate(lines):
        blit_text(dst, line, (x, y + i * lh), size, color, bold=bold,
                  anchor=anchor, alpha=alpha)
    return len(lines) * lh


def draw_card(screen, rect, key, up=False, selected=False, hover=False,
              alpha=255, compact=False):
    d = CARD_DEFS[key]
    col = d["color"]
    # 卡面先铺不透明深底，再压进卡牌自己的颜色；避免三张牌看起来都一样、像半透明
    fill = mix((12, 16, 24), col, 0.30 if selected else 0.20)
    if hover:
        fill = mix(fill, WHITE, 0.05)
    if up:
        fill = mix(fill, GOLD, 0.08)
    pygame.draw.rect(screen, fill, rect, border_radius=7)
    border = GOLD if up else (col if (selected or hover) else dim(col, 0.65))
    pygame.draw.rect(screen, border, rect, 2 if selected else 1, border_radius=7)
    # 顶部 / 左侧色条：让卡牌类型在不看文字时也能分辨
    pygame.draw.rect(screen, col, (rect.x + 2, rect.y + 2, rect.w - 4, 4),
                     border_radius=2)
    pygame.draw.rect(screen, col, (rect.x + 2, rect.y + 9, 3, rect.h - 18),
                     border_radius=1)
    if selected:
        glow(screen, rect.centerx, rect.centery, rect.w * 0.75, col, 0.35)
    # 形状缩略图
    w, h = d["shape"]
    cell = 8 if compact else 10
    ox = rect.x + 10
    oy = rect.y + 9
    for yy in range(h):
        for xx in range(w):
            r = pygame.Rect(ox + xx * (cell + 1), oy + yy * (cell + 1), cell, cell)
            pygame.draw.rect(screen, dim(col, 0.55), r, border_radius=2)
            pygame.draw.rect(screen, col, r, 1, border_radius=2)
    # 名称
    name = d["cn"] + ("++" if up else "")
    blit_text(screen, name, (rect.right - 9, rect.y + 9), 17,
              GOLD if up else WHITE, bold=True, anchor="topright", alpha=alpha)
    en = d["en"]
    blit_text(screen, en, (rect.right - 9, rect.y + 31), 10,
              dim(col, 0.9), mono=True, anchor="topright", alpha=alpha)
    # 目标 / 格数
    tag = {"edge": "划边", "two": "双目标", "node": "点对象",
           "area": "区域", "self": "自身", "dead": "修复"}[d["target"]]
    blit_text(screen, f"{tag} · {SHAPE_NAMES.get(d['shape'], '?')}格",
              (rect.x + 9, rect.bottom - 18), 11, DIM, alpha=alpha)
    if not compact:
        blit_text(screen, f"工作 {d['work']}", (rect.right - 9, rect.bottom - 18),
                  11, AMBER if d["work"] else DIM2, mono=True,
                  anchor="topright", alpha=alpha)


def draw_card_mini(screen, rect, key, up=False, dimmed=False):
    d = CARD_DEFS[key]
    col = dim(d["color"], 0.55) if dimmed else d["color"]
    pygame.draw.rect(screen, (14, 18, 26), rect, border_radius=5)
    pygame.draw.rect(screen, GOLD if up else col, rect, 1, border_radius=5)
    w, h = d["shape"]
    cell = min(8, (rect.w - 10) / max(1, w), (rect.h - 10) / max(1, h))
    ox = rect.centerx - w * cell / 2
    oy = rect.centery - h * cell / 2
    for yy in range(h):
        for xx in range(w):
            r = pygame.Rect(ox + xx * cell, oy + yy * cell, cell - 1, cell - 1)
            pygame.draw.rect(screen, dim(col, 0.5), r, border_radius=1)
            pygame.draw.rect(screen, col, r, 1, border_radius=1)


def draw_girl(screen, cx, cy, scale=1.0, color=CYAN, hair=(58, 178, 220),
              mood=0, t=0.0, portrait=False, alpha=255):
    """程序化 AI 娘：全息投影的几何少女，无外部素材。"""
    bob = math.sin(t * 2.0) * (3 if portrait else 1.5) * scale
    cx = int(cx)
    cy = int(cy + bob)
    s = scale
    if portrait:
        # 背后的全息圆环
        for i in range(3):
            r = (56 + i * 12) * s
            ring(screen, with_alpha(color, 30 - i * 8), cx, cy - 8 * s, r, 1)
        glow(screen, cx, cy, 150 * s, color, 0.18)
    # 头发外轮廓（三角/弧）
    hair_col = dim(hair, 0.85)
    pts = [(cx - 25 * s, cy - 18 * s), (cx - 18 * s, cy - 40 * s),
           (cx, cy - 48 * s), (cx + 18 * s, cy - 40 * s),
           (cx + 25 * s, cy - 18 * s), (cx + 18 * s, cy + 18 * s),
           (cx - 18 * s, cy + 18 * s)]
    pygame.draw.polygon(screen, dim(hair_col, 0.6), pts)
    pygame.draw.lines(screen, hair_col, True, pts, max(1, int(2 * s)))
    # 脸
    face = pygame.Rect(cx - 15 * s, cy - 26 * s, 30 * s, 30 * s)
    pygame.draw.ellipse(screen, (10, 13, 19), face)
    pygame.draw.ellipse(screen, with_alpha(color, 180), face, max(1, int(1.5 * s)))
    # 眼睛
    ey = cy - 14 * s
    ecol = color if mood >= 0 else AMBER
    for ex in (cx - 7 * s, cx + 7 * s):
        pygame.draw.ellipse(screen, ecol, (ex - 2.2 * s, ey - 4 * s, 4.4 * s, 7 * s))
        pygame.draw.ellipse(screen, WHITE, (ex - 1.1 * s, ey - 3 * s, 1.6 * s, 2.2 * s))
    # 嘴：情绪 0 平，-1 下弯，1 上弯
    if mood > 0:
        pygame.draw.arc(screen, ecol, (cx - 5 * s, cy - 4 * s, 10 * s, 8 * s),
                        3.5, 6.0, max(1, int(1.2 * s)))
    elif mood < 0:
        pygame.draw.arc(screen, AMBER, (cx - 5 * s, cy - 1 * s, 10 * s, 8 * s),
                        0.2, 2.8, max(1, int(1.2 * s)))
    else:
        pygame.draw.line(screen, dim(ecol, 0.8), (cx - 4 * s, cy - 1 * s),
                         (cx + 4 * s, cy - 1 * s), max(1, int(s)))
    # 耳机 / 数据接口
    pygame.draw.arc(screen, color, (cx - 23 * s, cy - 34 * s, 46 * s, 44 * s),
                    -0.7, 0.7, max(1, int(1.6 * s)))
    pygame.draw.circle(screen, ecol, (int(cx - 22 * s), int(cy - 8 * s)),
                       max(1, int(2.4 * s)))
    pygame.draw.circle(screen, ecol, (int(cx + 22 * s), int(cy - 8 * s)),
                       max(1, int(2.4 * s)))
    # 身体 / 悬浮衣领
    body = [(cx - 14 * s, cy + 20 * s), (cx, cy + 12 * s),
            (cx + 14 * s, cy + 20 * s), (cx + 9 * s, cy + 32 * s),
            (cx - 9 * s, cy + 32 * s)]
    pygame.draw.polygon(screen, dim(color, 0.18), body)
    pygame.draw.lines(screen, with_alpha(color, 170), True, body, max(1, int(1.5 * s)))
    # 浮游数据点
    for i in range(4 if portrait else 2):
        a = t * (1.1 + i * 0.2) + i * 1.7
        rr = (30 + i * 7) * s
        px = cx + math.cos(a) * rr
        py = cy - 6 * s + math.sin(a) * rr * 0.5
        pygame.draw.circle(screen, with_alpha(color, 120), (int(px), int(py)),
                           max(1, int(1.5 * s)))



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
