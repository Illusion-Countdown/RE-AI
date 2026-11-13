"""终端日志面板。"""

from __future__ import annotations

import pygame

import settings
from ui.widgets import draw_text, panel, wrap_lines


class Terminal:
    def __init__(self, max_lines: int = 80) -> None:
        self.lines: list[tuple[str, tuple[int, int, int]]] = []
        self.max_lines = max_lines

    def add(self, text: str, color: tuple[int, int, int] | None = None) -> None:
        if not text:
            return
        self.lines.append((str(text), color or settings.TEXT))
        if len(self.lines) > self.max_lines:
            del self.lines[: len(self.lines) - self.max_lines]

    def extend(self, items: list[tuple[str, tuple[int, int, int]]]) -> None:
        for text, color in items:
            self.add(text, color)

    def draw(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        panel(surface, rect, fill=settings.PANEL)
        draw_text(surface, "TERMINAL // stdout", 12, settings.MUTED, (rect.x + 16, rect.y + 9))
        pygame.draw.line(
            surface,
            settings.GRID,
            (rect.x + 16, rect.y + 28),
            (rect.right - 16, rect.y + 28),
        )

        max_width = rect.width - 34
        expanded: list[tuple[str, tuple[int, int, int]]] = []
        for text, color in self.lines:
            for line in wrap_lines(text, 14, max_width):
                expanded.append((line, color))
        visible = expanded[-4:]
        y = rect.y + 36
        for text, color in visible:
            draw_text(surface, ">", 14, settings.GREEN, (rect.x + 16, y))
            draw_text(surface, text, 14, color, (rect.x + 30, y))
            y += 19
