"""启动页：调度器进入腐烂机器。"""

from __future__ import annotations

import pygame

import settings
from scenes.base import Scene
from ui.widgets import draw_background, draw_text, draw_topbar, panel


class BootScene(Scene):
    def __init__(self, app) -> None:
        super().__init__(app)
        self.time = 0.0
        self.leaving = False
        self.lines = [
            "$ ./scheduler --attach 0x7f3a",
            "[OK] 内存块已分配：37 格",
            "[OK] 进程组：3 个算法",
            "[WARN] 外部写入正在增加",
            "",
            "> 你不是程序员。你是调度器。",
        ]

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_ESCAPE:
            self.app.quit()
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE) and not self.leaving:
            self.leaving = True
            self.app.start_game()

    def update(self, dt: float) -> None:
        self.time += dt

    def draw(self, surface: pygame.Surface) -> None:
        draw_background(surface)
        draw_topbar(surface, "RUNTIME 4.0", "SCHEDULER // ATTACH", "演示")
        draw_text(surface, "RUNTIME", 76, settings.WHITE, (84, 150), bold=True)
        draw_text(surface, "4.0", 76, settings.BLUE, (84, 235), bold=True)
        draw_text(surface, "你不写代码。你只决定谁跑、跑在哪、给多少算力。", 18,
                  settings.MUTED, (90, 340))
        draw_text(surface, "① 选节点    ② 放棋子 · 划辖区    ③ 运行时只出牌", 12,
                  settings.CYAN, (90, 378))
        box = pygame.Rect(760, 140, 430, 360)
        panel(surface, box, fill=settings.PANEL, border=settings.GRID)
        draw_text(surface, "启动日志", 12, settings.AMBER, (box.x + 22, box.y + 18), bold=True)
        y = box.y + 56
        for line in self.lines:
            color = settings.GREEN if line.startswith("[OK]") else settings.RED if line.startswith("[WARN]") else settings.TEXT
            draw_text(surface, line, 14, color, (box.x + 22, y))
            y += 28
        draw_text(surface, "按 Enter 接管内存", 20, settings.GREEN,
                  (settings.WIDTH // 2, 600), center=True, bold=True)
        draw_text(surface, "F11 / Alt+Enter 全屏  ·  Enter 开始  ·  Esc 退出", 12, settings.MUTED,
                  (settings.WIDTH // 2, 640), center=True)
