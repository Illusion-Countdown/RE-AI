# -*- coding: utf-8 -*-
"""战斗渲染：引用图、AI 娘、卡牌 HUD、画质降级与全屏特效。"""
import math
import random

import pygame

from .const import *
from .model import STRONG, WEAK, DANGLING
from .cards import CARD_DEFS, SHAPE_NAMES, RARITY_CN
from .content import GIRLS
from .fx import ScreenPost, draw_rings, draw_sparks, draw_floaters

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
    fill = (16, 20, 29) if not selected else (24, 32, 44)
    pygame.draw.rect(screen, fill, rect, border_radius=7)
    border = GOLD if up else (col if (selected or hover) else PANEL_LINE)
    pygame.draw.rect(screen, border, rect, 2 if selected else 1, border_radius=7)
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


class BattleRenderer:
    def __init__(self):
        self.post = ScreenPost()
        self.post.build(W, H)
        self.pixel_overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        for yy in range(0, H, 3):
            pygame.draw.line(self.pixel_overlay, (0, 0, 0, 55),
                             (0, yy), (W, yy), 1)
        for xx in range(0, W, 4):
            pygame.draw.line(self.pixel_overlay, (0, 0, 0, 28),
                             (xx, 0), (xx, H), 1)
        self.bg = self._make_bg()
        self.world = pygame.Surface((W, H), pygame.SRCALPHA)
        self.hand_rects = []
        self.card_at = None
        self.t = 0.0
        self.last_quality = 100
        self.trail = []

    def _make_bg(self):
        s = pygame.Surface((W, H), pygame.SRCALPHA)
        # 竞技场地板
        pygame.draw.rect(s, (8, 11, 16), ARENA)
        inner = PLAY.inflate(8, 8)
        pygame.draw.rect(s, (6, 8, 12), inner)
        # 网格
        step = 42
        for x in range(PLAY.x, PLAY.right + 1, step):
            pygame.draw.line(s, (16, 22, 30), (x, PLAY.y), (x, PLAY.bottom), 1)
        for y in range(PLAY.y, PLAY.bottom + 1, step):
            pygame.draw.line(s, (16, 22, 30), (PLAY.x, y), (PLAY.right, y), 1)
        # 斜向数据流
        for i in range(-6, 20):
            x = PLAY.x + i * 70
            pygame.draw.line(s, (10, 18, 24), (x, PLAY.y), (x + 170, PLAY.bottom), 1)
        # 边框
        pygame.draw.rect(s, (26, 36, 48), ARENA, 1)
        bracket(s, ARENA.inflate(-8, -8), (36, 52, 68), 22, 2)
        # 四角标记
        for x, y, txt in ((ARENA.x + 14, ARENA.y + 10, "MEM"),
                          (ARENA.right - 14, ARENA.y + 10, "0x00"),
                          (ARENA.x + 14, ARENA.bottom - 10, "REF"),
                          (ARENA.right - 14, ARENA.bottom - 10, "GC")):
            blit_text(s, txt, (x, y), 9, (40, 54, 68), mono=True,
                      anchor="topright" if x > W // 2 else "topleft")
        # 左侧 / 右侧底板
        panel(s, pygame.Rect(0, 72, 248, 714), (10, 13, 19), (24, 32, 43))
        panel(s, pygame.Rect(1308, 78, 292, 704), (10, 13, 19), (24, 32, 43))
        panel(s, pygame.Rect(0, 786, W, 114), (9, 12, 17), (26, 36, 48))
        # 顶栏底
        pygame.draw.rect(s, (8, 10, 15), (0, 0, W, 72))
        pygame.draw.line(s, (30, 42, 56), (0, 71), (W, 71))
        return s

    # ------------------------------------------------------------ 主绘制
    def draw(self, screen, b, mouse, dt=0.0):
        self.t += dt
        self.hand_rects = []
        self.card_at = None
        q = b.quality()
        self.last_quality = q

        self.world.fill((0, 0, 0, 0))
        self.world.blit(self.bg, (0, 0))
        ox, oy = b.fx.offset()
        old_clip = screen.get_clip()
        self.world.set_clip(ARENA)
        self.draw_world(self.world, b, (ox, oy + 12), mouse)
        self.world.set_clip(None)

        # 画质降级：世界先退化，UI 后画，保证文字高清
        band = b.quality_band()
        surf = self.world
        if band >= 1:
            factor = {1: 0.58, 2: 0.30, 3: 0.11}[band]
            size = (max(1, int(W * factor)), max(1, int(H * factor)))
            if band >= 3:
                # 最低画质：最近邻降采样，像素块要肉眼可见
                small = pygame.transform.scale(self.world, size)
            else:
                small = pygame.transform.smoothscale(self.world, size)
            surf = pygame.transform.scale(small, (W, H))
            if band >= 2:
                ov = pygame.Surface((W, H), pygame.SRCALPHA)
                ov.fill((10, 26, 24, 38 if band == 2 else 74))
                surf.blit(ov, (0, 0))
                self._tear(surf, band)
            if band >= 3:
                surf.blit(self.pixel_overlay, (0, 0))
                for _ in range(18):
                    rr = pygame.Rect(random.randint(0, W - 80),
                                     random.randint(ARENA.y, ARENA.bottom - 24),
                                     random.randint(18, 90), random.randint(2, 8))
                    pygame.draw.rect(surf, random.choice(
                        [(20, 40, 38), (8, 16, 20), (40, 30, 20)]), rr)
        screen.blit(surf, (0, 0))
        screen.set_clip(None)

        # 世界屏幕特效（扫描线 / 暗角 / 受击闪）
        self.post.draw(screen, b.fx)

        self.draw_ui(screen, b, mouse)
        self.draw_drag_ghost(screen, b)
        if band >= 1:
            self._quality_note(screen, b, q)

    def draw_drag_ghost(self, screen, b):
        if not getattr(b, "drag_active", False) or not b.aim:
            return
        card = b.aim["card"]
        mx, my = getattr(b, "mouse", pygame.mouse.get_pos())
        r = pygame.Rect(mx - 72, my - 94, 144, 82)
        draw_card(screen, r, card.key, card.up, selected=True, alpha=225)
        blit_text(screen, "松开放下", (r.centerx, r.y - 14), 10,
                  card.color, anchor="center", mono=True)

    def _tear(self, surf, band):
        n = 4 if band == 2 else 10
        for _ in range(n):
            y = random.randint(ARENA.y, ARENA.bottom - 20)
            h = random.randint(2, 10)
            dx = random.randint(-14, 14)
            try:
                strip = surf.subsurface((0, y, W, h)).copy()
                surf.blit(strip, (dx, y))
            except Exception:
                pass

    def _quality_note(self, screen, b, q):
        y = TOPBAR.bottom + 8
        txt = f"画质 {int(q)}%  负载 {len(b.deck.grid.owner) + len(b.deck.grid.dead)}/{b.deck.grid.w * b.deck.grid.h}  工作内存 {b.work_used:.0f}/{b.deck.grid.free_count()}"
        blit_text(screen, txt, (ARENA.right - 12, y), 12, AMBER,
                  mono=True, anchor="topright", shadow=2)

    # ------------------------------------------------------------ 世界
    def draw_world(self, surf, b, cam, mouse):
        ox, oy = cam
        # 内存尘埃：随战斗缓慢漂移，给空场地一点生命
        for i in range(26):
            px = PLAY.x + ((i * 191 + b.time * (9 + i % 4)) % PLAY.w)
            py = PLAY.bottom - ((b.time * (16 + i % 6) + i * 83) % PLAY.h)
            c = CYAN if i % 3 else PURPLE
            a = 24 + (i % 5) * 8
            pygame.draw.line(surf, with_alpha(c, a),
                             (px + ox, py + oy), (px + ox, py + oy + 4), 1)
        # 引用边：弱引用先画，强引用压在上面
        edges = sorted([e for e in b.graph.edges if e.alive],
                       key=lambda e: 0 if e.kind != STRONG else 1)
        for e in edges:
            if not e.src.alive or not e.dst.alive:
                continue
            self.draw_edge(surf, b, e, ox, oy)
        self.draw_alias_bonds(surf, b, ox, oy)
        # 悬垂 / 瞄准线
        self.draw_aim(surf, b, ox, oy, mouse)
        # 节点
        for n in b.graph.nodes:
            if not n.alive:
                continue
            self.draw_node(surf, b, n, ox, oy, n is b.hover_node)
        # 子弹
        for p in b.projectiles:
            x, y = p.x + ox, p.y + oy
            for k in (1, 2, 3):
                tx = p.x + ox - p.vx * 0.012 * k
                ty = p.y + oy - p.vy * 0.012 * k
                pygame.draw.circle(surf, with_alpha(p.color, 80 - k * 18),
                                   (int(tx), int(ty)), max(1, p.r - k // 2))
            glow(surf, x, y, p.r * 5, p.color, 0.55)
            pygame.draw.circle(surf, mix(p.color, WHITE, 0.35), (int(x), int(y)),
                               p.r)
            pygame.draw.circle(surf, WHITE, (int(x), int(y)), max(1, p.r // 2))
        # 特效
        b.fx.draw_world(surf, (ox, oy))
        draw_rings(surf, b.fx, (ox, oy))
        draw_sparks(surf, b.fx, (ox, oy))
        draw_floaters(surf, b.fx, (ox, oy))
        # 玩家
        self.draw_player(surf, b, ox, oy)

    def draw_edge(self, surf, b, e, ox, oy):
        pts = [(x + ox, y + oy) for x, y in e.points(20)]
        col = e.color
        weak = e.kind == WEAK
        if weak:
            # 弱引用：沿曲线挖空，保留“观测”而非“持有”的感觉
            pygame.draw.lines(surf, dim(col, 0.16), False, pts, 8)
            for i in range(0, len(pts) - 1, 2):
                pygame.draw.line(surf, with_alpha(col, 175),
                                 pts[i], pts[i + 1], 3)
        else:
            # 外发光 + 主芯（DANGLING 的三层线，本作加粗）
            pygame.draw.lines(surf, dim(col, 0.18), False, pts, 10)
            pygame.draw.lines(surf, dim(col, 0.30), False, pts, 5)
            pygame.draw.lines(surf, mix(col, WHITE, 0.25), False, pts, 3)
            # 流动光点：两枚，white 1px 核心 + 光晕；方向由 src -> dst
            held = e.src is b.player_node and e.kind == STRONG
            speed = 0.34 if held else 0.22
            for k in range(2):
                phase = (b.time * speed + k / 2.0 + e.flow) % 1.0
                f = phase * (len(pts) - 1)
                i = min(int(f), len(pts) - 2)
                t = f - i
                px = pts[i][0] * (1 - t) + pts[i + 1][0] * t
                py = pts[i][1] * (1 - t) + pts[i + 1][1] * t
                glow(surf, px, py, 14, col, 0.45)
                pygame.draw.circle(surf, WHITE, (int(px), int(py)), 1)
        # 箭头压在目标边缘，而不是悬空在节点中心
        ax, ay = pts[-1]
        bx, by = pts[-2]
        ang = math.atan2(ay - by, ax - bx)
        tipx = e.dst.x + ox - math.cos(ang) * (e.dst.r + 4)
        tipy = e.dst.y + oy - math.sin(ang) * (e.dst.r + 4)
        left = (tipx - math.cos(ang - 0.55) * 9,
                tipy - math.sin(ang - 0.55) * 9)
        right = (tipx - math.cos(ang + 0.55) * 9,
                 tipy - math.sin(ang + 0.55) * 9)
        pygame.draw.polygon(surf, col, [(tipx, tipy), left, right])
        glow(surf, tipx, tipy, 13, col, 0.45)

    def draw_alias_bonds(self, surf, b, ox, oy):
        """直接复用 DANGLING 的 ALIAS 虚线 + ∞ 标记。"""
        for pool in b.aliases:
            members = [m for m in pool.members if m.alive]
            if len(members) < 2:
                continue
            pulse = 0.5 + 0.5 * math.sin(b.time * 4 + len(members))
            for m in members:
                glow(surf, m.x + ox, m.y + oy, m.r * 2.4, MAGENTA,
                     0.22 + 0.10 * pulse)
            for i in range(len(members)):
                for j in range(i + 1, len(members)):
                    a, c = members[i], members[j]
                    dashed_line(surf, MAGENTA,
                                (a.x + ox, a.y + oy),
                                (c.x + ox, c.y + oy), 4, 6, 1,
                                alpha=int(70 + 60 * pulse))
                    mx = (a.x + c.x) / 2 + ox
                    my = (a.y + c.y) / 2 + oy
                    blit_text(surf, "∞", (mx, my), 16, MAGENTA,
                              anchor="center", bold=True)

    def draw_aim(self, surf, b, ox, oy, mouse):
        if not b.aim:
            if b.edge_drag:
                mx, my = mouse
                pygame.draw.line(surf, with_alpha(CYAN, 130), b.edge_drag,
                                 (mx, my), 2)
            return
        card = b.aim["card"]
        col = card.color
        mx, my = mouse
        if card.d["target"] == "two" and b.aim.get("src"):
            src = b.aim["src"]
            a = (src.x + ox, src.y + oy)
            pygame.draw.line(surf, with_alpha(col, 160), a, (mx + ox, my + oy), 2)
            pygame.draw.circle(surf, col, (int(src.x + ox), int(src.y + oy)),
                               src.r + 8, 2)
        elif card.d["target"] == "edge" and b.edge_drag:
            path = list(b.slash) or [b.edge_drag]
            if not path or path[-1] != (mx, my):
                path.append((mx, my))
            pts = [(int(x + ox), int(y + oy)) for x, y in path]
            if len(pts) > 1:
                pygame.draw.lines(surf, with_alpha(col, 120), False, pts, 9)
                pygame.draw.lines(surf, with_alpha(col, 220), False, pts, 3)
            for e in b.edges_on_path(path)[:2 if card.up else 1]:
                ep = [(x + ox, y + oy) for x, y in e.points(12)]
                pygame.draw.lines(surf, with_alpha(GOLD, 210), False, ep, 5)
        elif card.d["target"] == "area":
            pygame.draw.circle(surf, with_alpha(col, 70), (int(mx + ox), int(my + oy)),
                               180 if card.key == "LOSSY" else 150, 2)
        elif card.d["target"] in ("node", "two"):
            n = b.node_at(mx, my)
            if n:
                pygame.draw.circle(surf, col, (int(n.x + ox), int(n.y + oy)),
                                   n.r + 8, 2)

    def draw_player(self, surf, b, ox, oy):
        """直接复用 DANGLING 的 SELF：菱形核心 + 三旋转弧 + 轨迹。"""
        n = b.player_node
        x, y = n.x + ox, n.y + oy
        R = 21
        # 轨迹
        self.trail.append((n.x, n.y))
        if len(self.trail) > 26:
            self.trail.pop(0)
        for i, (tx, ty) in enumerate(self.trail[:-1]):
            a = i / max(1, len(self.trail))
            pygame.draw.circle(surf, mix((6, 8, 12), CYAN, a * 0.6),
                               (int(tx + ox), int(ty + oy)),
                               max(1, int(a * 3)))
        # 目标指示
        mx, my = b.mouse
        dx, dy = mx - x, my - y
        d = math.hypot(dx, dy) or 1
        if d > 24:
            ex, ey = x + dx / d * 30, y + dy / d * 30
            pygame.draw.line(surf, with_alpha(CYAN, 70), (x, y), (ex, ey), 1)
            pygame.draw.circle(surf, with_alpha(CYAN, 120),
                               (int(mx), int(my)), 4, 1)
        # 径向脉冲
        pulse = 0.5 + 0.5 * math.sin(self.t * 3)
        glow(surf, x, y, 54, CYAN, 0.38 + 0.10 * pulse)
        pygame.draw.circle(surf, with_alpha(CYAN, 60), (int(x), int(y)),
                           int(28 + pulse * 6), 1)
        # 本体
        pts = [(x, y - R), (x + R * 0.85, y), (x, y + R),
               (x - R * 0.85, y)]
        pygame.draw.polygon(surf, (10, 24, 30), pts)
        pygame.draw.polygon(surf, mix(CYAN, WHITE, 0.3), pts, 2)
        pygame.draw.circle(surf, WHITE, (int(x), int(y)), 2)
        # 三弧环
        ang = self.t * 1.4
        for i in range(3):
            a = ang + i * math.tau / 3
            pygame.draw.arc(surf, with_alpha(CYAN, 170),
                            (x - 24, y - 24, 48, 48), a, a + 1.1, 2)
        if b.iframe > 0:
            a = int(120 + 100 * math.sin(self.t * 20))
            pygame.draw.circle(surf, with_alpha(WHITE, a), (int(x), int(y)),
                               R + 7, 1)
        if b.alias_pool:
            blit_text(surf, "ALIASED", (x, y - 30), 10, MAGENTA,
                      anchor="midtop", mono=True)
        blit_text(surf, "SELF", (x, y + R + 6), 10, dim(CYAN, 0.9),
                  anchor="midtop", mono=True)

    def draw_node(self, surf, b, n, ox, oy, hover=False):
        x, y = n.x + ox, n.y + oy
        col = NODE_COLOR.get(n.kind, DIM)
        if n.hijacked if hasattr(n, "hijacked") else False:
            col = GREEN
        if n.hit_flash > 0:
            col = mix(col, WHITE, 0.65 * min(1.0, n.hit_flash))
        if hover:
            pygame.draw.circle(surf, with_alpha(col, 110), (int(x), int(y)),
                               n.r + 9, 1)
        glow(surf, x, y, n.r * 2.6, col, 0.22)
        if n.kind == "ROOT":
            self.shape_root(surf, n, x, y, col, hover)
        elif n.kind == "MINION":
            self.shape_alloc(surf, n, x, y, col, hover)
        elif n.kind == "CRAWLER":
            self.shape_eraser(surf, n, x, y, col, hover)
        elif n.kind == "SENTINEL":
            self.shape_sentinel(surf, n, x, y, col, hover)
        elif n.kind == "PYLON":
            self.shape_pylon(surf, n, x, y, col, hover)
        elif n.kind == "CYCLER":
            self.shape_cycler(surf, n, x, y, col, hover)
        elif n.kind == "ALLOCATOR":
            self.shape_alloc(surf, n, x, y, col, hover)
        elif n.kind == "WARD":
            self.shape_ward(surf, n, x, y, col, hover)
        elif n.kind == "BOMB":
            self.shape_bomb(surf, n, x, y, col, hover)
        elif n.kind in ("GC_CORE", "AUDITOR", "KERNEL"):
            self.shape_boss(surf, n, x, y, col, hover)
        elif n.kind == "ERASER":
            self.shape_eraser(surf, n, x, y, col, hover)
        elif n.kind == "QUANTIZER":
            self.shape_quant(surf, n, x, y, col, hover)
        else:
            pygame.draw.circle(surf, dim(col, 0.3), (int(x), int(y)), n.r)
            pygame.draw.circle(surf, col, (int(x), int(y)), n.r, 2)
        # 状态环
        if n.born_anim > 0 and n.kind != "ROOT":
            k = 1.0 - n.born_anim / 0.45
            pygame.draw.circle(surf, with_alpha(col, int(170 * (1 - k))),
                               (int(x), int(y)), int(n.r * (0.5 + k * 1.7)), 2)
            glow(surf, x, y, n.r * 2.2, col, 0.25 * (1 - k))
        if n.kind != "ROOT":
            self.draw_refcount(surf, n, b.graph.refcount(n))
        if n.hit_flash > 0:
            pygame.draw.circle(surf, with_alpha(WHITE, int(170 * n.hit_flash)),
                               (int(x), int(y)), n.r + 2, 2)
            glow(surf, x, y, n.r * 3, WHITE, 0.20 * n.hit_flash)
        if n.data.get("destructor") and not n.data.get("cast_stripped"):
            dashed_circle(surf, RED, x, y, n.r + 7, 5, 4, 2, 180)
        if n.data.get("cut_immune") and not n.data.get("cast_stripped"):
            pygame.draw.circle(surf, with_alpha(WHITE, 100), (int(x), int(y)),
                               n.r + 11, 1)
        if n.data.get("shield_t", 0) > 0:
            pygame.draw.circle(surf, with_alpha(BLUE, 190), (int(x), int(y)),
                               n.r + 10, 2)
            pygame.draw.arc(surf, WHITE, (x - n.r - 12, y - n.r - 12,
                                          (n.r + 12) * 2, (n.r + 12) * 2),
                            -math.pi / 2, -math.pi / 2 + 1.2, 2)
        if n.data.get("weak_mark"):
            dashed_circle(surf, with_alpha(PURPLE, 180), x, y, n.r + 6,
                          4, 5, 1, 180)
            blit_text(surf, "WEAK", (x, y - n.r - 20), 10, PURPLE,
                      anchor="midtop", mono=True)
        if n.stun > 0:
            pygame.draw.arc(surf, AMBER, (x - n.r - 6, y - n.r - 6,
                                          (n.r + 6) * 2, (n.r + 6) * 2),
                            0, math.tau * min(1, n.stun / 3), 2)
        if n.hostile and n.kind != "ROOT":
            atk = n.timers.get("atk", 99)
            if 0 < atk < 0.45:
                k = 1 - atk / 0.45
                rr = n.r + 10 + k * 8
                pygame.draw.arc(surf, with_alpha(col, int(110 + 120 * k)),
                                (x - rr, y - rr, rr * 2, rr * 2),
                                -math.pi / 2, -math.pi / 2 + math.tau * k, 2)
        if b.graph.between(b.player_node, n, STRONG):
            pygame.draw.circle(surf, with_alpha(CYAN, 120), (int(x), int(y)),
                               n.r + 5, 1)
        # 血条
        if n.kind != "ROOT":
            w = max(38, n.r * 2)
            r = pygame.Rect(x - w / 2, y - n.r - 16, w, 4)
            pygame.draw.rect(surf, (30, 20, 26), r, border_radius=2)
            f = clamp(n.hp / max(1, n.max_hp), 0, 1)
            if f > 0:
                pygame.draw.rect(surf, mix(RED, GREEN, f),
                                 (r.x, r.y, max(1, int(r.w * f)), r.h),
                                 border_radius=2)
            rc = b.graph.refcount(n)
            if rc > 8:
                blit_text(surf, f"rc{rc}", (x, y + n.r + 9), 10,
                          DIM, mono=True, anchor="midtop")
        if n.kind not in ("ROOT", "MINION", "PLAYER"):
            blit_text(surf, n.name, (x, y + n.r + 22), 10, dim(col, 0.9),
                      anchor="midtop", shadow=1)

    # ------------------------------------------------------------ 形状
    def shape_root(self, surf, n, x, y, col, hov):
        """DANGLING shape_root：菱形作用域 + {}。"""
        r = n.r
        pts = [(x, y - r * 0.7), (x + r * 0.7, y),
               (x, y + r * 0.7), (x - r * 0.7, y)]
        pygame.draw.polygon(surf, (14, 18, 24), pts)
        pygame.draw.polygon(surf, col, pts, 1)
        blit_text(surf, "{}", (x, y), 9, col, anchor="center", mono=True)

    def shape_minion(self, surf, n, x, y, col, hov):
        r = n.r * 1.22
        glow(surf, x, y, r * 1.9, col, 0.16)
        pygame.draw.circle(surf, (20, 14, 18), (int(x), int(y)), int(r))
        pygame.draw.circle(surf, mix(col, WHITE, 0.25),
                           (int(x), int(y)), int(r), 3)
        pygame.draw.circle(surf, dim(col, 0.5), (int(x), int(y)),
                           max(2, int(r * 0.58)), 1)
        pygame.draw.circle(surf, col, (int(x), int(y)), max(2, int(r * 0.26)))
        pygame.draw.circle(surf, WHITE, (int(x), int(y)), max(1, int(r * 0.09)))

    def shape_sentinel(self, surf, n, x, y, col, hov):
        r = n.r * 1.15
        pts = hex_points(x, y, r, math.pi / 6 + math.sin(n.spin) * 0.04)
        glow(surf, x, y, r * 2.1, col, 0.18)
        pygame.draw.polygon(surf, (26, 20, 12), pts)
        pygame.draw.polygon(surf, mix(col, WHITE, 0.18), pts, 3)
        inner = hex_points(x, y, r * 0.58, -n.spin * 0.35)
        pygame.draw.polygon(surf, dim(col, 0.55), inner, 1)
        for i in range(3):
            a = math.pi / 2 + i * math.tau / 3 + n.spin * 0.5
            pygame.draw.line(surf, col, (x, y),
                             (x + math.cos(a) * r * 0.72,
                              y + math.sin(a) * r * 0.72), 2)
        pygame.draw.circle(surf, mix(col, WHITE, 0.4), (int(x), int(y)), 4)

    def shape_pylon(self, surf, n, x, y, col, hov):
        r = n.r * 1.18
        pts = [(x, y - r), (x + r * 0.9, y + r * 0.7),
               (x - r * 0.9, y + r * 0.7)]
        glow(surf, x, y, r * 1.8, col, 0.16)
        pygame.draw.polygon(surf, (26, 12, 22), pts)
        pygame.draw.polygon(surf, mix(col, WHITE, 0.18), pts, 3)
        pygame.draw.line(surf, dim(col, 0.8), (x, y - r * 0.4),
                         (x, y + r * 0.4), 3)
        pygame.draw.line(surf, dim(col, 0.45), (x - r * 0.5, y + r * 0.55),
                         (x + r * 0.5, y + r * 0.55), 1)

    def shape_cycler(self, surf, n, x, y, col, hov):
        r = n.r * 1.15
        glow(surf, x, y, r * 1.9, col, 0.16)
        pygame.draw.circle(surf, (18, 14, 26), (int(x), int(y)), int(r))
        pygame.draw.circle(surf, mix(col, WHITE, 0.15),
                           (int(x), int(y)), int(r), 3)
        a = n.spin * 1.7
        pygame.draw.circle(surf, col, (int(x + math.cos(a) * r * 0.45),
                                        int(y + math.sin(a) * r * 0.45)), 4)
        pygame.draw.circle(surf, dim(col, 0.8),
                           (int(x + math.cos(a + math.pi) * r * 0.45),
                            int(y + math.sin(a + math.pi) * r * 0.45)), 4)
        pygame.draw.arc(surf, dim(col, 0.55),
                        (x - r * 0.7, y - r * 0.7, r * 1.4, r * 1.4),
                        a, a + 2.4, 2)

    def shape_alloc(self, surf, n, x, y, col, hov):
        r = n.r * 1.16
        pts = [(x, y - r), (x + r, y), (x, y + r), (x - r, y)]
        glow(surf, x, y, r * 1.9, col, 0.16)
        pygame.draw.polygon(surf, (12, 22, 22), pts)
        pygame.draw.polygon(surf, mix(col, WHITE, 0.15), pts, 3)
        pygame.draw.line(surf, col, (x - r * 0.35, y),
                         (x + r * 0.35, y), 3)
        pygame.draw.line(surf, col, (x, y - r * 0.35),
                         (x, y + r * 0.35), 3)
        pygame.draw.circle(surf, dim(col, 0.6), (int(x), int(y)),
                           max(2, int(r * 0.12)), 1)

    def shape_ward(self, surf, n, x, y, col, hov):
        self.shape_pylon(surf, n, x, y, col, hov)
        r = n.r
        pygame.draw.arc(surf, with_alpha(col, 130),
                        (x - r * 0.8, y - r * 0.8, r * 1.6, r * 1.6),
                        -0.4, 2.2, 1)

    def shape_bomb(self, surf, n, x, y, col, hov):
        r = n.r * 1.18
        pulse = 0.5 + 0.5 * math.sin(n.spin * 5)
        pts = hex_points(x, y, r, math.pi / 6)
        glow(surf, x, y, r * 2.0, GOLD, 0.2 + 0.2 * pulse)
        pygame.draw.polygon(surf, (26, 22, 10), pts)
        pygame.draw.polygon(surf, mix(GOLD, WHITE, pulse * 0.4), pts, 3)
        pygame.draw.circle(surf, mix(GOLD, WHITE, pulse),
                           (int(x), int(y)), max(3, int(4 + pulse * 4)))
        for i in range(4):
            a = n.spin + i * math.tau / 4
            pygame.draw.line(surf, dim(GOLD, 0.7),
                             (x + math.cos(a) * r * 0.55,
                              y + math.sin(a) * r * 0.55),
                             (x + math.cos(a) * r * 0.9,
                              y + math.sin(a) * r * 0.9), 2)

    def shape_eraser(self, surf, n, x, y, col, hov):
        """DANGLING shape_zombie：抖动脏对象。"""
        r = n.r * 1.14
        jx = random.uniform(-1.4, 1.4)
        jy = random.uniform(-1.4, 1.4)
        glow(surf, x, y, r * 1.9, col, 0.16)
        pygame.draw.circle(surf, (20, 12, 14),
                           (int(x + jx), int(y + jy)), int(r))
        pygame.draw.circle(surf, dim(col, 0.65),
                           (int(x + jx), int(y + jy)), int(r), 1)
        for i in range(5):
            a0 = n.spin + i * 1.26
            pygame.draw.arc(surf, dim(col, 0.85),
                            (x - r + jx, y - r + jy, r * 2, r * 2),
                            a0, a0 + 0.75, 3)
        blit_text(surf, "??", (x + jx, y + jy), 16, col,
                  anchor="center", mono=True, bold=True)

    def shape_quant(self, surf, n, x, y, col, hov):
        self.shape_core(surf, n, x, y, col, hov, scale=0.8)

    def shape_boss(self, surf, n, x, y, col, hov):
        self.shape_core(surf, n, x, y, col, hov, scale=1.0)

    def shape_core(self, surf, n, x, y, col, hov, scale=1.0):
        """DANGLING shape_core：八边形双层环 + 8 根刻度。"""
        r = n.r * scale * 1.12
        rot = n.spin * 0.5
        pts = hex_points(x, y, r, rot, 8)
        pygame.draw.polygon(surf, (26, 12, 22), pts)
        pygame.draw.polygon(surf, mix(col, WHITE, 0.15), pts, 3)
        pts2 = hex_points(x, y, r * 0.62, -rot * 1.6, 8)
        pygame.draw.polygon(surf, dim(col, 0.8), pts2, 2)
        pygame.draw.circle(surf, mix(col, WHITE, 0.35),
                           (int(x), int(y)), int(r * 0.22))
        for i in range(8):
            a = rot + i * math.tau / 8
            pygame.draw.line(surf, dim(col, 0.6),
                             (x + math.cos(a) * r * 1.05,
                              y + math.sin(a) * r * 1.05),
                             (x + math.cos(a) * r * 1.18,
                              y + math.sin(a) * r * 1.18), 2)
        glow(surf, x, y, r * 2.7, col, 0.38)

    # ------------------------------------------------------------ UI
    def draw_refcount(self, surf, n, rc):
        """直接复用 DANGLING 的 refcount 环。"""
        if n.stun > 0:
            return
        r = n.r + 9
        if rc <= 0:
            seg = 14
            for i in range(seg):
                a0 = i * math.tau / seg
                a1 = a0 + math.tau / seg * 0.45
                pygame.draw.line(surf, with_alpha(RED, 190),
                                 (n.x + math.cos(a0) * r,
                                  n.y + math.sin(a0) * r),
                                 (n.x + math.cos(a1) * r,
                                  n.y + math.sin(a1) * r), 1)
            return
        show = min(rc, 8)
        for i in range(8):
            if i >= show:
                break
            a0 = -math.pi / 2 + i * math.tau / 8 + 0.07
            a1 = a0 + math.tau / 8 - 0.14
            pts = [(n.x + math.cos(a0 + (a1 - a0) * k / 4) * r,
                    n.y + math.sin(a0 + (a1 - a0) * k / 4) * r)
                   for k in range(5)]
            pygame.draw.lines(surf, CYAN, False, pts, 2)
        if rc > 8:
            blit_text(surf, f"{rc}", (n.x + r + 8, n.y - 6), 10, CYAN, mono=True)

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
