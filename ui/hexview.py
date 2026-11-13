"""六边形棋盘渲染与命中。"""

from __future__ import annotations

from dataclasses import dataclass, field

import pygame

import settings
from core import hex as hx
from ui.widgets import draw_text, get_font


@dataclass
class BoardSnapshot:
    cells: dict[hx.Cell, dict] = field(default_factory=dict)
    pieces: list[dict] = field(default_factory=list)
    enemies: list[dict] = field(default_factory=list)
    jurisdiction: set[hx.Cell] = field(default_factory=set)
    active_ports: set[int] = field(default_factory=set)


class HexView:
    def __init__(self, size: float | None = None, origin: tuple[float, float] | None = None) -> None:
        self.size = float(size if size is not None else settings.HEX_SIZE)
        self.origin = origin if origin is not None else settings.HEX_ORIGIN
        self.time = 0.0

    def update(self, dt: float) -> None:
        self.time += dt

    def cell_center(self, q: int, r: int) -> tuple[int, int]:
        x, y = hx.hex_to_pixel(q, r, self.size, self.origin)
        return int(x), int(y)

    def cell_rect(self, q: int, r: int) -> pygame.Rect:
        cx, cy = self.cell_center(q, r)
        x, y, w, h = hx.hex_rect((cx, cy), self.size)
        return pygame.Rect(int(x), int(y), max(1, int(w)), max(1, int(h)))

    def cell_at(self, logical_pos: tuple[float, float]) -> hx.Cell | None:
        cell = hx.pixel_to_hex((logical_pos[0], logical_pos[1]), self.size, self.origin)
        if cell not in hx.cells():
            return None
        # 检查是否真在六边形内（不是只靠近）
        cx, cy = self.cell_center(*cell)
        if (cx - logical_pos[0]) ** 2 + (cy - logical_pos[1]) ** 2 > (self.size * 1.16) ** 2:
            return None
        return cell

    def _poly(self, surface, cell, color, width=0):
        cx, cy = self.cell_center(*cell)
        points = [(int(x), int(y)) for x, y in hx.hex_corners((cx, cy), self.size * 0.97)]
        pygame.draw.polygon(surface, color, points, width)

    def draw(self, surface, snapshot: BoardSnapshot, *, hover=None,
             selected_cells=None, range_cells=None, path_cells=None,
             deployable_cells=None) -> None:
        selected_cells = set(selected_cells or [])
        range_cells = set(range_cells or [])
        path_cells = set(path_cells or [])
        deployable_cells = set(deployable_cells or [])

        # 棋盘底
        for cell in hx.cells():
            data = snapshot.cells.get(cell, {})
            cx, cy = self.cell_center(*cell)
            fill = settings.MEM_DARK
            if data.get("allocated"):
                fill = settings.MEM_COLOR
            if data.get("sector_type"):
                fill = settings.SECTOR_COLORS.get(str(data["sector_type"]), fill)
            if data.get("core"):
                fill = settings.CORE_COLOR
            if data.get("broken"):
                fill = (42, 42, 48)
            self._poly(surface, cell, fill)
            # 环3总线
            if hx.distance((0, 0), cell) == 3 and not data.get("allocated"):
                self._poly(surface, cell, settings.BUS_COLOR, 1)
            if cell in snapshot.jurisdiction and not data.get("broken"):
                overlay = pygame.Surface((int(self.size * 2), int(self.size * 2)), pygame.SRCALPHA)
                pygame.draw.polygon(
                    overlay, (37, 99, 235, 52),
                    [(int(x - cx + self.size), int(y - cy + self.size))
                     for x, y in hx.hex_corners((cx, cy), self.size * 0.96)]
                )
                surface.blit(overlay, (int(cx - self.size), int(cy - self.size)))
            if cell in deployable_cells:
                self._poly(surface, cell, (90, 150, 240), 2)
            if cell in range_cells:
                self._poly(surface, cell, (34, 197, 94), 2)
            if cell in path_cells:
                self._poly(surface, cell, (245, 158, 11), 2)
            if data.get("port") is not None:
                port = int(data["port"])
                active = port in snapshot.active_ports
                color = settings.RED if active else settings.MUTED
                draw_text(surface, f"P{port+1}", 9, color, (cx, cy - self.size - 8), center=True)
            if data.get("trap"):
                draw_text(surface, "!", 15, settings.RED, (cx + self.size - 7, cy - self.size + 2))
        # 辖区边框
        for cell in snapshot.jurisdiction:
            self._poly(surface, cell, (59, 130, 246), 1)

        # 棋子
        for piece in snapshot.pieces:
            color = tuple(piece.get("color", settings.AI_COLOR))
            cells = list(piece.get("cells", []))
            for cell in cells:
                self._poly(surface, cell, color)
                self._poly(surface, cell, settings.WHITE if piece.get("main_thread") else settings.BLUE, 2)
            if cells:
                cx = sum(self.cell_center(*c)[0] for c in cells) // len(cells)
                cy = sum(self.cell_center(*c)[1] for c in cells) // len(cells)
                name = str(piece.get("name", ""))[:6]
                draw_text(surface, name, 9, settings.WHITE, (cx, cy - 5), center=True, bold=True)
                progress = float(piece.get("progress", 1.0))
                pygame.draw.rect(surface, (8, 12, 18), (cx - 18, cy - 22, 36, 3))
                pygame.draw.rect(surface, settings.CYAN, (cx - 18, cy - 22, int(36 * max(0, min(1, progress))), 3))
                ratio = float(piece.get("hp_ratio", 1.0))
                pygame.draw.rect(surface, (10, 14, 20), (cx - 18, cy + 10, 36, 3))
                pygame.draw.rect(surface, settings.GREEN if ratio > 0.35 else settings.RED,
                                 (cx - 18, cy + 10, int(36 * max(0, min(1, ratio))), 3))
                if piece.get("main_thread"):
                    draw_text(surface, "主线程", 8, settings.AMBER, (cx, cy - 18), center=True)

        # 敌人
        for enemy in snapshot.enemies:
            cell = enemy.get("cell")
            if cell is None:
                continue
            cx, cy = self.cell_center(*cell)
            color = settings.ENEMY_AI_COLOR if enemy.get("ghost") else settings.ENEMY_COLOR
            pygame.draw.circle(surface, color, (cx, cy), int(self.size * 0.34))
            pygame.draw.circle(surface, settings.BLACK, (cx, cy), int(self.size * 0.34), 1)
            draw_text(surface, str(enemy.get("name", ""))[:5], 8, settings.WHITE, (cx, cy + 1), center=True)
            ratio = float(enemy.get("hp_ratio", 1.0))
            pygame.draw.rect(surface, (20, 10, 10), (cx - 17, cy + 16, 34, 3))
            pygame.draw.rect(surface, settings.RED, (cx - 17, cy + 16, int(34 * max(0, min(1, ratio))), 3))

        # 激活端口外圈
        for i in range(6):
            if i in snapshot.active_ports:
                cx, cy = self.cell_center(*hx.port_cell(i))
                pygame.draw.circle(surface, settings.RED, (cx, cy), int(self.size * 1.02), 2)
        if hover and hover in hx.cells():
            pulse = 0.55 + 0.45 * abs((self.time * 2.4) % 2.0 - 1.0)
            cx, cy = self.cell_center(*hover)
            glow = pygame.Surface((settings.WIDTH, settings.HEIGHT), pygame.SRCALPHA)
            pygame.draw.circle(glow, (120, 200, 255, int(45 * pulse)), (cx, cy), int(self.size * 1.1))
            surface.blit(glow, (0, 0))
            self._poly(surface, hover, settings.WHITE, 2)
