# -*- coding: utf-8 -*-
"""一局远征的持久状态：牌组、生命、碎片、模块、Boss 规则与关卡进度。"""
import random

from memory_run.core.cards import Deck, CARD_DEFS
from memory_run.content import (
    ROOMS, TUTORIALS, TUTORIAL_COUNT, room_for_step, CARD_POOL_ZONE,
    MODULE_POOL, MODULES, MODULE_BY_ID, BOSS_RULES, RUN_ROOMS, ZONE_NAMES,
    BODIES, BODY_BY_ID,
)
from memory_run.const import clamp

MAX_HP = 100
REF_START = 3
EXPANSIONS = [(5, 5), (6, 6), (6, 7), (7, 7), (7, 7), (7, 7)]


class RunState:
    def __init__(self, tutorial=False, seed=None, body_id="tree"):
        self.tutorial = tutorial
        self.seed = seed if seed is not None else random.randrange(1, 10 ** 8)
        self.rng = random.Random(self.seed)
        self.body = BODY_BY_ID.get(body_id, BODIES[2])
        self.body_id = self.body["id"]
        self.deck = Deck()
        self.deck.start()
        # Deck.start 已放 2 CUT / 1 LINK / 1 WEAK；共 7 格占用，留 18 格。
        self.hp = self.body["hp"]
        self.max_hp = self.body["hp"]
        self.refs = REF_START
        self.shards = 0
        self.score = 0
        self.step = 0 if tutorial else TUTORIAL_COUNT
        self.modules = []
        self.rules = []
        self.bosses_cleared = 0
        self.rooms_cleared = 0
        self.perfects = 0
        self.grid_bonus = 0
        self.rd_choice = 0             # 0 高保真 / 1 平衡 / 2 低码率
        self.deck.rd_cap = (100, 75, 50)[self.rd_choice]
        self.stats = {
            "gc": 0, "cuts": 0, "links": 0, "dmg": 0, "kills": 0,
            "cards": 0, "perfects": 0, "time": 0.0, "rooms": 0,
            "necro": 0, "score": 0,
        }
        self.last_room = None
        self.log = []
        self.ended = False
        self.victory = False
        self.tutorial_done = False

    # ------------------------------------------------------------ 查询
    @property
    def room(self):
        return room_for_step(self.step)

    @property
    def zone(self):
        r = self.room
        return r["zone"] if r else 3

    @property
    def zone_name(self):
        return ZONE_NAMES.get(self.zone, ("未知", "UNKNOWN"))[0]

    def has(self, mid):
        return any(m["id"] == mid for m in self.modules)

    def has_rule(self, rid):
        return any(r["id"] == rid for r in self.rules)

    def add_module(self, mid):
        m = MODULE_BY_ID.get(mid)
        if m and not self.has(mid):
            self.modules.append(m)
            return True
        return False

    def add_rule(self, rid):
        for r in BOSS_RULES:
            if r["id"] == rid and not self.has_rule(rid):
                self.rules.append(r)
                if rid == "grid":
                    self.grid_bonus += 1
                    self._expand(1, 1)
                return True
        return False

    # ------------------------------------------------------------ 房间生命周期
    def begin_room(self):
        self.deck.rd_cap = (100, 75, 50)[self.rd_choice]
        self.room_dead_snapshot = set(self.deck.grid.dead)
        self.last_room = {
            "damage": 0.0, "min_quality": 100.0, "new_dead": 0,
            "start_dead": len(self.deck.grid.dead), "cleared": False,
            "perfect": False, "reward": None, "time": 0.0,
        }

    def note_damage(self):
        if self.last_room:
            self.last_room["damage"] += 1

    def note_quality(self, q):
        if self.last_room:
            self.last_room["min_quality"] = min(self.last_room["min_quality"], q)

    def restore_room_snapshot(self):
        """REF 回滚：把本房新增的坏死格退回进房时的状态。"""
        snap = getattr(self, "room_dead_snapshot", None)
        if snap is not None:
            self.deck.grid.dead = set(snap)
        self.deck.rd_cap = (100, 75, 50)[self.rd_choice]

    def complete_room(self, cleared, quality, damage, new_dead, time_used):
        """返回结算字典；调用方据此决定奖励界面。"""
        r = self.last_room or {}
        self.rooms_cleared += int(cleared)
        self.stats["rooms"] += int(cleared)
        self.stats["time"] += time_used
        self.room_clear_score = 0
        if not cleared:
            return {"cleared": False, "perfect": False, "score": 0, "shards": 0}
        base = 120 + 40 * self.bosses_cleared + int(time_used) * 2
        if self.room.get("boss"):
            base += 400
        self.score += base
        self.stats["score"] = self.score
        got_shards = 3 if self.room.get("boss") else 1
        self.shards += got_shards
        perfect = (damage <= 0 and quality >= 75.0 and new_dead <= 0)
        if perfect:
            self.perfects += 1
            self.stats["perfects"] += 1
            bonus = 2 * (2 if self.has_rule("perfect") else 1)
            self.shards += bonus
            got_shards += bonus
            self.score += 150
        r.update({"cleared": True, "perfect": perfect, "score": base,
                  "quality": quality, "damage": damage,
                  "new_dead": new_dead, "time": time_used,
                  "shards": got_shards})
        self.last_room = r
        return r

    def advance(self):
        """推进到下一关；Boss 后做扩容。返回是否还有房间。"""
        room = self.room
        if room and room.get("boss"):
            self.bosses_cleared += 1
            self._expand_after_boss()
        self.step += 1
        if self.tutorial and self.step >= TUTORIAL_COUNT:
            self.tutorial_done = True
        return self.room is not None

    def _expand_after_boss(self):
        idx = min(len(EXPANSIONS) - 1, self.bosses_cleared)
        base_w, base_h = EXPANSIONS[idx]
        # 网格规则是持久的额外 +1；Boss 扩容不能把已有的更大网格缩回去。
        w = max(self.deck.grid.w, min(7, base_w + self.grid_bonus))
        h = max(self.deck.grid.h, min(7, base_h + self.grid_bonus))
        self._expand_to(w, h)

    def _expand(self, dw, dh):
        g = self.deck.grid
        self._expand_to(min(7, g.w + dw), min(7, g.h + dh))
        for card in list(self.deck.vault):
            if self.deck.grid.auto_place(card):
                self.deck.vault.remove(card)

    def _expand_to(self, w, h):
        g = self.deck.grid
        old = set(self.deck.grid.dead)
        g.resize(w, h)
        g.dead = {c for c in old if c[0] < h and c[1] < w}
        # 已放置的卡如果因为缩小越界，收回仓库
        for card in list(self.deck.cards):
            if card.anchor:
                r, c = card.anchor
                cw, ch = card.shape
                if r + ch > h or c + cw > w:
                    self.deck.grid.remove(card)
                    if card not in self.deck.vault:
                        self.deck.vault.append(card)
        for card in list(self.deck.vault):
            if self.deck.grid.auto_place(card):
                self.deck.vault.remove(card)

    # ------------------------------------------------------------ 画质
    def set_rd(self, idx):
        self.rd_choice = clamp(int(idx), 0, 2)
        self.deck.rd_cap = (100, 75, 50)[self.rd_choice]

    def quality(self, work_used=0.0):
        q = self.deck.quality(work_used)
        if self.has("redundancy") and q < 25 and not self._redundancy_used_room():
            q = 50.0
        return q

    def _redundancy_used_room(self):
        return (self.last_room or {}).get("redundancy_used", False)

    def mark_redundancy(self):
        if self.last_room is not None:
            self.last_room["redundancy_used"] = True

    # ------------------------------------------------------------ 坏死格
    def add_dead_cells(self, n, near=None):
        """随机把 n 个空闲格变成坏死格；返回新增数量。"""
        free = self.deck.grid.free_cells()
        if not free:
            return 0
        self.rng.shuffle(free)
        if near:
            free.sort(key=lambda rc: abs(rc[0] - near[0]) + abs(rc[1] - near[1]))
        added = 0
        for cell in free[:n]:
            self.deck.grid.dead.add(cell)
            added += 1
        if added and self.last_room:
            self.last_room["new_dead"] += added
        self.stats["necro"] += added
        return added

    def repair_dead(self, n=1, cost_per=2):
        if not self.deck.grid.dead:
            return 0
        cost = n * cost_per
        if self.shards < cost:
            return 0
        removed = 0
        for cell in list(self.deck.grid.dead)[:n]:
            self.deck.grid.dead.discard(cell)
            removed += 1
        self.shards -= removed * cost_per
        # 修好格子后，仓库里放不下的卡可以尝试放回
        for card in list(self.deck.vault):
            if self.deck.grid.auto_place(card):
                self.deck.vault.remove(card)
        return removed

    # ------------------------------------------------------------ 奖励
    def card_pool(self):
        pool = list(CARD_POOL_ZONE.get(max(1, self.zone), CARD_POOL_ZONE[3]))
        # 智能掉落：已拥有的卡权重更高；寄存器不再限制抽牌
        weights = []
        for key in pool:
            if self.deck.cards_of(key):
                weights.append(55)
            else:
                weights.append(20)
        return pool, weights

    def make_card_rewards(self, count=3, rare=False):
        pool, weights = self.card_pool()
        if rare:
            pairs = [(k, w) for k, w in zip(pool, weights)
                     if CARD_DEFS[k]["rarity"] >= 1]
            if pairs:
                pool = [k for k, _w in pairs]
                weights = [w for _k, w in pairs]
        out = []
        guard = 0
        while len(out) < count and guard < 80:
            guard += 1
            key = self.rng.choices(pool, weights=weights, k=1)[0]
            if key not in out:
                out.append(key)
        while len(out) < count:
            out.append(self.rng.choice(pool))
        return out

    def add_card(self, key):
        card = self.deck.add(key)
        self.stats["cards"] += 1
        return card

    def make_shop_items(self):
        """商店：卡牌与规则增幅，碎片是唯一货币。"""
        pool, _weights = self.card_pool()
        self.rng.shuffle(pool)
        items = []
        for key in pool[:3]:
            price = 2 + CARD_DEFS[key]["rarity"] * 2
            items.append({"kind": "card", "key": key, "price": price})
        mods = [m for m in MODULE_POOL if not self.has(m)]
        self.rng.shuffle(mods)
        for mid in mods[:2]:
            items.append({"kind": "module", "id": mid, "price": 5})
        return items

    def buy_shop_item(self, item):
        if not item or self.shards < item["price"]:
            return False, "碎片不足"
        if item["kind"] == "card":
            card = self.add_card(item["key"])
            self.shards -= item["price"]
            return True, f"{CARD_DEFS[item['key']]['cn']} 已入库"
        if item["kind"] == "module":
            if self.has(item["id"]):
                return False, "已经拥有这个增幅"
            if not self.add_module(item["id"]):
                return False, "无效增幅"
            self.shards -= item["price"]
            return True, "增幅已安装"
        return False, "未知商品"

    def card_sell_price(self, card):
        base = 2 + int(CARD_DEFS[card.key].get("rarity", 0)) * 2
        if card.up:
            base += 3
        return base

    def sell_card(self, card):
        """整备界面拖到 SELL：把不要的卡换成碎片。"""
        if card is None or card not in self.deck.cards:
            return 0
        price = self.card_sell_price(card)
        self.deck.grid.remove(card)
        if card in self.deck.cards:
            self.deck.cards.remove(card)
        if card in self.deck.vault:
            self.deck.vault.remove(card)
        self.shards += price
        return price

    def make_module_rewards(self, count=3):
        """只返回尚未拥有的模块；后期池不足时允许少于 3 个。"""
        pool = [m for m in MODULE_POOL if not self.has(m)]
        self.rng.shuffle(pool)
        return pool[:count]

    def make_rule_rewards(self):
        pool = [r["id"] for r in BOSS_RULES if not self.has_rule(r["id"])]
        self.rng.shuffle(pool)
        return pool[:3]

    def tutorial_line(self):
        r = self.room
        if not r:
            return ""
        if r.get("tut") == "cut":
            return "先剪 SCOPE→SENTINEL。别打血条，让它失去引用。"
        if r.get("tut") == "weak":
            return "强引用环剪不断。用 WEAK 换掉一条边，再剪另一条。"
        if r.get("tut") == "link":
            return "把 BRUTE 链到自己身上，它就会停火并替你承伤。"
        if r.get("tut") == "cast":
            return "红色虚线是析构器。先 CAST 剥掉，再剪，别让它炸你。"
        return ""

    def summary(self):
        return {
            "score": self.score, "rooms": self.rooms_cleared,
            "perfects": self.perfects, "modules": len(self.modules),
            "shards": self.shards, "gc": self.stats["gc"],
            "cuts": self.stats["cuts"], "time": self.stats["time"],
        }
