# -*- coding: utf-8 -*-
"""地图场景：提交图 + revert / branch / merge。

这一屏是"git 当玩法"的地方，所以画得比战斗还认真。
"""
import pygame

import config
from core import actions
from data import CARDS, EDGES, NODES
from ui import draw, theme

NODE_W, NODE_H = 150, 52
X0, Y0 = 120, 150
GAP_Y = 96


def node_pos(node_id):
    """按 (层, 同层第几个) 算坐标。固定网格，不搞自动排布。"""
    info = NODES[node_id]
    layer = info["layer"]
    siblings = [n for n, d in NODES.items() if d["layer"] == layer]
    idx = sorted(siblings).index(node_id) if node_id in siblings else 0
    n = max(1, len(siblings))
    total_w = n * (NODE_W + 40) - 40
    start_x = config.WIDTH // 2 - total_w // 2
    return start_x + idx * (NODE_W + 40), Y0 + layer * GAP_Y


class MapScreen:
    def __init__(self, app):
        self.app = app
        self.state = app.state
        self.mode = "advance"       # advance / revert
        self.hover = None

    # ---------------------------------------------------------------- 输入

    def handle(self, e):
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_r:
                self.mode = "revert" if self.mode == "advance" else "advance"
            elif e.key == pygame.K_b:
                err = actions.branch(self.state)
                self.app.toast(err or "分支已开，收获暂存")
            elif e.key == pygame.K_m:
                err = actions.merge(self.state)
                self.app.toast(err or "合并完成")
            elif e.key == pygame.K_RETURN:
                self.mode = "advance"
            return

        if e.type == pygame.MOUSEMOTION:
            self.hover = self._node_at(e.pos)
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            node = self._node_at(e.pos)
            if node:
                self._click_node(node)

    def _node_at(self, pos):
        for nid in NODES:
            x, y = node_pos(nid)
            if pygame.Rect(x, y, NODE_W, NODE_H).collidepoint(pos):
                return nid
        return None

    def _click_node(self, node):
        st = self.state
        if self.mode == "revert":
            err = actions.revert(st, node)
            self.app.toast(err or f"已回退到 {node}")
            self.mode = "advance"
            return

        if node in st.map.children():
            ntype = st.map.node_type(node)
            err = actions.advance(st, node)
            if err:
                self.app.toast(err)
                return
            if ntype == "event":
                actions.finish_node(st)
                self.app.toast("事件：内存 +5 格")
                return
            self.app.enter_node()
        else:
            self.app.toast("只能走向相邻的节点（R 可以回退）")

    # ---------------------------------------------------------------- 更新

    def update(self, dt):
        pass

    # ---------------------------------------------------------------- 绘制

    def draw(self, screen):
        screen.fill(theme.BG)
        draw.text(screen, "提交图", 30, theme.TEXT, (60, 40), "topleft", True)
        draw.text(screen, "点击相邻节点推进 · R 回退 · B 分支 · M 合并",
                  16, theme.MUTED, (60, 84))

        self._draw_edges(screen)
        self._draw_nodes(screen)
        self._draw_sidebar(screen)

        if self.mode == "revert":
            draw.text(screen, "回退模式：点一个走过的节点", 20, theme.WARN,
                      (640, 40), "center", True)

    def _draw_edges(self, screen):
        st = self.state
        for a, kids in EDGES.items():
            for b in kids:
                x1, y1 = node_pos(a)
                x2, y2 = node_pos(b)
                start = (x1 + NODE_W // 2, y1 + NODE_H)
                end = (x2 + NODE_W // 2, y2)
                on_path = (a in st.map.path and b in st.map.path
                           and st.map.path.index(b) == st.map.path.index(a) + 1)
                color = theme.ACCENT if on_path else theme.LINE
                pygame.draw.line(screen, color, start, end, 3 if on_path else 1)

    def _draw_nodes(self, screen):
        st = self.state
        for nid, info in NODES.items():
            x, y = node_pos(nid)
            rect = pygame.Rect(x, y, NODE_W, NODE_H)

            visited = nid in st.map.path
            is_head = nid == st.map.head
            orphan = st.map.is_orphan(nid)
            reachable = nid in st.map.children()

            if is_head:
                fill, border = (30, 60, 96), theme.ACCENT
            elif orphan:
                fill, border = (30, 26, 26), (90, 60, 60)
            elif visited:
                fill, border = (24, 32, 40), theme.LINE
            elif reachable:
                fill, border = (22, 28, 36), theme.OK
            else:
                fill, border = (18, 20, 26), theme.LINE

            if self.hover == nid and (reachable or self.mode == "revert"):
                fill = (36, 44, 58)

            draw.panel(screen, rect, fill, border, 10)
            draw.text(screen, info["label"], 15,
                      theme.TEXT if (visited or reachable) else theme.MUTED,
                      rect.center, "center", is_head)
            if orphan:
                draw.text(screen, "孤儿", 12, theme.DANGER, (rect.right - 6, rect.bottom - 4),
                          "bottomright")

    def _draw_sidebar(self, screen):
        st = self.state
        x = 980
        draw.panel(screen, pygame.Rect(x, 130, 260, 420))
        draw.text(screen, "状态", 20, theme.TEXT, (x + 20, 150), "topleft", True)

        rows = [
            ("名额", f"{st.quota}"),
            ("腐化", f"{st.corruption:.0%}"),
            ("生命", f"{int(st.player.hp)}/{int(st.player.max_hp)}"),
            ("内存", f"{st.memory.stats()['used']}/{st.memory.stats()['total']}"),
        ]
        yy = 190
        for k, v in rows:
            draw.text(screen, k, 15, theme.MUTED, (x + 20, yy))
            draw.text(screen, v, 15, theme.TEXT, (x + 90, yy), "topleft", True)
            yy += 34

        deck = ", ".join(CARDS[c]["name"] for c in st.memory.active_cards()) or "空"
        draw.text(screen, "牌库", 15, theme.MUTED, (x + 20, yy))
        yy += 24
        line = ""
        f = theme.font(14)
        for ch in deck:
            if f.size(line + ch)[0] > 200:
                draw.text(screen, line, 14, theme.CARD, (x + 20, yy))
                yy += 20
                line = ch
            else:
                line += ch
        if line:
            draw.text(screen, line, 14, theme.CARD, (x + 20, yy))

        if st.branch_loot:
            yy += 10
            draw.text(screen, "支线暂存", 15, theme.PURPLE, (x + 20, yy))
            draw.text(screen, ", ".join(CARDS[c]["name"]
                                        for c in st.branch_loot),
                      15, theme.PURPLE, (x + 20, yy + 22))

        draw.text(screen, "路线", 15, theme.MUTED, (60, 640))
        draw.text(screen, st.map.ascii(), 14, theme.TEXT, (110, 640))
