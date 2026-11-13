"""通用 UI：字体、文字、按钮、面板、打字机、扫描线。"""

from __future__ import annotations

from typing import Callable

import pygame

import settings


_FONT_CACHE: dict[tuple[int, bool], pygame.font.Font] = {}
_SCANLINE_CACHE: pygame.Surface | None = None
_BG_CACHE: pygame.Surface | None = None


def draw_background(surface: pygame.Surface) -> None:
    global _BG_CACHE
    if _BG_CACHE is None:
        bg = pygame.Surface((settings.WIDTH, settings.HEIGHT))
        bg.fill(settings.BG)
        for x in range(0, settings.WIDTH, 40):
            pygame.draw.line(bg, (17, 23, 30), (x, 0), (x, settings.HEIGHT))
        for y in range(0, settings.HEIGHT, 40):
            pygame.draw.line(bg, (17, 23, 30), (0, y), (settings.WIDTH, y))
        glow = pygame.Surface((settings.WIDTH, settings.HEIGHT), pygame.SRCALPHA)
        pygame.draw.circle(glow, (26, 75, 120, 34), (180, 80), 340)
        pygame.draw.circle(glow, (110, 34, 40, 22), (1130, 650), 320)
        bg.blit(glow, (0, 0))
        _BG_CACHE = bg
    surface.blit(_BG_CACHE, (0, 0))


def get_font(size: int, bold: bool = False) -> pygame.font.Font:
    key = (size, bold)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    path = settings.font_file()
    if path is not None:
        font = pygame.font.Font(str(path), size)
    else:
        font = pygame.font.SysFont("microsoftyahei", size, bold=bold)
    font.set_bold(bold)
    _FONT_CACHE[key] = font
    return font


def draw_text(
    surface: pygame.Surface,
    text: str,
    size: int,
    color: tuple[int, int, int],
    pos: tuple[int, int],
    *,
    center: bool = False,
    bold: bool = False,
) -> pygame.Rect:
    image = get_font(size, bold).render(str(text), True, color)
    rect = image.get_rect()
    if center:
        rect.center = pos
    else:
        rect.topleft = pos
    surface.blit(image, rect)
    return rect


def measure(text: str, size: int, bold: bool = False) -> tuple[int, int]:
    return get_font(size, bold).size(str(text))


def wrap_lines(text: str, size: int, max_width: int, bold: bool = False) -> list[str]:
    """按字符换行，中文和英文都适用。"""
    font = get_font(size, bold)
    lines: list[str] = []
    for raw_line in str(text).split("\n"):
        current = ""
        for char in raw_line:
            test = current + char
            if font.size(test)[0] <= max_width or not current:
                current = test
            else:
                lines.append(current)
                current = char
        lines.append(current)
    return lines


def draw_wrapped_text(
    surface: pygame.Surface,
    text: str,
    size: int,
    color: tuple[int, int, int],
    pos: tuple[int, int],
    max_width: int,
    *,
    line_height: int | None = None,
    bold: bool = False,
) -> int:
    line_height = line_height or int(size * 1.55)
    y = pos[1]
    for line in wrap_lines(text, size, max_width, bold):
        draw_text(surface, line, size, color, (pos[0], y), bold=bold)
        y += line_height
    return y


def panel(
    surface: pygame.Surface,
    rect: pygame.Rect | tuple[int, int, int, int],
    *,
    fill: tuple[int, int, int] = settings.PANEL,
    border: tuple[int, int, int] = settings.GRID,
    radius: int = 10,
    width: int = 1,
) -> pygame.Rect:
    rect = pygame.Rect(rect)
    pygame.draw.rect(surface, fill, rect, border_radius=radius)
    pygame.draw.rect(surface, border, rect, width=width, border_radius=radius)
    return rect


def draw_bar(
    surface: pygame.Surface,
    rect: pygame.Rect | tuple[int, int, int, int],
    ratio: float,
    color: tuple[int, int, int],
    *,
    bg: tuple[int, int, int] = (12, 16, 22),
) -> None:
    rect = pygame.Rect(rect)
    ratio = max(0.0, min(1.0, ratio))
    pygame.draw.rect(surface, bg, rect, border_radius=5)
    inner = rect.inflate(-4, -4)
    inner.width = int(inner.width * ratio)
    if inner.width > 0:
        pygame.draw.rect(surface, color, inner, border_radius=4)
    pygame.draw.rect(surface, settings.GRID, rect, width=1, border_radius=5)


def darken(color: tuple[int, int, int], amount: int = 25) -> tuple[int, int, int]:
    return tuple(max(0, value - amount) for value in color)


def lighten(color: tuple[int, int, int], amount: int = 18) -> tuple[int, int, int]:
    return tuple(min(255, value + amount) for value in color)


