# -*- coding: utf-8 -*-
"""战场渲染与 HUD。"""
import math
import random
import pygame
from .const import *
from .model import STRONG, WEAK, DANGLING
from .content import META
from .battle import META_POS, TOOL_NAMES, TOOL_CN, TOOL_KEYS, PLAYER_R
from .fx import draw_floaters, draw_rings, draw_sparks

TYPE_CN = {
    "MINION": "小兵", "SENTINEL": "哨兵", "CYCLER": "环", "ALLOCATOR": "分配器",
    "ZOMBIE": "僵尸", "BOMB": "炸弹", "PYLON": "塔架", "CORE": "核心",
    "ROOT": "作用域", "PLAYER": "SELF",
}

TOOL_DESC = {
    0: "拖动任意节点到另一节点，建立一条强引用。从 SELF 出发的引用会让目标停火。",
    1: "拖动划过引用线即可剪断；点节点（数组/树）可批量剪。",
    2: "拖动建立 WEAK 引用：不计入 refcount，可破环、可留悬垂指针。",
    3: "拖动两个节点，合并血池。伤害、增益、死亡都会同步。",
    4: "点击节点，选择强转类型。",
}


TOOL_TIP = {
    0: "拖动：建立引用。从 SELF 出发 = 持有，目标停火",
    1: "划过引用线剪断 · 点节点可批量剪（1 片）",
    2: "拖动：建立不计入 refcount 的弱引用",
    3: "拖动两个节点，合并共享血池（2 片+1 堆）",
    4: "点击节点后选择强转类型（3 片）",
}


