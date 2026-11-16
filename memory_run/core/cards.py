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
    """网格 + 寄存器 + 仓库（放不进网格的卡）。"""

    def __init__(self):
        self.grid = Grid(5, 5)
        self.cards = []
        self.vault = []
        self.register = []
        self.register_cap = 3
        self.rd_cap = 100
        self.reshuffle_penalty = 0

    # ------------------------------------------------------------ 起始
    def start(self):
        for key in ("CUT", "CUT", "LINK", "WEAK"):
            self.cards.append(Card(key))
        # 整齐地摆在左上角，给玩家一个干净的空网格
        spots = [(0, 0), (0, 2), (0, 4), (2, 0)]
        for card, (r, c) in zip(self.cards, spots):
            self.grid.place(card, r, c, 0)
        self.register = ["CUT", "LINK", "WEAK"]

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
        cap = self.rd_cap - self.reshuffle_penalty
        return max(0.0, min(float(cap), base))

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

    # ------------------------------------------------------------ 寄存器
    def can_register(self, key):
        return key in self.register or len(self.register) < self.register_cap

    def toggle_register(self, key):
        if key in self.register:
            if len(self.register) > 1:
                self.register.remove(key)
                return True
            return False
        if len(self.register) < self.register_cap and self.cards_of(key):
            self.register.append(key)
            return True
        return False

    # ------------------------------------------------------------ 升级
    def upgrade_cost(self, discount=0):
        return max(1, 3 - discount)

    def upgrade_pair(self, key, shards, discount=0):
        if shards < self.upgrade_cost(discount):
            return False, "碎片不足"
        cards = [c for c in self.cards if c.key == key and not c.up and c.anchor]
        if len(cards) < 2:
            return False, "需要两张在场上的同名基础卡"
        a, b = cards[0], cards[1]
        self.grid.remove(b)
        self.cards.remove(b)
        a.up = True
        return True, ""

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
        """整个卡组：网格里所有可用的卡，而不是寄存器里的 3 种。"""
        pile = []
        for card in self.cards:
            if card.anchor and not self.grid.card_corroded(card):
                pile.append(card)
        rng.shuffle(pile)
        return pile


class Hand:
    """5 执行槽 + 1 备用 + 2 溢出；一张卡一次使用。"""

    def __init__(self, reserve_max=1, overflow_max=2):
        self.slots = [None] * 5
        self.reserve = [None] * reserve_max
        self.overflow = [None] * overflow_max
        self.used = []
        self.discarded = []
        self.destroyed = []
        self.msg = ""

    def total(self):
        return (sum(1 for x in self.slots if x) +
                sum(1 for x in self.reserve if x) +
                sum(1 for x in self.overflow if x))

    def add(self, card):
        for i, c in enumerate(self.slots):
            if c is None:
                self.slots[i] = card
                self.msg = f"抽到 {card.name} → 槽 {i + 1}"
                return "slot"
        for i, c in enumerate(self.reserve):
            if c is None:
                self.reserve[i] = card
                self.msg = f"抽到 {card.name} → 备用"
                return "reserve"
        for i, c in enumerate(self.overflow):
            if c is None:
                self.overflow[i] = card
                self.msg = f"抽到 {card.name} → 溢出（下次抽牌销毁）"
                return "overflow"
        self.destroyed.append(card)
        self.msg = f"手牌溢出：{card.name} 被销毁"
        return "destroyed"

    def take_slot(self, i):
        card = self.slots[i]
        if card is None:
            return None
        self.slots[i] = None
        self.used.append(card)
        return card

    def take_reserve(self, i):
        card = self.reserve[i]
        if card is None:
            return None
        self.reserve[i] = None
        self.used.append(card)
        return card

    def take_overflow(self, i):
        card = self.overflow[i]
        if card is None:
            return None
        self.overflow[i] = None
        self.used.append(card)
        return card

    def free_slots(self):
        return sum(1 for c in self.slots if c is None)

    def refill(self):
        """使用后，备用/溢出按顺序补进空槽。"""
        for i, c in enumerate(self.slots):
            if c is not None:
                continue
            src = None
            for j, x in enumerate(self.reserve):
                if x is not None:
                    self.reserve[j] = None
                    src = x
                    break
            if src is None:
                for j, x in enumerate(self.overflow):
                    if x is not None:
                        self.overflow[j] = None
                        src = x
                        break
            if src is not None:
                self.slots[i] = src

    def clear_overflow(self):
        out = [c for c in self.overflow if c is not None]
        self.overflow = [None] * len(self.overflow)
        self.destroyed.extend(out)
        return out

    def discard_all(self):
        out = [c for c in self.slots + self.reserve + self.overflow if c]
        self.slots = [None] * 5
        self.reserve = [None] * len(self.reserve)
        self.overflow = [None] * len(self.overflow)
        self.discarded.extend(out)
        return out

    def find_card(self, card):
        for i, c in enumerate(self.slots):
            if c is card:
                return ("slot", i)
        for i, c in enumerate(self.reserve):
            if c is card:
                return ("reserve", i)
        for i, c in enumerate(self.overflow):
            if c is card:
                return ("overflow", i)
        return None


def draw_three(hand, pile, used, rng):
    n = 0
    for _ in range(3):
        if not pile:
            break
        hand.add(pile.pop())
        n += 1
    return n
