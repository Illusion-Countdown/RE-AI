# -*- coding: utf-8 -*-
"""卡牌、网格装箱、BENCH、手牌与画质公式。

一张卡是一个实体：形状、占用格数、一次使用。网格里所有卡就是你的内存。
"""
import math
import random

from memory_run.const import (
    CYAN, MAGENTA, PURPLE, AMBER, GREEN, RED, GOLD, TEAL, BLUE, WHITE, DIM,
    clamp,
)

# ---------------------------------------------------------------- 卡牌定义
from memory_run.content.card_defs import CARD_DEFS, SHAPE_NAMES, RARITY_CN



class Card:
    """网格里的一张实体卡。"""

    _uid = [0]

    def __init__(self, key, up=False):
        Card._uid[0] += 1
        self.uid = Card._uid[0]
        self.key = key
        self.up = up
        self.anchor = None          # (row, col)
        self.rot = 0                # 0/1，1 = 旋转 90°

    @property
    def d(self):
        return CARD_DEFS[self.key]

    @property
    def name(self):
        return self.d["cn"] + ("++" if self.up else "")

    @property
    def shape(self):
        w, h = self.d["shape"]
        return (h, w) if self.rot else (w, h)

    @property
    def color(self):
        return self.d["color"]

    def cells(self, row=None, col=None):
        r = self.anchor[0] if row is None else row
        c = self.anchor[1] if col is None else col
        w, h = self.shape
        return [(r + y, c + x) for y in range(h) for x in range(w)]

    def __repr__(self):
        return f"<Card {self.key}{'++' if self.up else ''}#{self.uid}>"


class Grid:
    """5×5 起步的内存网格，坏死格永久占位。"""

    def __init__(self, w=5, h=5):
        self.w = w
        self.h = h
        self.dead = set()          # (row, col)
        self.owner = {}            # (row, col) -> Card

    def resize(self, w, h):
        self.w, self.h = w, h
        self.dead = {(r, c) for (r, c) in self.dead if r < h and c < w}

    def can_place(self, card, r, c, rot):
        card.rot = rot
        w, h = card.shape
        if r < 0 or c < 0 or r + h > self.h or c + w > self.w:
            return False
        for rr in range(r, r + h):
            for cc in range(c, c + w):
                if (rr, cc) in self.dead:
                    return False
                if (rr, cc) in self.owner:
                    return False
        return True

    def place(self, card, r, c, rot=0):
        if not self.can_place(card, r, c, rot):
            return False
        for cell in card.cells(r, c):
            self.owner[cell] = card
        card.anchor = (r, c)
        card.rot = rot
        return True

    def remove(self, card):
        if not card.anchor:
            return
        for cell in list(card.cells()):
            if self.owner.get(cell) is card:
                del self.owner[cell]
        card.anchor = None

    def at(self, r, c):
        return self.owner.get((r, c))

    def auto_place(self, card):
        for rot in (0, 1):
            for r in range(self.h):
                for c in range(self.w):
                    if self.can_place(card, r, c, rot):
                        return self.place(card, r, c, rot)
        return False

    def free_cells(self):
        return [(r, c) for r in range(self.h) for c in range(self.w)
                if (r, c) not in self.owner and (r, c) not in self.dead]

    def free_count(self):
        return self.w * self.h - len(self.owner) - len(self.dead)

    def card_corroded(self, card):
        return any(cell in self.dead for cell in card.cells())

    def all_cards(self):
        seen = []
        for card in self.owner.values():
            if card not in seen:
                seen.append(card)
        return seen

    def card_at_pixel(self, mx, my, rect):
        """把屏幕像素转成网格坐标（给整备界面用）。"""
        if not rect.collidepoint(mx, my):
            return None
        c = int((mx - rect.x) / (rect.w / self.w))
        r = int((my - rect.y) / (rect.h / self.h))
        if 0 <= r < self.h and 0 <= c < self.w:
            return (r, c)
        return None


