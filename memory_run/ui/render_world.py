# -*- coding: utf-8 -*-
from .render_deps import *

class WorldMixin:
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
            if not n.alive or n is b.player_node:
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
        if e.kind == PARRY:
            pulse = 0.5 + 0.5 * math.sin(b.time * 18)
            pygame.draw.lines(surf, with_alpha(RED, 70), False, pts, 10)
            pygame.draw.lines(surf, GOLD if pulse > 0.5 else RED,
                              False, pts, 3)
            mx, my = pts[len(pts) // 2]
            blit_text(surf, "CUT!", (mx, my - 14), 13, GOLD,
                      anchor="midtop", mono=True, bold=True)
            return
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
        """绘制 AI 娘自机；数据结构不是玩家。"""
        n = b.player_node
        girl = b.run.girl
        col = girl["color"]
        x, y = n.x + ox, n.y + oy
        R = 21
        # 轨迹
        self.trail.append((n.x, n.y))
        if len(self.trail) > 26:
            self.trail.pop(0)
        for i, (tx, ty) in enumerate(self.trail[:-1]):
            a = i / max(1, len(self.trail))
            pygame.draw.circle(surf, mix((6, 8, 12), col, a * 0.6),
                               (int(tx + ox), int(ty + oy)),
                               max(1, int(a * 3)))
        # 目标指示
        mx, my = b.mouse
        dx, dy = mx - x, my - y
        d = math.hypot(dx, dy) or 1
        if d > 24:
            ex, ey = x + dx / d * 30, y + dy / d * 30
            pygame.draw.line(surf, with_alpha(col, 70), (x, y), (ex, ey), 1)
            pygame.draw.circle(surf, with_alpha(col, 120),
                               (int(mx), int(my)), 4, 1)
        # 径向脉冲
        pulse = 0.5 + 0.5 * math.sin(self.t * 3)
        glow(surf, x, y, 54, col, 0.38 + 0.10 * pulse)
        pygame.draw.circle(surf, with_alpha(col, 60), (int(x), int(y)),
                           int(28 + pulse * 6), 1)
        # 本体：AI 娘
        draw_girl(surf, x, y + 2, 0.70, col, girl["hair"], 0, self.t)
        # 头顶手牌球：左=上一张，中=当前选中，右=下一张
        order = b.hand_order()
        orbs = [order[2][1], order[0][1], order[1][1]]
        spots = [(-60, -50), (0, -76), (60, -50)]
        for i, (card, (dx, dy)) in enumerate(zip(orbs, spots)):
            oxp, oyp = x + dx, y + dy
            if card is None:
                pygame.draw.circle(surf, (26, 34, 44), (int(oxp), int(oyp)),
                                   9, 1)
                continue
            c = card.color
            glow(surf, oxp, oyp, 30, c, 0.36)
            pygame.draw.circle(surf, dim(c, 0.35), (int(oxp), int(oyp)), 9)
            pygame.draw.circle(surf, c, (int(oxp), int(oyp)), 9, 2)
            pygame.draw.circle(surf, mix(c, WHITE, 0.55),
                               (int(oxp), int(oyp)), 3)
            if i == 1:
                pygame.draw.circle(surf, GOLD, (int(oxp), int(oyp)), 13, 2)
        # 角色旁选中牌回声：不低头也能确认当前牌名
        sel = b.hand.slots[b.selected]
        if sel is not None:
            name = sel.name
            pw = text_w(name, 10, bold=True) + 34
            pill = pygame.Rect(int(x - pw / 2), int(y - 108), pw, 20)
            pygame.draw.rect(surf, (7, 11, 16, 200), pill, border_radius=5)
            pygame.draw.rect(surf, sel.color, pill, 1, border_radius=5)
            icon = pygame.Rect(pill.x + 4, pill.y + 3, 14, 14)
            draw_card_mini(surf, icon, sel.key, sel.up)
            blit_text(surf, name, (pill.x + 22, pill.y + 3), 10,
                      WHITE, bold=True)
        if b.iframe > 0:
            a = int(120 + 100 * math.sin(self.t * 20))
            pygame.draw.circle(surf, with_alpha(WHITE, a), (int(x), int(y)),
                               R + 7, 1)
        if b.alias_pool:
            blit_text(surf, "ALIASED", (x, y - 126), 10, MAGENTA,
                      anchor="midtop", mono=True)
        blit_text(surf, girl["name"], (x, y + 42), 10, dim(col, 0.9),
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
        elif n.kind == "LUNGER":
            self.shape_alloc(surf, n, x, y, col, hover)
        elif n.kind == "EXECUTOR":
            self.shape_cycler(surf, n, x, y, col, hover)
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
        """DANGLING shape_eraser：抖动脏对象。"""
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