class Renderer:
    def __init__(self):
        self.bg = None
        self.trail = []
        self.t = 0.0
        self.hover_anim = {}

    # ------------------------------------------------------------ 光标
    def draw_cursor(self, screen, b):
        x, y = b.mouse
        if x < 2 and y < 2:
            return
        tool = b.tool
        cols = [CYAN, RED, PURPLE, MAGENTA, AMBER]
        col = cols[tool] if b.cast_menu is None else CYAN
        if b.drag:
            col = GREEN
        # 十字
        pygame.draw.circle(screen, with_alpha(col, 210), (int(x), int(y)), 8, 1)
        pygame.draw.line(screen, with_alpha(col, 180), (x - 15, y), (x - 4, y), 1)
        pygame.draw.line(screen, with_alpha(col, 180), (x + 4, y), (x + 15, y), 1)
        pygame.draw.line(screen, with_alpha(col, 180), (x, y - 15), (x, y - 4), 1)
        pygame.draw.line(screen, with_alpha(col, 180), (x, y + 4), (x, y + 15), 1)
        pygame.draw.circle(screen, col, (int(x), int(y)), 1)
        if b.state != "playing":
            return
        # 模式标签
        name = TOOL_NAMES[tool]
        cost = b.cost(["LINK", "CUT", "WEAK", "ALIAS", "CAST"][tool])
        lbl = f"{name} {cost}片" if cost else f"{name} 免费"
        if b.gc_active > 0:
            lbl = f"{name} FREE"
        lx, ly = x + 18, y + 14
        tw = text_w(lbl, 10)
        s = pygame.Surface((tw + 12, 18), pygame.SRCALPHA)
        s.fill((6, 10, 14, 190))
        screen.blit(s, (lx - 4, ly - 2))
        blit_text(screen, lbl, (lx + 2, ly), 10, col, mono=True)

    # ------------------------------------------------------------ 背景
    def build(self):
        s = pygame.Surface((W, H))
        s.fill(BG)
        # 顶部/侧栏
        pygame.draw.rect(s, (10, 13, 18), TOPBAR)
        pygame.draw.rect(s, (11, 14, 20), LEFTPANEL)
        pygame.draw.line(s, PANEL_LINE, (0, TOPBAR.bottom), (W, TOPBAR.bottom), 1)
        pygame.draw.line(s, PANEL_LINE, (LEFTPANEL.right, TOPBAR.bottom),
                         (LEFTPANEL.right, H), 1)
        # 竞技场底
        pygame.draw.rect(s, (8, 11, 16), ARENA, border_radius=4)
        # 网格
        grid = pygame.Surface((ARENA.w, ARENA.h), pygame.SRCALPHA)
        for x in range(0, ARENA.w, 42):
            a = 16 if x % 168 else 24
            pygame.draw.line(grid, (80, 140, 180, a), (x, 0), (x, ARENA.h))
        for y in range(0, ARENA.h, 42):
            a = 16 if y % 168 else 24
            pygame.draw.line(grid, (80, 140, 180, a), (0, y), (ARENA.w, y))
        for x in range(0, ARENA.w, 168):
            for y in range(0, ARENA.h, 168):
                pygame.draw.circle(grid, (110, 190, 230, 60), (x, y), 2)
        s.blit(grid, ARENA.topleft)
        # 越界带（那一格）
        band = pygame.Surface((ARENA.w, ARENA.h), pygame.SRCALPHA)
        col = (110, 210, 255, 9)
        pygame.draw.rect(band, col, (0, 0, ARENA.w, BAND))
        pygame.draw.rect(band, col, (0, ARENA.h - BAND, ARENA.w, BAND))
        pygame.draw.rect(band, col, (0, 0, BAND, ARENA.h))
        pygame.draw.rect(band, col, (ARENA.w - BAND, 0, BAND, ARENA.h))
        # 斜线纹理
        for i in range(-ARENA.h, ARENA.w, 24):
            col2 = (120, 200, 240, 10)
            for (ox, oy, ww, hh) in ((0, 0, ARENA.w, BAND),
                                     (0, ARENA.h - BAND, ARENA.w, BAND),
                                     (0, 0, BAND, ARENA.h),
                                     (ARENA.w - BAND, 0, BAND, ARENA.h)):
                x0 = max(i, -hh)
                pygame.draw.line(band, col2, (max(0, min(ARENA.w, i)) + ox, oy),
                                 (max(0, min(ARENA.w, i + hh)) + ox, oy + hh), 1)
        s.blit(band, ARENA.topleft)
        # 播放区边框
        pygame.draw.rect(s, (34, 52, 70), (PLAY.x - 1, PLAY.y - 1, PLAY.w + 2, PLAY.h + 2), 1)
        pygame.draw.rect(s, (26, 40, 54), ARENA, 1, border_radius=4)
        # 四角括号
        bracket(s, pygame.Rect(ARENA.x + 6, ARENA.y + 6, ARENA.w - 12, ARENA.h - 12),
                (60, 110, 140), 18, 2)
        # 地址刻度
        f = get_font(9, mono=True)
        for i in range(0, 16):
            x = PLAY.x + i * PLAY.w / 15
            pygame.draw.line(s, (40, 66, 84), (x, PLAY.bottom + 4), (x, PLAY.bottom + 10), 1)
            if i % 2 == 0:
                s.blit(f.render("0x%04X" % (i * 32), True, (44, 70, 90)), (x - 18, PLAY.bottom + 12))
        for i in range(0, 10):
            y = PLAY.y + i * PLAY.h / 9
            pygame.draw.line(s, (40, 66, 84), (PLAY.x - 10, y), (PLAY.x - 4, y), 1)
            if i % 2 == 0:
                surf = f.render("%02X" % (i * 16), True, (44, 70, 90))
                s.blit(surf, (PLAY.x - 12 - surf.get_width(), y - 5))
        # 内存转储纹理
        rnd = random.Random(7)
        f2 = get_font(10, mono=True)
        for i in range(52):
            x = rnd.randint(PLAY.x + 20, PLAY.right - 180)
            y = rnd.randint(PLAY.y + 10, PLAY.bottom - 14)
            txt = " ".join("%04x" % rnd.randint(0, 0xFFFF) for _ in range(3))
            col = rnd.choice([(18, 32, 40), (22, 30, 44), (16, 36, 34)])
            s.blit(f2.render(txt, True, col), (x, y))
        self.bg = s

    # ------------------------------------------------------------ 主绘制
    def draw(self, screen, b, mouse):
        self.t += 1 / 60
        world = pygame.Surface((W, H))
        world.blit(self.bg, (0, 0))
        # 内存扫描线
        sy = ARENA.y + (b.time * 26) % (ARENA.h - 2)
        sc = pygame.Surface((ARENA.w, 42), pygame.SRCALPHA)
        for i in range(42):
            a = int(10 * (1 - abs(i - 21) / 21) ** 2)
            pygame.draw.line(sc, (80, 200, 240, a), (0, i), (ARENA.w, i))
        world.blit(sc, (ARENA.x, sy - 21))
        pygame.draw.line(world, (30, 60, 74), (ARENA.x, sy), (ARENA.right, sy), 1)
        self.draw_meta(world, b)
        self.draw_edges(world, b)
        self.draw_leaks(world, b)
        self.draw_alias_bonds(world, b)
        self.draw_nodes(world, b)
        self.draw_player(world, b)
        self.draw_projectiles(world, b)
        self.draw_beams(world, b)
        draw_rings(world, b.fx)
        b.fx.draw_world(world, (0, 0))
        draw_sparks(world, b.fx)
        self.draw_drag(world, b, mouse)
        if b.gc_active > 0:
            self.draw_gc_overlay(world, b)
        elif b.plan:
            ov = pygame.Surface((ARENA.w, ARENA.h), pygame.SRCALPHA)
            ov.fill((20, 40, 70, 40))
            world.blit(ov, ARENA.topleft)
        draw_floaters(world, b.fx)

        ox, oy = b.fx.offset()
        screen.blit(world, (int(ox), int(oy)))

        self.draw_banner(screen, b)
        self.draw_hud(screen, b)
        self.draw_tooltip(screen, b, mouse)
        self.draw_cast_menu(screen, b)
        if b.state == "intro":
            self.draw_intro(screen, b)
        if b.state == "clear":
            self.draw_clear(screen, b)
        if b.state in ("dead", "victory", "done") and b.ending:
            pass
        return world

    def draw_banner(self, screen, b):
        if b.banner_t <= 0 or not getattr(b, "banner", None):
            return
        title, sub, dur = b.banner
        k = min(1.0, b.banner_t / 0.35)
        a = int(255 * k)
        w, h = 780, 74
        r = pygame.Rect(W // 2 - w // 2, ARENA.y + 44, w, h)
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        s.fill((12, 6, 14, int(215 * k)))
        pygame.draw.rect(s, with_alpha(MAGENTA, int(170 * k)), (0, 0, w, h), 1)
        screen.blit(s, r.topleft)
        bracket(screen, r, MAGENTA, 16, 2, a)
        blit_text(screen, title, (r.centerx, r.y + 12), 26, MAGENTA,
                  anchor="midtop", bold=True, alpha=a, mono=True)
        blit_text(screen, sub, (r.centerx, r.y + 46), 12, dim(WHITE, 0.8),
                  anchor="midtop", alpha=a)

    # ------------------------------------------------------------ 元数据
    def draw_meta(self, world, b):
        avail = b.room.get("oob", [])
        for key, (x, y) in META_POS.items():
            if key not in avail and not (key == "boss" and b.room.get("boss")):
                continue
            meta = META[key]
            active = b.oob
            a = 220 if active else 64
            r = pygame.Rect(0, 0, 96, 22)
            r.center = (int(x), int(y))
            s = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
            pygame.draw.rect(s, with_alpha(meta["color"], 30 if active else 8),
                             (0, 0, r.w, r.h), border_radius=3)
            pygame.draw.rect(s, with_alpha(meta["color"], a), (0, 0, r.w, r.h),
                             1, border_radius=3)
            world.blit(s, r.topleft)
            blit_text(world, meta["cn"], r.center, 10,
                      with_alpha(meta["color"], a if active else 55),
                      anchor="center", bold=False)
            if active:
                glow(world, x, y, 34, meta["color"], 0.3)

    # ------------------------------------------------------------ 边
    def draw_edges(self, world, b):
        t = b.time
        edges = [e for e in b.graph.edges if e.alive]
        edges.sort(key=lambda e: 0 if e.kind != STRONG else 1)
        for e in edges:
            pts = e.points(20)
            col = e.color
            if e.src is b.player_node and e.kind == STRONG:
                col = GREEN if not e.dst.hostile else CYAN
            held = e.src is b.player_node and e.kind == STRONG
            # 外发光
            wide = [(int(p[0]), int(p[1])) for p in pts]
            if len(wide) > 1:
                pygame.draw.lines(world, dim(col, 0.18), False, wide, 7)
                if e.kind == STRONG:
                    pygame.draw.lines(world, dim(col, 0.30), False, wide, 3)
                # 主芯
                if e.kind == WEAK:
                    for i in range(0, len(wide) - 1, 2):
                        pygame.draw.line(world, dim(col, 0.85), wide[i], wide[i + 1], 1)
                elif e.kind == DANGLING:
                    for i in range(0, len(wide) - 1, 2):
                        pygame.draw.line(world, dim(col, 0.8), wide[i], wide[i + 1], 2)
                else:
                    pygame.draw.lines(world, mix(col, WHITE, 0.25), False, wide, 2)
            # 流动光点
            if e.kind == STRONG:
                n_dots = 2
                for i in range(n_dots):
                    k = ((t * (0.35 if held else 0.22) + i / n_dots + e.flow) % 1.0)
                    p = bezier(pts[0], e.ctrl(), pts[-1], k)
                    glow(world, p[0], p[1], 13, col, 0.55)
                    pygame.draw.circle(world, WHITE, (int(p[0]), int(p[1])), 1)
            # 箭头
            self.draw_arrow(world, e, col)
            # 断链预警
            if e.warn > 0:
                p = bezier(pts[0], e.ctrl(), pts[-1], 0.5)
                blit_text(world, "!", (p[0], p[1] - 12), 14, RED, anchor="center", bold=True)
        # 悬垂指针
        for d in b.dangling:
            a = (b.player_node.x, b.player_node.y)
            c = (d["x"], d["y"])
            dashed_line(world, RED, a, c, 10, 8, 1,
                        alpha=int(90 + 90 * math.sin(t * 8)))
            pygame.draw.circle(world, RED, (int(c[0]), int(c[1])), 3, 1)
            blit_text(world, "悬垂", (c[0], c[1] + 10), 9, dim(RED, 0.9), anchor="center")

    def draw_arrow(self, world, e, col):
        pts = e.points(20)
        p1 = pts[-2]
        p2 = pts[-1]
        dx, dy = p2[0] - p1[0], p2[1] - p1[1]
        l = math.hypot(dx, dy) or 1
        ux, uy = dx / l, dy / l
        tip = (e.dst.x - ux * (e.dst.r + 4), e.dst.y - uy * (e.dst.r + 4))
        base = (tip[0] - ux * 9, tip[1] - uy * 9)
        px, py = -uy, ux
        tri = [tip, (base[0] + px * 4.5, base[1] + py * 4.5),
               (base[0] - px * 4.5, base[1] - py * 4.5)]
        pygame.draw.polygon(world, col, tri)
        glow(world, tip[0], tip[1], 12, col, 0.5)

    # ------------------------------------------------------------ 泄漏
    def draw_leaks(self, world, b):
        for lk in b.leaks:
            x, y = lk.x, lk.y
            pts = hex_points(x, y, lk.r, lk.born * 0.3 + 0.4)
            pygame.draw.polygon(world, (18, 20, 20), pts)
            pygame.draw.polygon(world, (58, 64, 60), pts, 1)
            # 破损纹
            for i in range(3):
                a0 = 0.7 + i * 2.1
                ax = x + math.cos(a0) * lk.r * 0.7
                ay = y + math.sin(a0) * lk.r * 0.7
                bx = x + math.cos(a0 + 1.1) * lk.r * 0.3
                by = y + math.sin(a0 + 1.1) * lk.r * 0.3
                pygame.draw.line(world, (72, 80, 74), (ax, ay), (bx, by), 1)
            blit_text(world, "leak", (x, y + lk.r + 4), 9, (72, 84, 78),
                      anchor="midtop", mono=True)

    # ------------------------------------------------------------ 别名
    def draw_alias_bonds(self, world, b):
        pools = {}
        for n in b.graph.nodes:
            if n.alive and n.alias:
                pools.setdefault(id(n.alias), (n.alias, []))[1].append(n)
        for pid, (pool, members) in pools.items():
            if len(members) < 2:
                continue
            pulse = 0.5 + 0.5 * math.sin(b.time * 4 + len(members))
            for m in members:
                glow(world, m.x, m.y, m.r * 2.4, MAGENTA, 0.22 + 0.1 * pulse)
            for i in range(len(members)):
                for j in range(i + 1, len(members)):
                    a, c = members[i], members[j]
                    dashed_line(world, MAGENTA, (a.x, a.y), (c.x, c.y), 4, 6, 1,
                                alpha=int(70 + 60 * pulse))
                    mid = ((a.x + c.x) / 2, (a.y + c.y) / 2)
                    blit_text(world, "∞", mid, 16, MAGENTA, anchor="center", bold=True)

    # ------------------------------------------------------------ 节点
    def draw_nodes(self, world, b):
        for n in sorted(b.graph.nodes, key=lambda n: (n.kind == "PLAYER", n.y)):
            if not n.alive or n.kind == "PLAYER":
                continue
            self.draw_node(world, b, n)

    def draw_node(self, world, b, n):
        x, y, r = n.x, n.y, n.r
        col = n.color
        hovered = (b.hover_node is n)
        if n.hit_flash > 0:
            col = mix(col, WHITE, 0.65 * n.hit_flash)
        # 光晕
        glow(world, x, y, r * 2.6, col, 0.30 if n.hostile else 0.16)
        if hovered:
            glow(world, x, y, r * 3.0, WHITE, 0.18)
        # 出生动画
        if n.born_anim > 0:
            k = 1 - n.born_anim
            pygame.draw.circle(world, col, (int(x), int(y)), int(r * (0.4 + k * 1.6)), 1)
        # 形状
        if n.kind == "ROOT":
            self.shape_root(world, n, col, hovered)
        elif n.kind == "SENTINEL":
            self.shape_sentinel(world, n, col, hovered)
        elif n.kind == "CYCLER":
            self.shape_cycler(world, n, col, hovered)
        elif n.kind == "ALLOCATOR":
            self.shape_alloc(world, n, col, hovered)
        elif n.kind == "ZOMBIE":
            self.shape_zombie(world, n, col, hovered)
        elif n.kind == "BOMB":
            self.shape_bomb(world, n, col, hovered)
        elif n.kind == "PYLON":
            self.shape_pylon(world, n, col, hovered)
        elif n.kind == "CORE":
            self.shape_core(world, n, col, hovered)
        else:
            self.shape_minion(world, n, col, hovered)
        # 引用计数环
        if n.kind != "ROOT":
            rc = 0 if n.stun > 0 else b.graph.refcount(n)
            self.draw_refcount(world, n, rc)
        # 血条
        if n.kind not in ("ROOT", "ZOMBIE") and n.max_hp > 1:
            hp, mx = b.display_hp(n)
            frac = max(0.0, min(1.0, hp / mx)) if mx else 0
            if frac < 0.999:
                w = max(30, r * 1.7)
                rr = pygame.Rect(int(x - w / 2), int(y + r + 8), int(w), 4)
                bar(world, rr, frac, n.color)
        # 类型标签
        if n.kind != "ROOT":
            lbl = TYPE_CN.get(n.kind, n.kind)
            col_lbl = dim(col, 0.85)
            blit_text(world, lbl, (x, y + r + 15), 10, col_lbl, anchor="midtop")
        # 状态
        if n.hostile and not n.hijacked:
            atk = n.timers.get("atk", 99)
            if 0 < atk < 0.45:
                k = 1 - atk / 0.45
                rr = n.r + 10 + k * 8
                pygame.draw.arc(world, with_alpha(n.color, int(120 + 120 * k)),
                                (x - rr, y - rr, rr * 2, rr * 2),
                                -math.pi / 2, -math.pi / 2 + math.tau * k, 2)
        if n.stun > 0:
            self.draw_stun(world, n)
        if n.data.get("int"):
            blit_text(world, "int", (x, y - r - 16), 11, AMBER, anchor="midtop", mono=True)
        if b.is_held(n) and n.hostile:
            blit_text(world, "HELD", (x, y - r - 16), 10, GREEN, anchor="midtop", mono=True)
        if n.hijacked:
            blit_text(world, "HIJACKED", (x, y - r - 16), 10, GREEN, anchor="midtop", mono=True)
        if n.kind == "ZOMBIE":
            pass
        # 选中/悬停
        if hovered:
            pygame.draw.circle(world, with_alpha(WHITE, 190), (int(x), int(y)),
                               int(r + 6), 1)

    def shape_root(self, world, n, col, hov):
        x, y, r = n.x, n.y, n.r
        pts = [(x, y - r * 0.7), (x + r * 0.7, y), (x, y + r * 0.7), (x - r * 0.7, y)]
        pygame.draw.polygon(world, (14, 18, 24), pts)
        pygame.draw.polygon(world, col, pts, 1)
        blit_text(world, "{}", (x, y), 9, col, anchor="center", mono=True)

    def shape_minion(self, world, n, col, hov):
        x, y, r = n.x, n.y, n.r
        pygame.draw.circle(world, (20, 14, 18), (int(x), int(y)), int(r))
        pygame.draw.circle(world, mix(col, WHITE, 0.2), (int(x), int(y)), int(r), 2)
        pygame.draw.circle(world, col, (int(x), int(y)), max(2, int(r * 0.25)))

    def shape_sentinel(self, world, n, col, hov):
        x, y, r = n.x, n.y, n.r
        pts = hex_points(x, y, r, math.pi / 6 + math.sin(n.spin) * 0.04)
        pygame.draw.polygon(world, (26, 20, 12), pts)
        pygame.draw.polygon(world, mix(col, WHITE, 0.15), pts, 2)
        for i in range(3):
            a = math.pi / 2 + i * math.tau / 3 + n.spin * 0.5
            pygame.draw.line(world, col, (x, y),
                             (x + math.cos(a) * r * 0.72, y + math.sin(a) * r * 0.72), 1)
        pygame.draw.circle(world, col, (int(x), int(y)), 3)

    def shape_cycler(self, world, n, col, hov):
        x, y, r = n.x, n.y, n.r
        pygame.draw.circle(world, (18, 14, 26), (int(x), int(y)), int(r))
        pygame.draw.circle(world, mix(col, WHITE, 0.1), (int(x), int(y)), int(r), 2)
        a = n.spin * 1.7
        pygame.draw.circle(world, col, (int(x + math.cos(a) * r * 0.45),
                                        int(y + math.sin(a) * r * 0.45)), 3)
        pygame.draw.circle(world, dim(col, 0.8),
                           (int(x + math.cos(a + math.pi) * r * 0.45),
                            int(y + math.sin(a + math.pi) * r * 0.45)), 3)
        pygame.draw.arc(world, dim(col, 0.55), (x - r * 0.7, y - r * 0.7, r * 1.4, r * 1.4),
                        a, a + 2.4, 1)

    def shape_alloc(self, world, n, col, hov):
        x, y, r = n.x, n.y, n.r
        pts = [(x, y - r), (x + r, y), (x, y + r), (x - r, y)]
        pygame.draw.polygon(world, (12, 22, 22), pts)
        pygame.draw.polygon(world, col, pts, 2)
        pygame.draw.line(world, col, (x - r * 0.35, y), (x + r * 0.35, y), 2)
        pygame.draw.line(world, col, (x, y - r * 0.35), (x, y + r * 0.35), 2)

    def shape_zombie(self, world, n, col, hov):
        x, y, r = n.x, n.y, n.r
        jx = random.uniform(-1.4, 1.4)
        jy = random.uniform(-1.4, 1.4)
        pygame.draw.circle(world, (20, 12, 14), (int(x + jx), int(y + jy)), int(r))
        for i in range(5):
            a0 = n.spin + i * 1.26
            pygame.draw.arc(world, dim(col, 0.85),
                            (x - r + jx, y - r + jy, r * 2, r * 2),
                            a0, a0 + 0.75, 2)
        blit_text(world, "??", (x + jx, y + jy), 14, col, anchor="center", mono=True, bold=True)

    def shape_bomb(self, world, n, col, hov):
        x, y, r = n.x, n.y, n.r
        pulse = 0.5 + 0.5 * math.sin(n.spin * 5)
        pts = hex_points(x, y, r, math.pi / 6)
        pygame.draw.polygon(world, (26, 22, 10), pts)
        pygame.draw.polygon(world, GOLD, pts, 2)
        pygame.draw.circle(world, mix(GOLD, WHITE, pulse), (int(x), int(y)), max(2, int(3 + pulse * 3)))
        glow(world, x, y, r * 1.6, GOLD, 0.2 + 0.2 * pulse)
        for i in range(4):
            a = n.spin + i * math.tau / 4
            pygame.draw.line(world, dim(GOLD, 0.7),
                             (x + math.cos(a) * r * 0.55, y + math.sin(a) * r * 0.55),
                             (x + math.cos(a) * r * 0.9, y + math.sin(a) * r * 0.9), 1)

    def shape_pylon(self, world, n, col, hov):
        x, y, r = n.x, n.y, n.r
        pts = [(x, y - r), (x + r * 0.9, y + r * 0.7), (x - r * 0.9, y + r * 0.7)]
        pygame.draw.polygon(world, (26, 12, 22), pts)
        pygame.draw.polygon(world, col, pts, 2)
        pygame.draw.line(world, dim(col, 0.8), (x, y - r * 0.4), (x, y + r * 0.4), 2)

    def shape_core(self, world, n, col, hov):
        x, y, r = n.x, n.y, n.r
        rot = n.spin * 0.5
        pts = hex_points(x, y, r, rot, 8)
        pygame.draw.polygon(world, (26, 12, 22), pts)
        pygame.draw.polygon(world, col, pts, 2)
        pts2 = hex_points(x, y, r * 0.62, -rot * 1.6, 8)
        pygame.draw.polygon(world, dim(col, 0.8), pts2, 1)
        pygame.draw.circle(world, mix(col, WHITE, 0.3), (int(x), int(y)), int(r * 0.2))
        for i in range(8):
            a = rot + i * math.tau / 8
            pygame.draw.line(world, dim(col, 0.6),
                             (x + math.cos(a) * r * 1.05, y + math.sin(a) * r * 1.05),
                             (x + math.cos(a) * r * 1.18, y + math.sin(a) * r * 1.18), 2)
        glow(world, x, y, r * 2.6, col, 0.35)

    def draw_refcount(self, world, n, rc):
        r = n.r + 9
        if n.stun > 0:
            return
        if rc <= 0:
            seg = 14
            for i in range(seg):
                a0 = i * math.tau / seg
                a1 = a0 + math.tau / seg * 0.45
                pygame.draw.line(world, with_alpha(RED, 190),
                                 (n.x + math.cos(a0) * r, n.y + math.sin(a0) * r),
                                 (n.x + math.cos(a1) * r, n.y + math.sin(a1) * r), 1)
            return
        show = min(rc, 8)
        segs = 8 if rc <= 8 else 8
        for i in range(segs):
            if i >= show:
                break
            a0 = -math.pi / 2 + i * math.tau / segs + 0.07
            a1 = a0 + math.tau / segs - 0.14
            pts = [(n.x + math.cos(a0 + (a1 - a0) * k / 4) * r,
                    n.y + math.sin(a0 + (a1 - a0) * k / 4) * r) for k in range(5)]
            pygame.draw.lines(world, CYAN, False, pts, 2)
        if rc > 8:
            blit_text(world, f"{rc}", (n.x + r + 8, n.y - 6), 10, CYAN, mono=True)

    def draw_stun(self, world, n):
        x, y, r = n.x, n.y, n.r
        a0 = n.spin * 4
        for i in range(3):
            a = a0 + i * math.tau / 3
            px = x + math.cos(a) * r * 1.35
            py = y + math.sin(a) * r * 1.35
            glow(world, px, py, 8, CYAN, 0.6)
            pygame.draw.circle(world, CYAN, (int(px), int(py)), 2)
        blit_text(world, "SEGFAULT", (x, y - r - 26), 12, CYAN, anchor="center", mono=True)

    # ------------------------------------------------------------ 玩家
    def draw_player(self, world, b):
        x, y = b.px, b.py
        t = b.time
        # 轨迹
        if len(self.trail) > 26:
            self.trail.pop(0)
        self.trail.append((x, y))
        for i, (tx, ty) in enumerate(self.trail[:-1]):
            a = i / len(self.trail)
            pygame.draw.circle(world, mix(BG, CYAN, a * 0.6), (int(tx), int(ty)),
                               max(1, int(a * 3)))
        # 目标指示
        mx, my = b.mouse
        dx, dy = mx - x, my - y
        d = math.hypot(dx, dy) or 1
        if d > 24:
            ex, ey = x + dx / d * 30, y + dy / d * 30
            pygame.draw.line(world, with_alpha(CYAN, 70), (x, y), (ex, ey), 1)
            pygame.draw.circle(world, with_alpha(CYAN, 120), (int(mx), int(my)), 4, 1)
        # 径向脉冲
        pulse = 0.5 + 0.5 * math.sin(t * 3)
        glow(world, x, y, 46, CYAN, 0.35 + 0.1 * pulse)
        pygame.draw.circle(world, with_alpha(CYAN, 60), (int(x), int(y)),
                           int(24 + pulse * 6), 1)
        # 本体
        pts = [(x, y - PLAYER_R), (x + PLAYER_R * 0.85, y),
               (x, y + PLAYER_R), (x - PLAYER_R * 0.85, y)]
        pygame.draw.polygon(world, (10, 24, 30), pts)
        pygame.draw.polygon(world, mix(CYAN, WHITE, 0.3), pts, 2)
        pygame.draw.circle(world, WHITE, (int(x), int(y)), 2)
        # 环
        ang = t * 1.4
        for i in range(3):
            a = ang + i * math.tau / 3
            pygame.draw.arc(world, with_alpha(CYAN, 170),
                            (x - 22, y - 22, 44, 44), a, a + 1.1, 2)
        if b.iframe > 0:
            a = int(120 + 100 * math.sin(t * 20))
            pygame.draw.circle(world, with_alpha(WHITE, a), (int(x), int(y)),
                               int(PLAYER_R + 7), 1)
        if b.alias_pool:
            blit_text(world, "ALIASED", (x, y - 30), 10, MAGENTA, anchor="midtop", mono=True)
        # 名字
        blit_text(world, "SELF", (x, y + PLAYER_R + 6), 10, dim(CYAN, 0.9),
                  anchor="midtop", mono=True)

    # ------------------------------------------------------------ 弹幕
    def draw_projectiles(self, world, b):
        for p in b.projectiles:
            glow(world, p.x, p.y, p.r * 3.2, p.color, 0.55)
            pygame.draw.circle(world, mix(p.color, WHITE, 0.5),
                               (int(p.x), int(p.y)), max(1, int(p.r)))
            if p.kind == "big":
                pygame.draw.circle(world, p.color, (int(p.x), int(p.y)),
                                   int(p.r + 3), 1)
            # 尾迹
            pygame.draw.line(world, dim(p.color, 0.5), (p.x, p.y),
                             (p.x - p.vx * 0.035, p.y - p.vy * 0.035), 2)

    def draw_beams(self, world, b):
        for bm in b.beams:
            if bm.t < bm.warn:
                k = bm.t / bm.warn
                ex = bm.node.x + math.cos(bm.angle) * bm.length
                ey = bm.node.y + math.sin(bm.angle) * bm.length
                dashed_line(world, with_alpha(MAGENTA, int(80 + 100 * k)),
                            (bm.node.x, bm.node.y), (ex, ey), 14, 10, 1)
            else:
                ex = bm.node.x + math.cos(bm.angle) * bm.length
                ey = bm.node.y + math.sin(bm.angle) * bm.length
                pygame.draw.line(world, dim(MAGENTA, 0.3),
                                 (bm.node.x, bm.node.y), (ex, ey), int(bm.width * 1.8))
                pygame.draw.line(world, MAGENTA, (bm.node.x, bm.node.y), (ex, ey),
                                 int(bm.width * 0.5))
                pygame.draw.line(world, WHITE, (bm.node.x, bm.node.y), (ex, ey), 3)

    # ------------------------------------------------------------ 拖拽
    def draw_drag(self, world, b, mouse):
        if b.drag:
            a = b.drag["src"]
            mx, my = b.drag["pos"]
            b2 = b.node_at(mx, my)
            if b.tool == 1:
                col = CYAN
            elif b.tool == 2:
                col = PURPLE
            elif b.tool == 3:
                col = MAGENTA
            else:
                col = CYAN
            segs = 26
            for i in range(segs):
                if i % 2:
                    continue
                t0 = i / segs
                t1 = (i + 1) / segs
                p0 = (a.x + (mx - a.x) * t0, a.y + (my - a.y) * t0)
                p1 = (a.x + (mx - a.x) * t1, a.y + (my - a.y) * t1)
                pygame.draw.line(world, mix(BG, col, 0.5 + 0.5 * t0), p0, p1, 2)
            glow(world, mx, my, 18, col, 0.5)
            if b2 is not None and b2 is not a and b2.alive:
                ok = True
                if b.tool == 3:
                    ok = not (b2.kind == "ROOT" or a.kind == "ROOT")
                col2 = GREEN if ok else RED
                pygame.draw.circle(world, col2, (int(b2.x), int(b2.y)),
                                   int(b2.r + 8), 2)
                c = b.cost({1: "WEAK", 2: "ALIAS"}.get(b.tool, "LINK"))
                blit_text(world, f"{'WEAK' if b.tool == 2 else 'ALIAS' if b.tool == 3 else 'LINK'} · {c}",
                          (mx + 16, my - 8), 13, col2, bold=True, mono=True)
        if b.slash and len(b.slash) > 1:
            pts = b.slash
            for i in range(len(pts) - 1):
                a = i / max(1, len(pts) - 1)
                pygame.draw.line(world, mix(WHITE, CYAN, a), pts[i], pts[i + 1],
                                 2 + int(a * 3))
            # 剪线火花
            for i in range(len(pts) - 1):
                if random.random() < 0.4:
                    x = (pts[i][0] + pts[i + 1][0]) / 2
                    y = (pts[i][1] + pts[i + 1][1]) / 2
                    glow(world, x, y, 10, WHITE, 0.5)

    # ------------------------------------------------------------ GC
    def draw_gc_overlay(self, world, b):
        ov = pygame.Surface((ARENA.w, ARENA.h), pygame.SRCALPHA)
        ov.fill((8, 20, 36, 150))
        world.blit(ov, ARENA.topleft)
        # 重新描一遍图，让它成为焦点
        self.draw_edges(world, b)
        self.draw_alias_bonds(world, b)
        self.draw_nodes(world, b)
        self.draw_player(world, b)
        # 计时条
        k = max(0.0, min(1.0, b.gc_active / 2.2))
        rr = pygame.Rect(ARENA.x + 40, ARENA.y + 18, ARENA.w - 80, 4)
        bar(world, rr, k, CYAN)
        blit_text(world, "TIME TO REWIRE  %.1fs" % max(0.0, b.gc_active),
                  (ARENA.centerx, ARENA.y + 30), 11, CYAN, anchor="midtop", mono=True)
        # 边框脉冲
        pygame.draw.rect(world, with_alpha(CYAN, int(120 + 80 * math.sin(b.time * 20))),
                         ARENA, 2)

    # ------------------------------------------------------------ 悬停信息
    def draw_tooltip(self, screen, b, mouse):
        if b.state != "playing":
            return
        if b.drag or b.slash or b.cast_menu:
            return
        n = b.hover_node
        if n is None:
            e = b.hover_edge
            if e is not None:
                self.edge_tooltip(screen, b, e, mouse)
            return
        x, y = mouse
        w, h = 272, 160
        rx = min(x + 22, W - w - 12)
        ry = min(y + 18, H - h - 12)
        r = pygame.Rect(rx, ry, w, h)
        panel(screen, r, (10, 14, 20), dim(n.color, 0.8), 4, 1, 240)
        bracket(screen, r, n.color, 10, 1, 170)
        blit_text(screen, n.name, (r.x + 12, r.y + 9), 15, mix(n.color, WHITE, 0.4), bold=True)
        blit_text(screen, TYPE_CN.get(n.kind, n.kind), (r.right - 12, r.y + 12), 11,
                  dim(n.color, 0.9), anchor="topright")
        rc = b.graph.refcount(n)
        yy = r.y + 34
        hp, mx = b.display_hp(n)
        if n.kind not in ("ROOT", "ZOMBIE") and mx > 1:
            blit_text(screen, "HP", (r.x + 12, yy), 10, DIM, mono=True)
            bar(screen, pygame.Rect(r.x + 40, yy + 2, 120, 7), hp / mx, n.color)
            blit_text(screen, f"{int(hp)}/{int(mx)}", (r.x + 166, yy - 1), 10, DIM, mono=True)
            yy += 20
        blit_text(screen, "refcount", (r.x + 12, yy), 10, DIM, mono=True)
        blit_text(screen, str(rc), (r.x + 82, yy - 2), 14,
                  CYAN if rc else RED, bold=True, mono=True)
        if rc == 0:
            blit_text(screen, "→ 下帧被 GC 擦除", (r.x + 100, yy - 1), 11, GREEN)
        else:
            blit_text(screen, f"剪断 {rc} 条入边即可回收", (r.x + 100, yy - 1), 11, DIM)
        yy += 22
        ins = len(b.graph.incoming(n))
        outs = len(b.graph.outgoing(n))
        blit_text(screen, f"入边 {ins} / 出边 {outs}", (r.x + 12, yy), 11, DIM)
        if b.is_held(n):
            blit_text(screen, "被你持有：停火", (r.x + 118, yy), 11, GREEN)
        elif n.alias:
            blit_text(screen, f"别名 {len(n.alias.members)} 个", (r.x + 118, yy), 11, MAGENTA)
        elif n.stun > 0:
            blit_text(screen, f"眩晕 {n.stun:.1f}s", (r.x + 118, yy), 11, CYAN)
        blit_text(screen, TOOL_TIP.get(b.tool, ""), (r.x + 12, r.bottom - 22), 10, dim(DIM, 0.9))

    def edge_tooltip(self, screen, b, e, mouse):
        x, y = mouse
        w, h = 230, 76
        rx = min(x + 18, W - w - 12)
        ry = min(y + 14, H - h - 12)
        r = pygame.Rect(rx, ry, w, h)
        panel(screen, r, (10, 14, 20), dim(e.color, 0.8), 4, 1, 240)
        kind_cn = {STRONG: "强引用 STRONG", WEAK: "弱引用 WEAK", DANGLING: "悬垂 DANGLING"}[e.kind]
        blit_text(screen, kind_cn, (r.x + 12, r.y + 9), 13, e.color, bold=True, mono=True)
        blit_text(screen, f"{e.src.name} → {e.dst.name}", (r.x + 12, r.y + 30), 11, DIM)
        if e.kind == STRONG:
            blit_text(screen, "计入 refcount · 左键拖动可剪断", (r.x + 12, r.y + 50), 10, DIM)
        elif e.kind == WEAK:
            blit_text(screen, "不计入 refcount · 可破环", (r.x + 12, r.y + 50), 10, DIM)
        else:
            blit_text(screen, "指向已释放对象 · 剪断可清除它", (r.x + 12, r.y + 50), 10, DIM)

    # ------------------------------------------------------------ 强转菜单
    def draw_cast_menu(self, screen, b):
        if not b.cast_menu:
            return
        n = b.cast_menu["node"]
        x = min(max(n.x + 50, 12), W - 300)
        y = min(max(n.y - 40, 100), H - 160)
        r = pygame.Rect(int(x), int(y), 286, 118)
        panel(screen, r, (12, 16, 24), CYAN, 4, 1, 245)
        bracket(screen, r, CYAN, 12, 1, 200)
        blit_text(screen, "CAST // 类型强转", (r.x + 12, r.y + 8), 13, CYAN, bold=True, mono=True)
        blit_text(screen, f"目标 {n.name}", (r.x + 12, r.y + 28), 10, DIM)
        rows = [("1", "NULL 空类型", "眩晕 3s · 出边悬空", CYAN),
                ("2", "int 整型", "34 伤害 · 禁止重建", AMBER)]
        for i, (k, t1, t2, c) in enumerate(rows):
            rr = pygame.Rect(r.x + 8, r.y + 46 + i * 32, r.w - 16, 28)
            pygame.draw.rect(screen, (18, 24, 34) if i else (22, 30, 42), rr, border_radius=3)
            pygame.draw.rect(screen, dim(c, 0.6), rr, 1, border_radius=3)
            blit_text(screen, k, (rr.x + 9, rr.y + 6), 13, c, bold=True, mono=True)
            blit_text(screen, t1, (rr.x + 28, rr.y + 6), 12, mix(c, WHITE, 0.3), bold=True)
            blit_text(screen, t2, (rr.x + 128, rr.y + 8), 10, DIM)
        blit_text(screen, f"费用 {b.cost('CAST')} 时间片 · 右键取消", (r.x + 12, r.bottom - 16), 10,
                  DIM, mono=False)

    # ------------------------------------------------------------ HUD
    def draw_hud(self, screen, b):
        self.draw_topbar(screen, b)
        self.draw_left(screen, b)
        self.draw_bottom(screen, b)

    def draw_topbar(self, screen, b):
        r = TOPBAR
        pygame.draw.rect(screen, (9, 12, 17), (0, 0, W, 76))
        pygame.draw.line(screen, (28, 38, 50), (0, 75), (W, 75), 1)
        # logo
        blit_text(screen, "悬垂", (22, 12), 30, WHITE, bold=True)
        blit_text(screen, "DANGLING", (96, 26), 12, CYAN, mono=True)
        blit_text(screen, "v1.0 demo", (96, 42), 9, DIM, mono=True)
        pygame.draw.line(screen, dim(CYAN, 0.5), (96, 22), (162, 22), 1)
        # 房间
        room = b.room
        x = 196
        blit_text(screen, room["code"], (x, 14), 11, AMBER, mono=True, bold=True)
        blit_text(screen, room["title"], (x, 30), 19, WHITE, bold=True)
        blit_text(screen, room["cn"], (x, 53), 11, DIM)
        # 进度
        px = 470
        for i in range(9):
            cx = px + i * 19
            if i < b.room_index:
                col = dim(CYAN, 0.8)
            elif i == b.room_index:
                col = WHITE
            else:
                col = (44, 52, 64)
            if i == b.room_index:
                pygame.draw.rect(screen, col, (cx, 26, 11, 11))
            else:
                pygame.draw.rect(screen, col, (cx, 30, 8, 4))
        blit_text(screen, f"{b.room_index + 1}/9", (px + 176, 24), 12, DIM, mono=True)

        # GC 计时
        gc_f = 1.0 - max(0.0, min(1.0, b.gc_timer / b.body["gc_period"]))
        if b.gc_active > 0:
            gc_f = max(0.0, b.gc_active / 2.2)
        rr = pygame.Rect(660, 28, 250, 9)
        col = CYAN if b.gc_active > 0 else (AMBER if b.gc_timer < 4 else dim(CYAN, 0.6))
        bar(screen, rr, gc_f, col, (20, 26, 34))
        if b.gc_active > 0:
            txt = "GC PAUSE"
        else:
            txt = "GC in %.1fs" % max(0.0, b.gc_timer)
        blit_text(screen, txt, (rr.x, rr.y - 15), 10,
                  col if b.gc_timer < 4 else DIM, mono=True)
        blit_text(screen, "STOP-THE-WORLD", (rr.right + 8, rr.y - 14), 9, dim(DIM, 0.8), mono=True)
        if b.plan:
            blit_text(screen, "PLAN", (rr.right + 8, rr.y + 2), 13, AMBER, bold=True, mono=True)
        # 分数 / 命
        blit_text(screen, "SCORE", (1000, 14), 9, DIM, mono=True)
        blit_text(screen, f"{b.run.score:06d}", (1000, 26), 24, GOLD, bold=True, mono=True)
        blit_text(screen, "REF", (1150, 14), 9, DIM, mono=True)
        for i in range(3):
            cx = 1150 + i * 24
            cy = 44
            if i < b.lives:
                pts = [(cx, cy - 8), (cx + 8, cy), (cx, cy + 8), (cx - 8, cy)]
                pygame.draw.polygon(screen, RED, pts)
                glow(screen, cx, cy, 14, RED, 0.4)
            else:
                pts = [(cx, cy - 8), (cx + 8, cy), (cx, cy + 8), (cx - 8, cy)]
                pygame.draw.polygon(screen, (50, 40, 44), pts, 1)
        blit_text(screen, f"x{b.lives}", (1232, 36), 14, WHITE, bold=True, mono=True)
        # 暂停提示
        blit_text(screen, "SPACE 规划", (W - 190, 16), 10, DIM)
        blit_text(screen, "ESC 暂停", (W - 190, 32), 10, DIM)
        blit_text(screen, "F11 全屏", (W - 190, 48), 10, dim(DIM, 0.7))

    def draw_left(self, screen, b):
        x0 = 16
        y = 88
        # 身体
        body = b.body
        r = pygame.Rect(10, y, 226, 126)
        panel(screen, r, (12, 16, 22), dim(body["color"], 0.55), 4)
        bracket(screen, r, body["color"], 10, 1, 130)
        blit_text(screen, body["name"], (r.x + 12, r.y + 8), 19, body["color"], bold=True)
        blit_text(screen, body["en"], (r.x + 12 + text_w(body["name"], 19, True) + 8, r.y + 14),
                  9, dim(body["color"], 0.7), mono=True)
        pygame.draw.line(screen, dim(body["color"], 0.25), (r.x + 12, r.y + 38),
                         (r.right - 12, r.y + 38), 1)
        blit_text(screen, "被动 PASSIVE", (r.x + 12, r.y + 44), 9, dim(body["color"], 0.9))
        self.small_wrap(screen, body["passive"], (r.x + 12, r.y + 60), r.w - 24, 10,
                        (150, 170, 190))
        y = r.bottom + 10

        # 生命
        rr = pygame.Rect(x0, y, 226, 52)
        panel(screen, rr, (11, 15, 21), PANEL_LINE, 4)
        blit_text(screen, "LIFE", (rr.x + 10, rr.y + 6), 9, DIM, mono=True)
        hp, mx = (b.alias_pool.hp, b.alias_pool.max) if b.alias_pool else (b.hp, b.max_hp)
        bar(screen, pygame.Rect(rr.x + 10, rr.y + 20, 206, 10), hp / mx,
            RED if hp / mx < 0.35 else (GREEN if b.alias_pool else (200, 70, 80)),
            (24, 26, 32))
        blit_text(screen, f"{max(0, int(hp))} / {int(mx)}", (rr.right - 10, rr.y + 5),
                  10, DIM, anchor="topright", mono=True)
        if b.alias_pool:
            blit_text(screen, "共享血池", (rr.x + 44, rr.y + 5), 9, MAGENTA, mono=True)
        y = rr.bottom + 8

        # 时间片
        rr = pygame.Rect(x0, y, 226, 56)
        panel(screen, rr, (11, 15, 21), PANEL_LINE, 4)
        blit_text(screen, "TIME SLICE", (rr.x + 10, rr.y + 6), 9, DIM, mono=True)
        blit_text(screen, f"{int(b.slices)}/{b.max_slices}", (rr.right - 10, rr.y + 4),
                  11, CYAN, anchor="topright", mono=True, bold=True)
        pip_w = min(18, int((rr.w - 20) / max(1, b.max_slices)) - 2)
        for i in range(b.max_slices):
            cx = rr.x + 10 + i * (pip_w + 3)
            filled = i < int(b.slices)
            col = CYAN if filled else (30, 40, 50)
            if b.gc_active > 0:
                col = GREEN
            pygame.draw.rect(screen, col, (cx, rr.y + 24, pip_w, 10), border_radius=2)
            if filled:
                glow(screen, cx + pip_w / 2, rr.y + 29, 10, col, 0.25)
        # 堆
        blit_text(screen, "HEAP", (rr.x + 10, rr.y + 40), 9, DIM, mono=True)
        for i in range(b.max_heap):
            cx = rr.x + 52 + i * 15
            col = MAGENTA if i < b.heap else (34, 32, 44)
            pygame.draw.rect(screen, col, (cx, rr.y + 40, 9, 9), border_radius=2)
        y = rr.bottom + 8

        # 专注
        rr = pygame.Rect(x0, y, 226, 30)
        panel(screen, rr, (11, 15, 21), PANEL_LINE, 4)
        blit_text(screen, "FOCUS", (rr.x + 10, rr.y + 8), 9, DIM, mono=True)
        bar(screen, pygame.Rect(rr.x + 56, rr.y + 10, 160, 7), b.focus / b.focus_max,
            AMBER if b.plan else dim(AMBER, 0.55), (24, 26, 32))
        y = rr.bottom + 12

        # 工具
        blit_text(screen, "TOOLS", (x0 + 2, y), 10, DIM, mono=True)
        blit_text(screen, "左键拖拽 · 右键写入", (LEFTPANEL.right - 14, y), 9,
                  dim(DIM, 0.7), anchor="topright")
        y += 18
        for i in range(5):
            rr = pygame.Rect(8, y, 230, 38)
            active = b.tool == i
            bgc = (18, 30, 40) if active else (11, 15, 21)
            panel(screen, rr, bgc, dim(CYAN, 0.7) if active else PANEL_LINE, 4)
            if active:
                pygame.draw.rect(screen, CYAN, (rr.x, rr.y + 4, 2, rr.h - 8))
            blit_text(screen, TOOL_KEYS[i], (rr.x + 12, rr.y + 9), 12,
                      CYAN if active else DIM, mono=True, bold=True)
            blit_text(screen, TOOL_NAMES[i], (rr.x + 30, rr.y + 6), 12,
                      WHITE if active else (150, 164, 180), bold=active, mono=True)
            blit_text(screen, TOOL_CN[i], (rr.x + 30, rr.y + 21), 9,
                      CYAN if active else dim(DIM, 0.8))
            c = b.cost(["LINK", "CUT", "WEAK", "ALIAS", "CAST"][i])
            if c == 0:
                blit_text(screen, "免费", (rr.right - 10, rr.y + 13), 10, GREEN,
                          anchor="topright")
            else:
                blit_text(screen, f"{c} 片", (rr.right - 10, rr.y + 12), 10,
                          CYAN if active else dim(DIM, 0.9), anchor="topright")
            y = rr.bottom + 3
        y += 8

        # 内存 / 负载
        rr = pygame.Rect(x0, y, 226, 58)
        panel(screen, rr, (11, 15, 21), PANEL_LINE, 4)
        blit_text(screen, "MEMORY", (rr.x + 10, rr.y + 6), 9, DIM, mono=True)
        blit_text(screen, f"{int(b.memory)}%", (rr.right - 10, rr.y + 4), 10,
                  RED if b.memory > 60 else DIM, anchor="topright", mono=True)
        bar(screen, pygame.Rect(rr.x + 10, rr.y + 20, 206, 6), b.memory / 100,
            RED if b.memory > 60 else (120, 130, 110), (24, 26, 32))
        blit_text(screen, "LOAD", (rr.x + 10, rr.y + 34), 9, DIM, mono=True)
        lf = b.load_ratio()
        bar(screen, pygame.Rect(rr.x + 44, rr.y + 36, 172, 6), lf,
            AMBER if lf > 0.7 else dim(BLUE, 0.7), (24, 26, 32))
        y = rr.bottom + 8

        # 模块
        n_mod = len(b.run.modules)
        blit_text(screen, f"MODULES {n_mod}", (x0 + 2, y), 9, DIM, mono=True)
        y += 14
        for m in b.run.modules[-5:]:
            yy = y
            blit_text(screen, "▸", (x0 + 2, yy), 10, m["color"], mono=True)
            blit_text(screen, m["name"], (x0 + 14, yy), 10, mix(m["color"], WHITE, 0.2))
            y += 15
        if n_mod == 0:
            blit_text(screen, "每关结束选择一个模块", (x0 + 2, y), 9, dim(DIM, 0.7))

    def small_wrap(self, screen, s, pos, maxw, size, col):
        x, y = pos
        line = ""
        lines = []
        for ch in s:
            if ch == "\n":
                lines.append(line)
                line = ""
                continue
            if ch in "，。、；：！？）》」』%":
                line += ch
                continue
            if text_w(line + ch, size) > maxw and line:
                lines.append(line)
                line = ch
            else:
                line += ch
        if line:
            lines.append(line)
        for i, ln in enumerate(lines[:4]):
            blit_text(screen, ln, (x, y + i * (size + 4)), size, col)

    def draw_bottom(self, screen, b):
        r = BOTTOM
        pygame.draw.rect(screen, (9, 12, 17), r)
        pygame.draw.line(screen, (28, 38, 50), (r.x, r.y), (r.right, r.y), 1)
        hint = b.room.get("hint", "")
        self.small_wrap(screen, hint, (264, r.y + 12), 980, 12, (150, 166, 186))
        if b.toast_t > 0:
            blit_text(screen, "» " + b.toast_msg, (264, r.y + 50), 12,
                      mix(AMBER, WHITE, 0.4), bold=True)
        # 控制
        cx = W - 340
        blit_text(screen, "WASD 移动", (cx, r.y + 10), 10, DIM)
        blit_text(screen, "1-5 工具", (cx + 92, r.y + 10), 10, DIM)
        blit_text(screen, "按住 SPACE 规划", (cx, r.y + 26), 10, DIM)
        blit_text(screen, "右键 / F 写入", (cx + 92, r.y + 26), 10, DIM)
        blit_text(screen, "R 死代码消除", (cx, r.y + 42), 10, DIM)
        blit_text(screen, "M 静音", (cx + 92, r.y + 42), 10, DIM)

    # ------------------------------------------------------------ 关卡介绍
    def draw_intro(self, screen, b):
        k = b.intro_t / 2.1
        a = int(255 * min(1.0, k * 1.6))
        room = b.room
        ov = pygame.Surface((W, H), pygame.SRCALPHA)
        ov.fill((4, 6, 9, int(170 * min(1.0, k * 1.4))))
        screen.blit(ov, (0, 0))
        cx = W // 2
        yy = 300
        # 卡片
        card = pygame.Rect(cx - 470, yy - 96, 940, 320)
        s = pygame.Surface((card.w, card.h), pygame.SRCALPHA)
        pygame.draw.rect(s, (10, 14, 20, int(230 * min(1, k * 1.5))), (0, 0, card.w, card.h),
                         border_radius=6)
        pygame.draw.rect(s, with_alpha(AMBER, int(120 * min(1, k * 1.5))), (0, 0, card.w, card.h),
                         1, border_radius=6)
        screen.blit(s, card.topleft)
        bracket(screen, card, AMBER, 18, 2, int(160 * min(1, k * 1.5)))
        blit_text(screen, f"ROOM {b.room_index + 1:02d} / 09    {room['code']}",
                  (cx, yy - 62), 11, AMBER, anchor="center", mono=True, alpha=a)
        blit_text(screen, room["title"], (cx, yy), 48, WHITE, anchor="center",
                  bold=True, alpha=a, shadow=3)
        blit_text(screen, room["cn"], (cx, yy + 58), 16, CYAN, anchor="center", alpha=a)
        pygame.draw.line(screen, dim(AMBER, 0.45), (cx - 200, yy - 78), (cx + 200, yy - 78), 1)
        blit_text(screen, room["intro"], (cx, yy + 92), 13, DIM, anchor="center", alpha=a)
        # 目标提示
        hint = room.get("hint", "")
        self.wrap_center(screen, hint, cx, yy + 128, 820, 12, (196, 210, 228), a)
        blit_text(screen, "点击跳过", (cx, 700), 11, dim(DIM, 0.7), anchor="center", alpha=a)

    def wrap_center(self, screen, s, cx, y, maxw, size, col, alpha=255):
        lines = []
        cur = ""
        for ch in s:
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
        for i, ln in enumerate(lines[:3]):
            blit_text(screen, ln, (cx, y + i * (size + 8)), size, col,
                      anchor="midtop", alpha=alpha)

    def draw_clear(self, screen, b):
        k = b.end_t / 2.2
        ov = pygame.Surface((W, H), pygame.SRCALPHA)
        ov.fill((4, 22, 16, int(90 * min(1, k * 2))))
        screen.blit(ov, (0, 0))
        blit_text(screen, "ROOM CLEAR", (W // 2, 420), 40, GREEN, anchor="center",
                  bold=True, mono=True, shadow=3)
        blit_text(screen, "引用图已重置", (W // 2, 470), 13, dim(GREEN, 0.8),
                  anchor="center")
