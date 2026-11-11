"""新手引导与中文目标栏。

只负责“告诉玩家现在该做什么”，不修改任何游戏状态。
"""

from __future__ import annotations

from dataclasses import dataclass

import pygame

import settings
from ui.widgets import draw_text, draw_wrapped_text, get_font, panel


@dataclass(frozen=True)
class GuideStep:
    id: str
    title: str
    body: str
    tip: str
    highlight: str


STEPS: tuple[GuideStep, ...] = (
    GuideStep(
        "map",
        "第一步 · 选一个节点",
        "你是调度器，不是操作员。先从提交图上选一条路；A/B 是二选一，走哪条，另一条就变成孤儿。",
        "点节点进入编译期；S 商店、V 事件、B 分支、R 回退。",
        "map",
    ),
    GuideStep(
        "place",
        "第二步 · 把算法放进内存",
        "按 1~6 选一个交换区里的棋子，再点亮的蓝色内存格。棋子会占格，也会替核心挡路。",
        "先放 1~3 个棋子；形状越大，占的内存越多。",
        "bench",
    ),
    GuideStep(
        "jurisdiction",
        "第三步 · 决定 AI 能看见谁",
        "按 J 打开辖区画笔，点内存格圈出 DeepSeek 的辖区。只有辖区内的棋子吃 +20% 技能伤害，并积攒大招。",
        "你只有 12 格视野，棋子却有更多——这就是本作最重要的取舍。",
        "ai",
    ),
    GuideStep(
        "run",
        "第四步 · 开始运行",
        "点『开始运行』。进入运行时后，棋子会按自己的时间片自动出手；你不能再移动它们。",
        "运行时你只有指令卡和 DeepSeek 大招。",
        "run",
    ),
    GuideStep(
        "cards",
        "运行时 · 你只能发信号",
        "点右侧一张手牌，再点棋子 / 敌人 / 棋盘释放。算力每波重置，卡不要舍不得打。",
        "绿色读条是棋子的下一次出手；蓝色读条是 DeepSeek 充能。",
        "hand",
    ),
    GuideStep(
        "ultimate",
        "大招 · 长思考 CoT",
        "DeepSeek 充能到 100 后，点右侧头像。6 秒内 O(n²)/O(2ⁿ) 不再卡顿，出手更快。",
        "充能来自辖区内棋子造成的伤害。",
        "ultimate",
    ),
)

HELP_SECTIONS = [
    ("一局流程", [
        "选节点 → 编译期（摆棋子 / 划辖区）",
        "→ 运行时（3 波，棋子自己打）",
        "→ 抽卡 / 商店 → 下一层",
        "→ 4 层后打首领 → 结算",
    ]),
    ("编译期", [
        "1~6：选择交换区棋子",
        "点击亮蓝内存格：放置",
        "J：辖区画笔；点格子增删",
        "E：扩容一个扇区（碎片）",
        "O：超频；X：撤回",
        "R / Enter：开始运行",
    ]),
    ("运行时", [
        "点手牌 → 点目标 / 棋盘",
        "点右侧 DeepSeek 头像：大招",
        "绿色读条：棋子出手进度",
        "核心生命归零：本节点失败",
    ]),
    ("地图", [
        "点击节点：进入",
        "B：分支；R：回退",
        "S：商店；V：事件",
        "G：打孤儿残影，清技术债",
    ]),
    ("记住", [
        "环境随机，不能覆写",
        "对齐摩擦 / 多 AI 本版不做",
        "棋子是钉子，不会自己走",
        "你决定谁跑、跑在哪、给多少资源",
    ]),
]