class Deck:
    """网格 + 仓库（放不进网格的卡）。"""

    def __init__(self):
        self.grid = Grid(5, 5)
        self.cards = []
        self.vault = []
        self.rd_cap = 100

    # ------------------------------------------------------------ 起始
    def start(self):
        for key in ("CUT", "CUT", "LINK", "WEAK"):
            self.cards.append(Card(key))
        # 整齐地摆在左上角，给玩家一个干净的空网格
        spots = [(0, 0), (0, 2), (0, 4), (2, 0)]
        for card, (r, c) in zip(self.cards, spots):
            self.grid.place(card, r, c, 0)

    def add(self, key, up=False, auto=True):
        card = Card(key, up)
        self.cards.append(card)
        if auto and not self.grid.auto_place(card):
            self.vault.append(card)
        return card

    def remove_card(self, card):
        self.grid.remove(card)
        if card in self.cards:
            self.cards.remove(card)
        if card in self.vault:
            self.vault.remove(card)

    # ------------------------------------------------------------ 查询
    def cards_of(self, key):
        return [c for c in self.cards if c.key == key]

    def placed_of(self, key):
        return [c for c in self.cards if c.key == key and c.anchor]

    def damaged_cards(self):
        return [c for c in self.cards if c.anchor and self.grid.card_corroded(c)]

    def type_counts(self):
        d = {}
        for c in self.cards:
            d[c.key] = d.get(c.key, 0) + 1
        return d

    def quality(self, work_used=0.0):
        total = self.grid.w * self.grid.h
        occupied = len(self.grid.owner)
        dead = len(self.grid.dead)
        load = occupied + dead
        free = max(1, total - load)
        base = 100 - 50.0 * load / max(1, total) - 50.0 * work_used / free
        return max(0.0, min(float(self.rd_cap), base))

    def quality_band(self, q=None):
        q = self.quality() if q is None else q
        if q >= 75:
            return 0
        if q >= 50:
            return 1
        if q >= 25:
            return 2
        return 3

    def quality_bonus(self, q=None):
        q = self.quality() if q is None else q
        return (0.0, 0.08, 0.18, 0.30)[self.quality_band(q)]

    def upgrade_cards(self, a, b):
        """拖动同名基础卡互相覆盖 = 免费升级，不消耗碎片。"""
        if a is None or b is None or a is b:
            return False
        if a.key != b.key or a.up or b.up:
            return False
        if not (a.anchor and b.anchor):
            return False
        self.grid.remove(b)
        if b in self.cards:
            self.cards.remove(b)
        a.up = True
        return True

    # ------------------------------------------------------------ 战斗牌堆
    def room_pile(self, rng):
        """整个卡组：网格里所有可用的卡。"""
        pile = []
        for card in self.cards:
            if card.anchor and not self.grid.card_corroded(card):
                pile.append(card)
        rng.shuffle(pile)
        return pile


class Hand:
    """3 张手牌；没有备用槽，也没有溢出槽。"""

    LIMIT = 3

    def __init__(self):
        self.slots = [None] * self.LIMIT
        self.msg = ""

    def total(self):
        return sum(1 for x in self.slots if x)

    def add(self, card):
        for i, c in enumerate(self.slots):
            if c is None:
                self.slots[i] = card
                self.msg = f"抽到 {card.name} → 槽 {i + 1}"
                return i
        self.msg = f"手牌已满：{card.name} 留在牌堆"
        return None

    def take_slot(self, i):
        card = self.slots[i]
        if card is None:
            return None
        self.slots[i] = None
        return card

    def free_slots(self):
        return sum(1 for c in self.slots if c is None)

    def discard_all(self):
        out = [c for c in self.slots if c]
        self.slots = [None] * self.LIMIT
        return out

    def find_card(self, card):
        for i, c in enumerate(self.slots):
            if c is card:
                return ("slot", i)
        return None
