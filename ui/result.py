# -*- coding: utf-8 -*-
"""结算：输出你的提交图。

这是整个游戏的情感落点 —— 不是"你赢了"，是"你留下了什么"。
"""
import pygame

import config
from data import CARDS
from ui import draw, theme


class ResultScreen:
    def __init__(self, app, win):
        self.app = app
        self.state = app.state
        self.win = win

    def handle(self, e):
        if e.type == pygame.KEYDOWN and e.key == pygame.K_r:
            self.app.back_to_menu()

    def update(self, dt):
        pass

    def draw(self, screen):
        screen.fill(theme.BG)
        st = self.state

        title = "v1.0 已发布" if self.win else "进程终止"
        color = theme.OK if self.win else theme.DANGER
        draw.text(screen, title, 46, color, (640, 70), "center", True)

        # 左边：统计
        draw.panel(screen, pygame.Rect(70, 150, 380, 420))
        draw.text(screen, "统计", 20, theme.TEXT, (100, 172), "topleft", True)

        stats = [
            ("击杀", st.kills),
            ("剩余名额", st.quota),
            ("腐化", f"{st.corruption:.0%}"),
            ("孤儿节点", "、".join(st.map.orphans) or "无"),
            ("内存", f"{st.memory.stats()['used']}/{st.memory.stats()['total']}"),
            ("碎格", st.memory.stats()["broken"]),
        ]
        y = 220
        for k, v in stats:
            draw.text(screen, k, 16, theme.MUTED, (100, y))
            draw.text(screen, str(v), 16, theme.TEXT, (220, y), "topleft", True)
            y += 38

        draw.text(screen, "存活卡牌", 16, theme.MUTED, (100, y + 10))
        yy = y + 36
        for cid in st.memory.active_cards():
            draw.text(screen, f"· {CARDS[cid]['name']}", 15, theme.CARD, (110, yy))
            yy += 24

        # 右边：提交图
        draw.panel(screen, pygame.Rect(490, 150, 720, 420))
        draw.text(screen, "提交图", 20, theme.TEXT, (520, 172), "topleft", True)

        lines = ["$ git log --graph --oneline", ""]
        path = st.map.path
        for i, nid in enumerate(reversed(path)):
            mark = "*" if i == 0 else "*"
            tag = "  ← 孤儿" if st.map.is_orphan(nid) else ""
            lines.append(f"{mark} {nid:<3} {st.map.label(nid)}{tag}")
        if st.map.scouted:
            lines.append("")
            lines.append("支线侦察过：" + ", ".join(st.map.scouted))

        y = 214
        for line in lines[:14]:
            color = theme.MUTED if line.startswith("$") else theme.TEXT
            draw.text(screen, line, 14, color, (520, y), "topleft")
            y += 24

        draw.text(screen, "按 R 重新开始", 16, theme.ACCENT,
                  (640, 640), "center", True)
        draw.text(screen, "你不需要战胜过去，你只需要发布。", 14, theme.MUTED,
                  (640, 672), "center")
