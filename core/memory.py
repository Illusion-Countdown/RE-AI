# -*- coding: utf-8 -*-
"""内存块：5×5 的格子，算法卡放进去才存在。

三条规则：
  1. 必须连续放置（横扫或竖扫）
  2. 被敌人打碎的格子永久不可用
  3. 压在被碎格子上的卡 → 禁用，移出牌库
"""
from dataclasses import dataclass, field

BROKEN = "BROKEN"


@dataclass
class Memory:
    w: int = 5
    h: int = 5
    grid: list = field(default_factory=list)      # grid[y][x] = None | card_id | BROKEN
    placed: dict = field(default_factory=dict)    # card_id -> (x, y, w, h)
    disabled: set = field(default_factory=set)    # 卡被禁用

    def __post_init__(self):
        if not self.grid:
            self.grid = [[None] * self.w for _ in range(self.h)]

    # ---------------- 查询 ----------------

    def free_cells(self) -> list:
        return [(x, y) for y in range(self.h) for x in range(self.w)
                if self.grid[y][x] is None]

    def is_broken(self, x, y) -> bool:
        return self.grid[y][x] == BROKEN

    def has_card(self, card_id) -> bool:
        return card_id in self.placed and card_id not in self.disabled

    def active_cards(self) -> list:
        return [c for c in self.placed if c not in self.disabled]

    # ---------------- 放置 ----------------

    def fits(self, w, h, x, y) -> bool:
        if x < 0 or y < 0 or x + w > self.w or y + h > self.h:
            return False
        for dy in range(h):
            for dx in range(w):
                if self.grid[y + dy][x + dx] is not None:
                    return False
        return True

    def find_spot(self, w, h):
        """first-fit：从上到下、从左到右找第一个能放下的位置。"""
        for y in range(self.h):
            for x in range(self.w):
                if self.fits(w, h, x, y):
                    return x, y
        return None

    def place(self, card_id, w, h) -> bool:
        # 同一张卡不能放两次：否则 placed 被覆盖，格子会重复计账
        if card_id in self.placed:
            return False

        spot = self.find_spot(w, h)
        if spot is None:
            return False
        x, y = spot
        for dy in range(h):
            for dx in range(w):
                self.grid[y + dy][x + dx] = card_id
        self.placed[card_id] = (x, y, w, h)
        self.disabled.discard(card_id)
        return True

    def remove(self, card_id):
        if card_id not in self.placed:
            return
        x, y, w, h = self.placed.pop(card_id)
        for dy in range(h):
            for dx in range(w):
                if self.grid[y + dy][x + dx] == card_id:
                    self.grid[y + dy][x + dx] = None
        self.disabled.discard(card_id)

    # ---------------- 扩容 & 损坏 ----------------

    def expand(self, cells: int = 5):
        """扩容：加一行（5 格）。"""
        rows = max(1, cells // self.w)
        for _ in range(rows):
            self.grid.append([None] * self.w)
        self.h = len(self.grid)

    def smash(self, prefer_card: bool = True) -> str:
        """打碎一格。优先打有卡的格子（敌人就是冲着你的构筑来的）。

        返回被禁用的卡 id（没有则返回空串）。
        """
        candidates = []
        for y in range(self.h):
            for x in range(self.w):
                v = self.grid[y][x]
                if v is None or v == BROKEN:
                    continue
                if prefer_card and v != BROKEN:
                    candidates.append((x, y, v))
                else:
                    candidates.append((x, y, v))

        if not candidates:
            return ""

        # 优先有卡的
        with_card = [c for c in candidates if c[2] != BROKEN]
        pool = with_card or candidates
        x, y, v = pool[len(pool) // 2]      # 取中间的，位置稳定好演示

        self.grid[y][x] = BROKEN
        if v != BROKEN and v in self.placed and v not in self.disabled:
            self.disabled.add(v)
            return v
        return ""

    def repair(self, n: int = 1) -> int:
        """修复 n 格。返回实际修复数。"""
        fixed = 0
        for y in range(self.h):
            for x in range(self.w):
                if self.grid[y][x] == BROKEN and fixed < n:
                    self.grid[y][x] = None
                    fixed += 1
        return fixed

    def stats(self) -> dict:
        total = self.w * self.h
        broken = sum(1 for y in range(self.h) for x in range(self.w)
                     if self.grid[y][x] == BROKEN)
        used = sum(1 for y in range(self.h) for x in range(self.w)
                   if self.grid[y][x] not in (None, BROKEN))
        return {
            "total": total,
            "broken": broken,
            "used": used,
            "free": total - broken - used,
            "disabled": len(self.disabled),
        }