class Guide:
    def __init__(self) -> None:
        self.step = 0
        self.visible = True
        self.help_visible = False
        self.time = 0.0

    @property
    def current(self) -> GuideStep:
        return STEPS[min(self.step, len(STEPS) - 1)]

    def set_step(self, step_id: str) -> None:
        for index, step in enumerate(STEPS):
            if step.id == step_id:
                self.step = max(self.step, index)
                return

    def advance(self) -> None:
        if self.step < len(STEPS) - 1:
            self.step += 1
        else:
            self.visible = False

    def hide(self) -> None:
        self.visible = False

    def toggle_help(self) -> None:
        self.help_visible = not self.help_visible

    def update(self, dt: float) -> None:
        self.time += dt

    # ------------------------------------------------------------------
    def objective(self, scene) -> str:
        mode = scene.mode
        if mode == "map":
            return "当前目标：选一个节点进入；A/B 二选一，另一条会变成孤儿"
        if mode == "compile":
            return "当前目标：放棋子 → 划 DeepSeek 辖区 → 点『开始运行』"
        if mode == "battle":
            if scene.battle and scene.battle.boss_mode:
                return "当前目标：撑住核心，打穿三阶段生产环境"
            return "当前目标：棋子自动打；点卡干预，充能够了放大招"
        if mode == "draft":
            return "当前目标：三选一，把新算法放进交换区"
        if mode == "shop":
            return "当前目标：花碎片补强；Enter 离开商店"
        if mode == "event":
            return "当前目标：选一个事件奖励"
        if mode == "merge":
            return "当前目标：合并冲突，二选一"
        if mode == "result":
            return "本局结束：R 重开一局"
        return ""

    def draw_objective(self, surface: pygame.Surface, scene) -> None:
        rect = pygame.Rect(24, 650, 1232, 42)
        panel(surface, rect, fill=(10, 15, 22), border=settings.GRID)
        draw_text(surface, self.objective(scene), 13, settings.TEXT, (rect.x + 14, rect.y + 7))
        hint = "H / F1 帮助"
        if self.visible:
            hint = "T 下一步  ·  " + hint
        w = get_font(11).size(hint)[0]
        draw_text(surface, hint, 11, settings.MUTED, (rect.right - w - 14, rect.y + 14))

    def draw_card(self, surface: pygame.Surface, scene) -> None:
        if not self.visible or self.help_visible or scene.mode in ("result",):
            return
        step = self.current
        if step.id in ("place", "jurisdiction", "run") and scene.mode != "compile":
            return
        if step.id in ("cards", "ultimate") and scene.mode != "battle":
            return
        rect = pygame.Rect(24, 526, 610, 108)
        panel(surface, rect, fill=(12, 18, 27), border=settings.CYAN, width=1)
        pygame.draw.rect(surface, settings.CYAN, (rect.x, rect.y, 3, rect.height), border_radius=2)
        draw_text(surface, step.title, 15, settings.CYAN, (rect.x + 16, rect.y + 12), bold=True)
        draw_wrapped_text(surface, step.body, 12, settings.TEXT,
                          (rect.x + 16, rect.y + 38), rect.width - 32, line_height=18)
        draw_text(surface, "提示：" + step.tip, 10, settings.AMBER,
                  (rect.x + 16, rect.bottom - 22))
        draw_text(surface, "T 跳过/下一步", 10, settings.MUTED, (rect.right - 110, rect.bottom - 22))
        self._draw_highlight(surface, scene, step.highlight)

    def _draw_highlight(self, surface: pygame.Surface, scene, key: str) -> None:
        rect = None
        if key == "map":
            rect = pygame.Rect(60, 200, 740, 310)
        elif key == "bench":
            rect = pygame.Rect(662, 252, 250, 190)
        elif key == "ai":
            rect = pygame.Rect(662, 178, 560, 62)
        elif key == "run":
            rect = pygame.Rect(654, 602, 312, 50)
        elif key == "hand":
            rect = pygame.Rect(662, 260, 560, 330)
        elif key == "ultimate":
            rect = pygame.Rect(1154, 86, 88, 74)
        if rect is None:
            return
        pulse = 0.55 + 0.45 * abs((self.time * 1.8) % 2.0 - 1.0)
        glow = pygame.Surface((settings.WIDTH, settings.HEIGHT), pygame.SRCALPHA)
        pygame.draw.rect(glow, (110, 190, 255, int(190 * pulse)), rect, width=2, border_radius=8)
        surface.blit(glow, (0, 0))
        draw_text(surface, "★", 13, settings.CYAN, (rect.right - 4, rect.y - 10))

    def draw_help(self, surface: pygame.Surface) -> None:
        if not self.help_visible:
            return
        dim = pygame.Surface((settings.WIDTH, settings.HEIGHT), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 190))
        surface.blit(dim, (0, 0))
        rect = pygame.Rect(150, 78, 980, 566)
        panel(surface, rect, fill=(10, 16, 24), border=settings.CYAN, radius=10)
        draw_text(surface, "调度器手册", 30, settings.WHITE, (rect.x + 28, rect.y + 20), bold=True)
        draw_text(surface, "你不是程序员。你决定谁跑、跑在哪、给多少资源。", 13,
                  settings.MUTED, (rect.x + 30, rect.y + 62))
        col_x = [rect.x + 30, rect.x + 360, rect.x + 690]
        col_w = 300
        for index, (title, lines) in enumerate(HELP_SECTIONS):
            col = index % 3
            row = index // 3
            x = col_x[col]
            y = rect.y + 108 + row * 210
            draw_text(surface, title, 16, settings.AMBER, (x, y), bold=True)
            pygame.draw.line(surface, settings.GRID, (x, y + 24), (x + col_w - 20, y + 24))
            yy = y + 34
            for line in lines:
                draw_text(surface, "· " + line, 12, settings.TEXT, (x, yy))
                yy += 22
        draw_text(surface, "H / F1 关闭手册  ·  Esc 关闭", 12, settings.MUTED,
                  (rect.centerx, rect.bottom - 26), center=True)