def draw_dashed_rect(
    surface: pygame.Surface,
    rect: pygame.Rect,
    color: tuple[int, int, int],
    *,
    dash: int = 10,
    gap: int = 7,
    width: int = 1,
) -> None:
    x, y, w, h = rect
    for start in range(x, x + w, dash + gap):
        end = min(start + dash, x + w)
        pygame.draw.line(surface, color, (start, y), (end, y), width)
        pygame.draw.line(surface, color, (start, y + h), (end, y + h), width)
    for start in range(y, y + h, dash + gap):
        end = min(start + dash, y + h)
        pygame.draw.line(surface, color, (x, start), (x, end), width)
        pygame.draw.line(surface, color, (x + w, start), (x + w, end), width)


def draw_scanlines(surface: pygame.Surface) -> None:
    global _SCANLINE_CACHE
    if _SCANLINE_CACHE is None:
        overlay = pygame.Surface((settings.WIDTH, settings.HEIGHT), pygame.SRCALPHA)
        for y in range(0, settings.HEIGHT, 4):
            pygame.draw.line(overlay, (0, 0, 0, 18), (0, y), (settings.WIDTH, y), 1)
        _SCANLINE_CACHE = overlay
    surface.blit(_SCANLINE_CACHE, (0, 0))


def draw_topbar(surface: pygame.Surface, left: str, center: str, right: str) -> None:
    pygame.draw.rect(surface, settings.BG_DEEP, (0, 0, settings.WIDTH, 56))
    pygame.draw.line(surface, settings.GRID, (0, 55), (settings.WIDTH, 55))
    draw_text(surface, left, 15, settings.MUTED, (24, 18), bold=True)
    draw_text(surface, center, 17, settings.TEXT, (settings.WIDTH // 2, 17), center=True)
    width = measure(right, 14)[0]
    draw_text(surface, right, 14, settings.MUTED,
              (settings.WIDTH - 24 - width, 19))


def draw_footer(surface: pygame.Surface, text: str,
                color: tuple[int, int, int] = settings.MUTED) -> None:
    draw_text(surface, text, 13, color, (24, settings.HEIGHT - 22))


class Button:
    def __init__(
        self,
        rect: pygame.Rect | tuple[int, int, int, int],
        label: str,
        callback: Callable[[], None] | None = None,
        *,
        size: int = 17,
        subtext: str = "",
        accent: tuple[int, int, int] = settings.BLUE,
        enabled: bool = True,
    ) -> None:
        self.rect = pygame.Rect(rect)
        self.label = label
        self.subtext = subtext
        self.callback = callback
        self.size = size
        self.accent = accent
        self.enabled = enabled
        self.hovered = False

    def set(self, *, label: str | None = None, subtext: str | None = None,
            enabled: bool | None = None, accent: tuple[int, int, int] | None = None) -> None:
        if label is not None:
            self.label = label
        if subtext is not None:
            self.subtext = subtext
        if enabled is not None:
            self.enabled = enabled
        if accent is not None:
            self.accent = accent

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                if self.enabled and self.callback is not None:
                    self.callback()
                    return True
        return False

    def draw(self, surface: pygame.Surface) -> None:
        if self.enabled:
            fill = settings.PANEL_2 if not self.hovered else lighten(settings.PANEL_2, 10)
            border = self.accent if self.hovered else darken(self.accent, 35)
            text_color = settings.TEXT if self.hovered else settings.WHITE
        else:
            fill = (20, 24, 30)
            border = (45, 52, 60)
            text_color = settings.MUTED
        pygame.draw.rect(surface, fill, self.rect, border_radius=8)
        pygame.draw.rect(surface, border, self.rect, width=1, border_radius=8)
        if self.enabled:
            pygame.draw.rect(
                surface,
                self.accent,
                pygame.Rect(self.rect.x, self.rect.y + 8, 3, self.rect.height - 16),
                border_radius=2,
            )
        if self.subtext:
            draw_text(
                surface,
                self.label,
                self.size,
                text_color,
                (self.rect.centerx, self.rect.y + 13),
                center=True,
            )
            draw_text(
                surface,
                self.subtext,
                12,
                settings.MUTED if self.enabled else (80, 86, 94),
                (self.rect.centerx, self.rect.y + 31),
                center=True,
            )
        else:
            draw_text(
                surface,
                self.label,
                self.size,
                text_color,
                self.rect.center,
                center=True,
            )


class Typewriter:
    def __init__(self, text: str, speed: float = 42.0) -> None:
        self.text = str(text)
        self.speed = speed
        self.visible = 0.0

    @property
    def done(self) -> bool:
        return self.visible >= len(self.text)

    def update(self, dt: float) -> None:
        if not self.done:
            self.visible = min(len(self.text), self.visible + self.speed * dt)

    def reveal_all(self) -> None:
        self.visible = float(len(self.text))

    def rendered(self) -> str:
        return self.text[: int(self.visible)]
