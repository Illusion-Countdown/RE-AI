"""六边形棋盘几何：37 格、6 扇区、6 端口、像素坐标。

轴向坐标 (q, r)，尖顶 pointy-top。
"""

from __future__ import annotations

import math
from collections import deque

Cell = tuple[int, int]
RADIUS = 3
SQRT3 = math.sqrt(3.0)
DIRECTIONS: list[Cell] = [(1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1)]


def cells(radius: int = RADIUS) -> list[Cell]:
    out: list[Cell] = []
    for q in range(-radius, radius + 1):
        for r in range(-radius, radius + 1):
            if abs(q + r) <= radius:
                out.append((q, r))
    out.sort(key=lambda c: (distance((0, 0), c), math.atan2(c[1], c[0])))
    return out


def ring(radius: int) -> list[Cell]:
    return [c for c in cells(RADIUS) if distance((0, 0), c) == radius]


def neighbors(cell: Cell) -> list[Cell]:
    q, r = cell
    return [(q + dq, r + dr) for dq, dr in DIRECTIONS]


def distance(a: Cell, b: Cell) -> int:
    dq = a[0] - b[0]
    dr = a[1] - b[1]
    return max(abs(dq), abs(dr), abs(dq + dr))


def direction_index(cell: Cell) -> int | None:
    if cell == (0, 0):
        return None
    angle = math.atan2(cell[1], cell[0])
    best = 0
    best_delta = 99.0
    for i, (dq, dr) in enumerate(DIRECTIONS):
        target = math.atan2(dr, dq)
        delta = abs(math.atan2(math.sin(angle - target), math.cos(angle - target)))
        if delta < best_delta:
            best_delta = delta
            best = i
    return best


def hex_to_pixel(q: int, r: int, size: float, origin: tuple[float, float] = (0.0, 0.0)) -> tuple[float, float]:
    x = size * SQRT3 * (q + r / 2.0) + origin[0]
    y = size * 1.5 * r + origin[1]
    return x, y


def pixel_to_hex(pos: tuple[float, float], size: float, origin: tuple[float, float] = (0.0, 0.0)) -> Cell:
    # 37 格很小，直接以像素中心最近者为准，保证 roundtrip 绝对一致
    best = (0, 0)
    best_dist = 1e30
    for cell in cells(RADIUS):
        px, py = hex_to_pixel(cell[0], cell[1], size, origin)
        d = (px - pos[0]) ** 2 + (py - pos[1]) ** 2
        if d < best_dist:
            best_dist = d
            best = cell
    return best


def hex_corners(center: tuple[float, float], size: float) -> list[tuple[float, float]]:
    pts = []
    for i in range(6):
        angle = math.radians(60 * i - 30)
        pts.append((center[0] + size * math.cos(angle), center[1] + size * math.sin(angle)))
    return pts


def hex_rect(center: tuple[float, float], size: float) -> tuple[float, float, float, float]:
    pts = hex_corners(center, size)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)


# ---------------------------------------------------------------------------
# 扇区 / 端口
# ---------------------------------------------------------------------------
_RING2 = ring(2)
_RING3 = ring(3)
_SECTOR_CENTERS: list[float] = []
for d in DIRECTIONS:
    _SECTOR_CENTERS.append(math.atan2(d[1], d[0]))


def _angle_delta(a: float, b: float) -> float:
    return abs(math.atan2(math.sin(a - b), math.cos(a - b)))


def _sector_from_cells() -> list[list[Cell]]:
    ordered = sorted(_RING2, key=lambda c: math.atan2(c[1], c[0]))
    return [ordered[i * 2:(i + 1) * 2] for i in range(6)]


_SECTORS = _sector_from_cells()
_SECTOR_CENTERS = [
    math.atan2(sum(c[1] for c in bucket) / 2.0, sum(c[0] for c in bucket) / 2.0)
    for bucket in _SECTORS
]


def sector_cells(index: int) -> list[Cell]:
    if 0 <= index < 6:
        return list(_SECTORS[index])
    return []


def sector_of(cell: Cell) -> int | None:
    for i, bucket in enumerate(_SECTORS):
        if cell in bucket:
            return i
    return None


def _port_cells() -> list[Cell]:
    result = []
    for i in range(6):
        target = _SECTOR_CENTERS[i]
        result.append(min(_RING3, key=lambda c: _angle_delta(math.atan2(c[1], c[0]), target)))
    return result


_PORTS = _port_cells()


def port_cell(index: int) -> Cell:
    return _PORTS[index % 6]


def port_index(cell: Cell) -> int | None:
    for i, port in enumerate(_PORTS):
        if cell == port:
            return i
    return None


def _shortest_path(start: Cell, target: Cell) -> list[Cell]:
    queue = deque([[start]])
    seen = {start}
    while queue:
        path = queue.popleft()
        end = path[-1]
        if end == target:
            return path
        for nxt in neighbors(end):
            if nxt not in cells(RADIUS) or nxt in seen:
                continue
            seen.add(nxt)
            queue.append(path + [nxt])
    return [start]


def port_path(index: int) -> list[Cell]:
    port = port_cell(index)
    path = _shortest_path(port, (0, 0))
    # 强制长度 4：端口 -> 环2 -> 环1 -> 核心
    if len(path) != 4:
        # BFS 最短不会发生；兜底沿距离递减重选
        cur = port
        out = [cur]
        while cur != (0, 0):
            candidates = [n for n in neighbors(cur) if n in cells(RADIUS) and distance(n, (0, 0)) < distance(cur, (0, 0))]
            if not candidates:
                break
            cur = candidates[0]
            out.append(cur)
        return out
    return path
