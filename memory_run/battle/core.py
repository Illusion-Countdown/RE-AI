# -*- coding: utf-8 -*-
from .deps import *
from .input import InputMixin
from .actions import ActionsMixin
from .gc import GcMixin
from .player import PlayerMixin
from .enemies import EnemiesMixin


class Battle(InputMixin, ActionsMixin, GcMixin, PlayerMixin, EnemiesMixin):
    def __init__(self, run, fx):
        self.run = run
        self.fx = fx
        self.room = run.room
        self.graph = Graph()
        self.time = 0.0
        self.state = "intro"
        self.intro_t = 2.0
        self.end_t = 0.0
        self.ending = None
        self.result = None
        self.finished = False
        self.aim = None
        self.drag_active = False
        self.mouse = (W // 2, H // 2)
        self.hover_node = None
        self.hover_edge = None
        self.edge_drag = None
        self.two_drag = None
        self.slash = []
        self.projectiles = []
        self.pending_cuts = []
        self.pending_explosions = []
        self.aliases = []
        self.hand = Hand(reserve_max=1, overflow_max=2)
        self.pile = []
        self.used = []
        self.discarded = []
        self.destroyed = []
        self.reshuffled = False
        self.draw_timer = max(1.2, 2.4 - self.run.draw_bonus)
        self.redraw_used = False
        self.work_used = 0.0
        self.work_regen = self.run.body.get("regen", 1.7)
        self.quality_penalty = 0.0
        self.quality_drain = 0.0
        self.crash_t = 0.0
        self.redundancy_t = 0.0
        self.compress_t = 0.0
        self.slow_t = 0.0
        self.erase_streak = 0
        self.streak_t = 0.0
        self.cascade_marks = set()
        self.extra_gc = False
        self.gc_dirty = False
        self._resolving = False
        self.free_gc_used = False
        self.necro_bomb_used = False
        self.dead_code_used = False
        self.exception_used = False
        self.write_cd = 0.0
        self.hp = run.hp
        self.max_hp = run.max_hp
        self.speed = run.body.get("speed", 268)
        self.iframe = 0.0
        self.dash_cd = 0.0
        self.dash_t = 0.0
        self.focus = 3.2
        self.focus_max = 3.2
        self.plan = False
        self.hurt_flash = 0.0
        self.spawn_flash = 1.0
        self.alias_pool = None
        self.banner = self.room.get("intro", "")
        self.banner_t = 2.6
        self.toast_msg = self.room.get("hint", "")
        self.toast_t = 999.0 if self.room.get("tutorial") else 5.0
        self.phase_text = ""
        self.stats = {"dmg": 0.0, "cuts": 0, "gc": 0, "cards": 0, "links": 0}
        self.start_damage = (run.last_room or {}).get("damage", 0.0)
        self.start_dead = len(run.deck.grid.dead)
        self.wave_t = 6.0
        self.wave_left = 0
        self.build_room()
        self.shuffle_room()

    # ================================================================ 构建

    def build_room(self):
        g = self.graph
        specs = self.room["nodes"]
        by_id = {}
        for spec in specs:
            kind = spec["kind"]
            n = Node(kind, 0, 0, spec.get("name") or kind)
            hp = spec.get("hp")
            n.hp = n.max_hp = float(hp if hp is not None else
                                     DEFAULT_HP.get(kind, 40))
            n.data.update({k: v for k, v in spec.items()
                           if k not in ("id", "kind", "p", "name", "hp")})
            if kind == "ROOT":
                n.immortal = True
                n.collectible = False
                n.hostile = False
                n.targetable = False
                n.r = 15
            elif kind == "BOMB":
                n.r = 22
                n.data["destructor"] = True
            elif kind in ("GC_CORE", "AUDITOR", "KERNEL"):
                n.r = 40
                n.data["boss"] = n.data.get("boss", kind.lower())
                n.collectible = False
                n.immortal = True
            elif kind == "PYLON":
                n.r = 24
            elif kind == "CRAWLER":
                n.r = 26
                n.data["necro"] = True
            elif kind == "ERASER":
                n.r = 32
            else:
                n.r = 24 if n.max_hp < 100 else 28
            n.x = PLAY.x + spec["p"][0] * PLAY.w
            n.y = PLAY.y + spec["p"][1] * PLAY.h
            n.spawn_t = 0.0
            n.timers["atk"] = self.run.rng.uniform(1.8, 3.0)
            n.timers["special"] = self.run.rng.uniform(2.0, 5.0)
            n.timers["phase"] = 0.0
            n.data["barrier_used"] = False
            n.born_anim = 0.45
            by_id[spec["id"]] = n
            g.add_node(n)
        # 玩家是一个真实节点（LINK 的起点、WRITE 的源）
        self.player_node = Node("PLAYER", PLAY.centerx, PLAY.bottom - 120,
                                "SELF", hp=self.hp, r=PLAYER_R)
        self.player_node.immortal = True
        self.player_node.collectible = False
        self.player_node.hostile = False
        self.player_node.targetable = True
        g.add_node(self.player_node)
        g.player = self.player_node
        # 边：允许重复，R04 的“两把锁”需要两条根引用
        for a, b, kind in self.room["edges"]:
            if a in by_id and b in by_id:
                g.add_edge(by_id[a], by_id[b], kind, unique=False)
        self.add_reinforcements(by_id)
        g.time = 0.0
        self.by_id = by_id
        self.root = by_id.get("scope")

    def shuffle_room(self):
        self.pile = self.run.deck.room_pile(self.run.rng)
        self.hand = Hand(reserve_max=1, overflow_max=2)
        tut = self.room.get("tut")
        if tut:
            # 教程不靠抽牌运气：把这一课需要的卡直接塞进起手
            need = {
                "cut": ["CUT"],
                "weak": ["WEAK", "CUT", "CUT"],
                "link": ["LINK", "CUT", "CUT"],
                "cast": ["TRUNC", "CUT"],
            }.get(tut, ["CUT"])
            have = {c.key for c in self.pile}
            for key in need:
                # 直接造一张临时卡；它不属于牌组，用完即消失
                card = Card(key)
                self.hand.add(card)
                have.add(key)
            for _ in range(3 - len(need)):
                if self.pile:
                    self.hand.add(self.pile.pop())
        else:
            for _ in range(3):
                self.draw_one(initial=True)
        self.fx.add_text(self.player_node.x, self.player_node.y - 40,
                         "DECK ONLINE", CYAN, 18, 1.2)

    # ================================================================ 查询

    @property
    def deck(self):
        return self.run.deck

    def node_at(self, x, y, pad=8):
        return self.graph.pick_at(x, y, pad)

    def edge_at(self, x, y, tol=13):
        return self.graph.edge_at(x, y, tol)

    def quality(self):
        q = self.run.quality(self.work_used) - self.quality_drain - self.quality_penalty
        if getattr(self, "redundancy_t", 0) > 0:
            q = max(q, 50.0)
        return clamp(q, 0.0, 100.0)

    def quality_band(self):
        q = self.quality()
        return 0 if q >= 75 else (1 if q >= 50 else (2 if q >= 25 else 3))

    def damage_mult(self):
        q = self.quality()
        m = 1.0 + self.deck.quality_bonus(q)
        if self.compress_t > 0:
            m += 0.30
        if self.run.has("overload") and q < 50:
            m += 0.15
        per = 0.02 if self.run.has("cascade_bonus") else 0.01
        m += min(0.10, self.erase_streak * per)
        return min(2.0, m)

    def toast(self, msg, t=2.4):
        self.toast_msg = msg
        self.toast_t = t

    def nope(self, msg):
        self.toast(msg)
        self.fx.add_text(self.player_node.x, self.player_node.y - 34,
                         msg, AMBER, 15, 0.8)

    # ================================================================ 抽牌

    def reshuffle(self):
        if not self.used:
            return False
        self.pile = list(self.used)
        self.used = []
        self.run.rng.shuffle(self.pile)
        self.reshuffled = True
        self.deck.reshuffle_penalty = min(42, self.deck.reshuffle_penalty + 6)
        self.toast("牌堆洗回｜本房画质上限 -6%（可重复，代价递增）")
        self.fx.add_glitch(0.22)
        return True

    def draw_one(self, initial=False):
        if not self.pile and not self.reshuffle():
            return None
        # 坏死格上的卡不能抽出来
        while self.pile and self.pile[-1].anchor and \
                self.deck.grid.card_corroded(self.pile[-1]):
            self.used.append(self.pile.pop())
        if not self.pile:
            return None
        if not initial:
            self.hand.clear_overflow()
        card = self.pile.pop()
        where = self.hand.add(card)
        if where != "destroyed":
            self.fx.add_text(self.player_node.x, self.player_node.y - 54,
                             f"{card.name}", card.color, 14, 0.8)
        return card

    # ================================================================ 输入

    def update(self, dt, inp):
        self.mouse = inp.get("mouse", self.mouse)
        if self.state == "intro":
            self.intro_t -= dt
            if self.intro_t <= 0:
                self.state = "playing"
            return
        if self.state == "clear":
            self.end_t -= dt
            if self.end_t <= 0 and not self.finished:
                self.finalize(True)
            return
        if self.state == "dead":
            self.end_t -= dt
            if self.end_t <= 0 and not self.finished:
                self.finalize(False)
            return
        if self.state != "playing":
            return
        if self.fx.hitstop > 0:
            self.fx.hitstop = max(0.0, self.fx.hitstop - dt)
            return

        self.plan = bool(inp.get("plan")) and self.focus > 0
        if self.plan:
            self.focus = max(0.0, self.focus - dt * 1.4)
        else:
            self.focus = min(self.focus_max, self.focus + dt * 0.45)
        wdt = dt * (0.35 if self.plan else 1.0) * self.fx.time_scale()
        self.time += wdt
        self.update_player(wdt, inp)
        self.update_work(wdt)
        self.update_draw(dt)
        self.update_status(wdt)
        self.update_enemies(wdt)
        self.update_waves(wdt)
        self.update_projectiles(wdt)
        self.update_aliases(dt)
        self.update_pending(wdt)
        self.update_cascade(dt)
        self.update_quality(wdt)
        self.resolve_gc()
        self.check_clear()

    def finalize(self, cleared):
        q = self.quality()
        damage = (self.run.last_room or {}).get("damage", 0.0)
        new_dead = max(0, len(self.deck.grid.dead) - self.start_dead)
        res = self.run.complete_room(cleared, q, damage, new_dead, self.time)
        self.result = res
        self.finished = True
        if cleared:
            self.state = "clear"
        else:
            self.state = "dead"
