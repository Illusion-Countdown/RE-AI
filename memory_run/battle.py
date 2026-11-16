# -*- coding: utf-8 -*-
"""战斗核心：引用图、卡牌动作、GC 级联、画质、敌人与 Boss。"""
import math
import traceback
import random

import pygame

from .const import (
    W, H, PLAY, ARENA, CYAN, CYAN_D, MAGENTA, MAGENTA_D, AMBER, AMBER_D,
    GREEN, GREEN_D, RED, RED_D, PURPLE, PURPLE_D, BLUE, TEAL, GOLD, WHITE,
    DIM, DIM2, clamp, lerp, approach, seg_point_dist, vdist, dim,
)
from .model import Node, Graph, STRONG, WEAK, DANGLING
from .cards import Hand, CARD_DEFS, Card
from . import audio

PLAYER_R = 13
DEFAULT_HP = {
    "MINION": 24, "SENTINEL": 60, "CYCLER": 50, "ALLOCATOR": 70,
    "WARD": 50, "ZOMBIE": 1, "BOMB": 20, "PYLON": 80,
    "QUANTIZER": 100, "GLITCH": 70, "TEAR": 70, "CRAWLER": 100,
    "ERASER": 200, "GC_CORE": 600, "AUDITOR": 800, "KERNEL": 500,
}
NODE_COLOR = {
    "MINION": RED, "SENTINEL": AMBER, "CYCLER": PURPLE,
    "ALLOCATOR": TEAL, "WARD": BLUE, "BOMB": GOLD, "PYLON": MAGENTA,
    "QUANTIZER": GREEN, "GLITCH": PURPLE, "TEAR": RED,
    "CRAWLER": AMBER, "ERASER": WHITE, "GC_CORE": MAGENTA,
    "AUDITOR": AMBER, "KERNEL": CYAN, "ROOT": (96, 112, 132),
}


class Projectile:
    __slots__ = ("x", "y", "vx", "vy", "r", "dmg", "color", "life", "dead",
                 "necro")

    def __init__(self, x, y, vx, vy, r, dmg, color, life=6.0, necro=False):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.r = r
        self.dmg = dmg
        self.color = color
        self.life = life
        self.dead = False
        self.necro = necro


class AliasPool:
    _next = [1]

    def __init__(self, members, duration=6.0):
        self.gid = AliasPool._next[0]
        AliasPool._next[0] += 1
        self.members = list(members)
        self.max = sum(max(1.0, m.max_hp) for m in members)
        self.hp = sum(max(0.0, m.hp) for m in members)
        self.t = duration
        for m in members:
            m.alias = self

    def sync(self):
        self.hp = max(0.0, self.hp)
        for m in self.members:
            m.hp = self.hp * (m.max_hp / max(1.0, self.max))

    def alive_members(self):
        return [m for m in self.members if m.alive]

    def clear(self):
        for m in self.members:
            if m.alias is self:
                m.alias = None


class Battle:
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

    def add_reinforcements(self, by_id):
        """提高压力但不堆小怪：给编队补 WARD/PYLON 支援，而不是塞 MINION。"""
        if self.room.get("tutorial") or self.room.get("boss"):
            self.wave_left = 1 if int(self.room.get("danger", 1)) >= 8 else 0
            return
        danger = int(self.room.get("danger", 1))
        parent = by_id.get("scope")
        for n in self.graph.nodes:
            if n.kind in ("SENTINEL", "ALLOCATOR"):
                parent = n
                break
        if parent is None:
            return
        has_ward = any(n.kind == "WARD" for n in self.graph.nodes)
        if danger >= 5 and not has_ward:
            x = PLAY.centerx + PLAY.w * 0.22
            y = PLAY.y + PLAY.h * 0.28
            w = Node("WARD", x, y, "SUPPORT.WARD",
                     hp=45 + danger * 6, r=18)
            w.data["barrier"] = True
            w.timers["atk"] = self.run.rng.uniform(0.8, 2.0)
            w.timers["special"] = 2.0
            w.hostile = True
            w.targetable = True
            w.spawn_t = 0.0
            w.born_anim = 0.45
            self.graph.add_node(w)
            self.graph.add_edge(parent, w, STRONG, unique=False)
            by_id["support_ward"] = w
        if danger >= 8:
            x = PLAY.centerx - PLAY.w * 0.24
            y = PLAY.y + PLAY.h * 0.30
            p = Node("PYLON", x, y, "SUPPORT.PYLON",
                     hp=35 + danger * 4, r=17)
            p.hostile = True
            p.targetable = True
            p.timers["atk"] = self.run.rng.uniform(0.8, 2.2)
            p.spawn_t = 0.0
            p.born_anim = 0.45
            self.graph.add_node(p)
            self.graph.add_edge(parent, p, STRONG, unique=False)
            by_id["support_pylon"] = p
        self.wave_left = 1 if danger >= 8 else 0
        self.wave_t = 8.0

    def spawn_wave(self):
        if self.wave_left <= 0 or self.room.get("tutorial"):
            return
        hubs = [n for n in self.graph.nodes if n.alive and
                n.kind in ("SENTINEL", "ALLOCATOR", "GC_CORE",
                           "AUDITOR", "KERNEL")]
        parent = hubs[0] if hubs else self.root
        if parent is None:
            return
        danger = int(self.room.get("danger", 1))
        # 协同增援：一个带辐条的 SENTINEL，而不是两隻小怪
        x = clamp(parent.x + self.run.rng.uniform(-90, 90),
                  PLAY.x + 30, PLAY.right - 30)
        y = clamp(parent.y + self.run.rng.uniform(60, 120),
                  PLAY.y + 30, PLAY.bottom - 30)
        e = Node("SENTINEL", x, y, "REINFORCE.ELITE",
                 hp=50 + danger * 6, r=20)
        e.hostile = True
        e.targetable = True
        e.timers["atk"] = self.run.rng.uniform(0.8, 2.0)
        e.spawn_t = 0.0
        e.born_anim = 0.45
        self.graph.add_node(e)
        self.graph.add_edge(parent, e, STRONG, unique=False)
        self.by_id[f"wave{self.wave_left}"] = e
        self.wave_left -= 1
        self.toast("敌方支援到位：SENTINEL 加入编队", 1.6)
        self.fx.add_shake(2.0, 8)
        self.fx.add_ring(x, y, 6, 50, AMBER, 0.45, 2)

    def update_waves(self, dt):
        if self.state != "playing" or self.wave_left <= 0:
            return
        self.wave_t -= dt
        if self.wave_t <= 0:
            self.spawn_wave()

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
    def select_slot(self, i):
        if self.state != "playing":
            return
        self.drag_active = False
        card = self.hand.slots[i]
        if card is None:
            self.nope("这个执行槽是空的")
            return
        if self.aim and self.aim.get("card") is card:
            self.aim = None
            return
        self.aim = {"card": card, "where": ("slot", i), "stage": 0, "src": None}
        mode = card.d["target"]
        if mode in ("self", "dead"):
            self.use_card(card, ("slot", i))

    def select_reserve(self, i):
        if i >= len(self.hand.reserve):
            return
        card = self.hand.reserve[i]
        if card is None:
            return
        self.aim = {"card": card, "where": ("reserve", i), "stage": 0, "src": None}
        if card.d["target"] in ("self", "dead"):
            self.use_card(card, ("reserve", i))

    def select_overflow(self, i):
        if i >= len(self.hand.overflow):
            return
        card = self.hand.overflow[i]
        if card is None:
            return
        self.aim = {"card": card, "where": ("overflow", i), "stage": 0, "src": None}
        if card.d["target"] in ("self", "dead"):
            self.use_card(card, ("overflow", i))

    # 拖拽：按住手牌 -> 拖到世界 -> 松开
    def card_in(self, where, idx):
        if where == "slot":
            return self.hand.slots[idx] if idx < 5 else None
        if where == "reserve":
            return self.hand.reserve[idx] if idx < len(self.hand.reserve) else None
        if where == "overflow":
            return self.hand.overflow[idx] if idx < len(self.hand.overflow) else None
        return None

    def preview_card(self, where, idx):
        card = self.card_in(where, idx)
        if card is None:
            return
        self.aim = {"card": card, "where": (where, idx),
                    "stage": 0, "src": None}
        self.drag_active = True

    def select_where(self, where, idx, immediate=True):
        card = self.card_in(where, idx)
        if card is None:
            self.nope("这张卡已经不在手牌里了")
            return
        self.aim = {"card": card, "where": (where, idx),
                    "stage": 0, "src": None}
        self.drag_active = False
        if immediate and card.d["target"] in ("self", "dead"):
            self.use_card(card, (where, idx))

    def drop_card_at(self, pos):
        """松手落点：按卡的 target 模式结算。"""
        if not self.aim or self.state != "playing":
            return False
        card = self.aim["card"]
        where = self.aim["where"]
        mode = card.d["target"]
        if mode == "edge":
            e = self.edge_at(pos[0], pos[1])
            if e is None:
                self.nope("松手处没有引用线")
                return False
            return self.use_card(card, where, target=e)
        if mode == "node":
            n = self.node_at(pos[0], pos[1])
            if n is None:
                self.nope("松手处没有对象")
                return False
            return self.use_card(card, where, target=n)
        if mode == "area":
            return self.use_card(card, where, target=pos)
        if mode in ("self", "dead"):
            return self.use_card(card, where)
        if mode == "two":
            n = self.node_at(pos[0], pos[1])
            if n is None:
                self.nope("松手处没有对象")
                return False
            if card.key == "LINK":
                if n is self.player_node:
                    self.nope("LINK 需要一个目标")
                    return False
                return self.use_card(card, where,
                                     target=(self.player_node, n))
            # WEAK / ALIAS：先落第一个目标，再点第二个
            self.aim.update({"stage": 1, "src": n})
            self.toast("已选中第一个目标：再点第二个；右键取消")
            return False
        return False

    def on_key(self, key, mods=0):
        if self.state != "playing":
            return
        if pygame.K_1 <= key <= pygame.K_5:
            self.select_slot(key - pygame.K_1)
        elif key == pygame.K_q:
            self.redraw()
        elif key == pygame.K_g:
            self.free_gc()
        elif key == pygame.K_r:
            self.necro_bomb()
        elif key == pygame.K_t:
            self.dead_code()

    def redraw(self):
        if self.redraw_used:
            self.nope("本房间已经重抽过了")
            return
        if not self.pile:
            self.reshuffle()
        self.redraw_used = True
        dropped = self.hand.discard_all()
        self.discarded.extend(dropped)
        for _ in range(3):
            self.draw_one(initial=True)
        self.toast("重抽：弃掉手牌，抽 3 张（本房一次）")
        self.fx.add_ring(self.player_node.x, self.player_node.y, 10, 70,
                         PURPLE, 0.5, 2)
        audio.play("select")

    def free_gc(self):
        if not self.run.has_rule("free_gc") or self.free_gc_used:
            self.nope("没有免费的 GC")
            return
        self.free_gc_used = True
        self.gc_dirty = True
        self.toast("免费 GC：引用归零的对象立即回收")
        self.fx.add_flash(0.18, CYAN, 6)
        self.fx.add_glitch(0.3)

    def necro_bomb(self):
        if not self.run.has("necro_bomb") or self.necro_bomb_used:
            self.nope("没有可用的坏死引爆")
            return
        if not self.deck.grid.dead:
            self.nope("没有坏死格可以引爆")
            return
        self.necro_bomb_used = True
        self.deck.grid.dead.pop()
        self.explode(self.player_node.x, self.player_node.y, 230, 60, MAGENTA)
        self.work_used = max(0.0, self.work_used - 2)
        self.toast("坏死引爆：消耗 1 个坏死格")
        audio.play("boom")

    def dead_code(self):
        if not self.run.has("dead_code") or self.dead_code_used:
            self.nope("没有死代码消除")
            return
        self.dead_code_used = True
        for n in self.graph.hostiles():
            n.stun = max(n.stun, 3.0)
            n.timers["atk"] = max(n.timers["atk"], 3.0)
        self.fx.add_flash(0.2, CYAN, 5)
        self.toast("死代码消除：全场敌人停火 3 秒")
        audio.play("cast")

    def on_mouse_move(self, pos):
        self.mouse = pos
        self.hover_node = self.node_at(*pos)
        self.hover_edge = None if self.hover_node else self.edge_at(*pos)
        if self.edge_drag and self.aim:
            if not self.slash:
                self.slash = [self.edge_drag]
            if vdist(self.slash[-1][0], self.slash[-1][1], pos[0], pos[1]) >= 6:
                self.slash.append(pos)
                if len(self.slash) > 64:
                    self.slash.pop(1)
            self.fx.add_parts(pos[0], pos[1], CYAN, 1, 40, 0.18, 1.2)

    def on_mouse_down(self, pos, button, mods=0):
        self.mouse = pos
        if self.state != "playing":
            return
        if button == 3:
            if self.aim:
                self.aim = None
            else:
                self.write_attack()
            return
        if button != 1:
            return
        if not self.aim:
            return
        card = self.aim["card"]
        mode = card.d["target"]
        if mode == "two":
            n = self.node_at(*pos)
            if n is None:
                self.nope("需要选中一个对象")
                return
            if self.aim["stage"] == 0:
                self.aim["src"] = n
                self.aim["stage"] = 1
                self.two_drag = pos
                self.fx.add_ring(n.x, n.y, 5, 28, card.color, 0.25, 2)
            else:
                if n is self.aim["src"]:
                    return
                self.use_card(card, self.aim["where"], target=(self.aim["src"], n))
        elif mode == "edge":
            self.edge_drag = pos
            self.slash = [pos]
        elif mode == "node":
            n = self.node_at(*pos)
            if n is not None:
                self.use_card(card, self.aim["where"], target=n)
        elif mode == "area":
            self.use_card(card, self.aim["where"], target=pos)

    def on_mouse_up(self, pos, button, mods=0):
        self.mouse = pos
        if self.state != "playing" or not self.aim:
            self.edge_drag = None
            self.two_drag = None
            return
        card = self.aim["card"]
        mode = card.d["target"]
        if mode == "edge" and self.edge_drag:
            a = self.edge_drag
            path = list(self.slash)
            if len(path) < 2 or vdist(path[-1][0], path[-1][1],
                                      pos[0], pos[1]) > 4:
                path.append(pos)
            self.edge_drag = None
            self.slash = []
            edges = self.edges_on_path(path)
            if not edges:
                self.nope("划过的地方没有引用线")
                return
            self.use_card(card, self.aim["where"], target=edges)
        elif mode == "two" and self.aim["stage"] == 1 and self.two_drag:
            n = self.node_at(*pos)
            self.two_drag = None
            if n is not None and n is not self.aim["src"]:
                self.use_card(card, self.aim["where"], target=(self.aim["src"], n))

    def edges_on_path(self, path):
        """按“第一次被划到”的顺序返回边；单剪只取第一条。"""
        found = []
        if len(path) < 2:
            return []
        for e in self.graph.edges:
            if not e.alive:
                continue
            first = None
            for i in range(len(path) - 1):
                if e.segment_cross(path[i], path[i + 1]):
                    first = i
                    break
            if first is None:
                for i in range(len(path) - 1):
                    mx = (path[i][0] + path[i + 1][0]) / 2
                    my = (path[i][1] + path[i + 1][1]) / 2
                    if e.hit_test(mx, my, 12):
                        first = i
                        break
            if first is not None:
                found.append((first, e))
        found.sort(key=lambda pair: pair[0])
        return [e for _i, e in found]

    def edges_on_line(self, a, b):
        out = []
        for e in self.graph.edges:
            if not e.alive:
                continue
            if e.segment_cross(a, b) or e.hit_test(b[0], b[1], 16):
                out.append(e)
        out.sort(key=lambda e: vdist(e.src.x, e.src.y, b[0], b[1]))
        return out

    # ================================================================ 用卡
    def card_work(self, card):
        w = card.d["work"]
        if card.key == "WEAK" and self.run.has("weak_net"):
            w = 0
        if card.up and card.key == "STEAL":
            w = max(0, w - 1)
        return w

    def spend_work(self, card):
        cost = self.card_work(card)
        if cost <= 0:
            return True
        free = max(1, self.deck.grid.free_count())
        if self.work_used + cost > free + 0.001:
            self.nope("工作内存不足：修坏死格、删卡或等它恢复")
            return False
        self.work_used += cost
        return True

    def use_card(self, card, where, target=None):
        if self.state != "playing":
            return False
        if card in self.deck.cards and card.anchor and \
                self.deck.grid.card_corroded(card) and card.key != "ECC":
            self.nope("这张卡被坏死格腐蚀了，先用 ECC 修格")
            return False
        if not self.spend_work(card):
            return False
        try:
            ok = self.apply_card(card, target)
        except Exception as exc:
            # 工具输入异常不能把整局游戏带崩；记录并安全退费
            traceback.print_exc()
            self.work_used = max(0.0, self.work_used - self.card_work(card))
            self.nope("工具执行失败，已安全取消")
            return False
        if not ok:
            # 费用已经付出，但无效目标不该吃掉卡：把工作内存退回
            self.work_used = max(0.0, self.work_used - self.card_work(card))
            return False
        kind, idx = where
        if kind == "slot":
            self.hand.take_slot(idx)
        elif kind == "reserve":
            self.hand.take_reserve(idx)
        else:
            self.hand.take_overflow(idx)
        self.hand.refill()
        if self.hand.free_slots() > 0:
            self.draw_timer = min(self.draw_timer, 0.65)
        self.aim = None
        self.edge_drag = None
        self.stats["cards"] += 1
        self.run.stats["cards"] += 1
        self.fx.add_flash(0.025, card.color, 11)
        self.fx.add_shake(1.2, 9)
        if self.card_work(card):
            self.fx.add_text(self.player_node.x + 26, self.player_node.y - 18,
                             f"-{self.card_work(card)} WORK", AMBER, 11, 0.7)
        self.fx.add_ring(self.player_node.x, self.player_node.y,
                         6, 42, card.color, 0.3, 2)
        audio.play("select")
        return True

    def apply_card(self, card, target):
        key = card.key
        up = card.up
        if key == "CUT":
            edges = target if isinstance(target, list) else [target]
            edges = [e for e in edges if e is not None]
            if not edges:
                return False
            n = 2 if up else 1
            cut = 0
            for e in edges[:n]:
                if self.cut_edge(e):
                    cut += 1
            if cut:
                self.fx.add_text(self.player_node.x, self.player_node.y - 40,
                                 f"CUT x{cut}", CYAN, 16, 0.8)
            return cut > 0
        if key == "LINK":
            if not isinstance(target, (list, tuple)) or len(target) < 2:
                return False
            a, b = target[0], target[1]
            return self.do_link(a, b, up)
        if key == "WEAK":
            if not isinstance(target, (list, tuple)) or len(target) < 2:
                return False
            a, b = target[0], target[1]
            return self.do_weak(a, b)
        if key == "CLIP":
            return self.do_clip(target, up)
        if key == "SWEEP":
            return self.do_sweep(target, 5 if up else 3)
        if key == "WEAKEN":
            edges = target if isinstance(target, list) else [target]
            edges = [e for e in edges if e is not None]
            n = 2 if up else 1
            done = 0
            for e in edges[:n]:
                if self.do_weaken_edge(e):
                    done += 1
            return done > 0
        if key == "ALIAS":
            if not isinstance(target, (list, tuple)) or len(target) < 2:
                return False
            a, b = target[0], target[1]
            return self.do_alias(a, b, 8.0 if up else 6.0)
        if key == "VOID":
            if isinstance(target, (list, tuple)):
                target = target[0] if target else None
            return self.do_cast(target, void=True, up=up)
        if key == "TRUNC":
            if isinstance(target, (list, tuple)):
                target = target[0] if target else None
            return self.do_cast(target, void=False, up=up)
        if key == "DELAY":
            edges = target if isinstance(target, list) else [target]
            edges = [e for e in edges if e is not None]
            n = 2 if up else 1
            delay = 2.0 if up else 3.0
            for e in edges[:n]:
                self.pending_cuts.append({"edge": e, "t": delay})
            if edges:
                self.fx.add_text(self.player_node.x, self.player_node.y - 40,
                                 f"DELAY {delay:.0f}s", AMBER, 15, 0.9)
            return bool(edges)
        if key == "REFLECT":
            e = target[0] if isinstance(target, (list, tuple)) and target else target
            return self.do_reflect(e, 80 if up else 40)
        if key == "STEAL":
            e = target[0] if isinstance(target, (list, tuple)) and target else target
            return self.do_steal(e, up)
        if key == "COMPRESS":
            return self.do_compress(up)
        if key == "ECC":
            return self.do_ecc(2 if up else 1)
        if key == "LOSSY":
            self.explode(target[0], target[1], 180, 120 if up else 80, GOLD)
            added = self.run.add_dead_cells(3 if up else 2)
            if added:
                self.toast(f"有损爆发：永久毁掉 {added} 个空闲格")
            self.fx.add_shake(14, 3)
            audio.play("boom")
            return True
        if key == "DOWN":
            self.slow_t = max(self.slow_t, 7.0 if up else 5.0)
            self.quality_penalty = min(45.0, self.quality_penalty + (15 if up else 20))
            self.fx.add_flash(0.15, CYAN, 5)
            self.fx.add_ring(target[0], target[1], 10, 260, CYAN, 0.6, 3)
            self.toast("降采样：敌人和子弹变慢，画质下降")
            audio.play("glitch")
            return True
        return False

    # ================================================================ 工具动作
    def cut_edge(self, e):
        if e is None or not e.alive:
            return False
        dst = e.dst
        if dst.data.get("cut_immune") and not dst.data.get("cast_stripped"):
            self.nope(f"{dst.name} 拒绝被 CUT：先用 CAST 赋予类型")
            return False
        if dst.data.get("barrier") and not dst.data.get("barrier_used"):
            dst.data["barrier_used"] = True
            self.fx.add_ring(dst.x, dst.y, dst.r * 0.7, dst.r * 2.2, BLUE, 0.4, 3)
            self.fx.add_text(dst.x, dst.y - dst.r - 12, "BARRIER", BLUE, 14, 1.0)
            self.toast("屏障吸收了这次剪断（每个对象一次）")
            audio.play("weak")
            return False
        if self.run.has("steal") and e.src is not self.player_node and \
                self.run.rng.random() < 0.30 and dst.alive:
            self.graph.remove_edge(e)
            if not self.graph.between(self.player_node, dst, STRONG):
                self.graph.add_edge(self.player_node, dst, STRONG)
            dst.data["held"] = True
            self.toast("引用窃取：这条边归你了")
        else:
            self.graph.remove_edge(e)
        self.stats["cuts"] += 1
        self.run.stats["cuts"] += 1
        self.fx.add_spark((e.src.x, e.src.y), (dst.x, dst.y), CYAN, 0.3, 3)
        self.fx.add_parts(dst.x, dst.y, CYAN, 6, 120, 0.35, 1.8)
        self.fx.add_flash(0.025, CYAN, 12)
        self.fx.add_hitstop(0.018)
        self.fx.add_shake(1.8, 8)
        self.gc_dirty = True
        audio.play("cut")
        if e.src is self.player_node:
            dst.data["held"] = False
        self.resolve_gc()
        return True

    def do_link(self, a, b, up=False):
        if a is None or b is None or a is b:
            return False
        if not a.alive or not b.alive:
            return False
        if self.graph.between(a, b, STRONG):
            self.nope("这两个对象之间已经有强引用了")
            return False
        e = self.graph.add_edge(a, b, STRONG)
        if not e:
            return False
        self.stats["links"] += 1
        self.run.stats["links"] += 1
        if a is self.player_node:
            b.data["held"] = True
            self.toast(f"持有 {b.name}：它停火，替你分摊 15% 伤害（每多 1 条 +15%，上限 45%）；不占 refcount")
        self.fx.add_dir_parts(a.x, a.y, math.atan2(b.y - a.y, b.x - a.x),
                              CYAN, 9, 210, 0.42, 2.0, 0.5)
        self.fx.add_ring(b.x, b.y, 5, 36, CYAN, 0.35, 2)
        self.fx.add_flash(0.03, CYAN, 12)
        self.fx.add_shake(1.0, 10)
        self.gc_dirty = True
        audio.play("link")
        if up:
            self.work_used = max(0.0, self.work_used - 1)
        return True

    def do_weak(self, a, b):
        if a is None or b is None or a is b or not a.alive or not b.alive:
            return False
        strong = self.graph.between(a, b, STRONG)
        weak = self.graph.between(a, b, WEAK)
        if weak:
            self.nope("这里已经有弱引用了")
            return False
        if strong:
            for e in strong:
                e.kind = WEAK
                e.alive = True
            b.data["weak_mark"] = True
            if a is self.player_node:
                b.data["held"] = False
            self.gc_dirty = True
            ang = math.atan2(b.y - a.y, b.x - a.x)
            self.fx.add_dir_parts(a.x, a.y, ang, PURPLE, 8, 200, 0.4, 2.0, .5)
            self.fx.add_ring(b.x, b.y, 6, 34, PURPLE, 0.35, 2)
            self.fx.add_text(b.x, b.y - b.r - 14, "STRONG→WEAK", PURPLE, 13, 0.8)
            self.fx.add_shake(1.6, 8)
            audio.play("weak")
            self.resolve_gc()
            return True
        self.graph.add_edge(a, b, WEAK)
        b.data["weak_mark"] = True
        ang = math.atan2(b.y - a.y, b.x - a.x)
        self.fx.add_dir_parts(a.x, a.y, ang, PURPLE, 8, 200, 0.4, 2.0, .5)
        self.fx.add_ring(b.x, b.y, 6, 34, PURPLE, 0.35, 2)
        self.fx.add_text(b.x, b.y - b.r - 14, "ref+1", PURPLE, 12, 0.75)
        self.fx.add_shake(1.6, 8)
        audio.play("weak")
        self.gc_dirty = True
        return True

    def do_clip(self, n, up=False):
        if n is None or not n.alive:
            return False
        ins = self.graph.incoming(n, STRONG)
        if not ins:
            self.nope("它没有强引用入边")
            return False
        cut = 0
        for e in list(ins):
            if self.cut_edge(e):
                cut += 1
        if cut and up:
            self.work_used = max(0.0, self.work_used - 1)
        return cut > 0

    def do_sweep(self, point, limit=3):
        def edist(e):
            pts = e.points(12)
            return min(seg_point_dist(point[0], point[1], pts[i][0], pts[i][1],
                                      pts[i + 1][0], pts[i + 1][1])
                       for i in range(len(pts) - 1))
        edges = [e for e in self.graph.edges if e.alive and edist(e) < 155]
        edges.sort(key=edist)
        cut = 0
        for e in edges[:limit]:
            if self.cut_edge(e):
                cut += 1
        if cut:
            self.fx.add_ring(point[0], point[1], 10, 170, GREEN, 0.45, 4)
            self.fx.add_text(point[0], point[1] - 20, f"SWEEP x{cut}", GREEN, 18, 1.0)
        return cut > 0

    def do_weaken_edge(self, e):
        if isinstance(e, (list, tuple)):
            e = e[0] if e else None
        if e is None or not e.alive or e.kind != STRONG:
            return False
        e.kind = WEAK
        e.dst.data["weak_mark"] = True
        if e.src is self.player_node:
            e.dst.data["held"] = False
        self.fx.add_spark((e.src.x, e.src.y), (e.dst.x, e.dst.y), PURPLE, 0.3, 3)
        self.fx.add_text(e.dst.x, e.dst.y - e.dst.r - 10, "WEAKEN", PURPLE, 14, 0.9)
        audio.play("weak")
        self.gc_dirty = True
        self.resolve_gc()
        return True

    def do_alias(self, a, b, duration):
        if a is None or b is None or a is b or not a.alive or not b.alive:
            return False
        if a.alias or b.alias:
            self.nope("其中一个对象已经在别名组里了")
            return False
        pool = AliasPool([a, b], duration)
        self.aliases.append(pool)
        if a is self.player_node or b is self.player_node:
            self.alias_pool = pool
        self.fx.add_ring(a.x, a.y, 6, 48, MAGENTA, 0.45, 3)
        self.fx.add_ring(b.x, b.y, 6, 48, MAGENTA, 0.45, 3)
        mid = ((a.x + b.x) / 2, (a.y + b.y) / 2)
        self.fx.add_ring(mid[0], mid[1], 10, 90, MAGENTA, 0.55, 3)
        self.fx.add_parts(mid[0], mid[1], MAGENTA, 22, 240, 0.6, 2.6)
        self.fx.add_text(mid[0], mid[1] - 26, "ALIAS", MAGENTA, 18, 1.0)
        self.fx.add_flash(0.12, MAGENTA, 5)
        self.fx.add_shake(6, 5)
        self.fx.add_hitstop(0.06)
        audio.play("alias")
        return True

    def do_cast(self, n, void=True, up=False):
        if n is None or not n.alive or n.kind in ("ROOT", "PLAYER"):
            return False
        if n.data.get("boss"):
            self.nope("核心对象不可 CAST")
            return False
        stripped = bool(n.data.get("destructor")) or bool(n.data.get("cut_immune"))
        n.data["cast_stripped"] = True
        n.data["cut_immune"] = False
        n.data["destructor"] = False
        n.data["cast_disable"] = 3.0 if (void and up) else (2.0 if void else 1.0)
        n.stun = max(n.stun, 3.0 if (void and up) else (2.0 if void else 1.0))
        color = WHITE if void else AMBER
        self.fx.add_ring(n.x, n.y, n.r * 0.5, n.r * 2.4, color, 0.5, 3)
        self.fx.add_flash(0.05, color, 9)
        self.fx.add_hitstop(0.02)
        self.fx.add_shake(2.2, 8)
        self.fx.add_parts(n.x, n.y, color, 14, 170, 0.5, 2.0)
        self.fx.add_text(n.x, n.y - n.r - 16,
                         "CAST<void>" if void else "CAST<int>", color, 15, 1.1)
        if not void:
            self.explode(n.x, n.y, 120, 50 if up else 34, AMBER, hit_player=False)
        if stripped:
            self.toast("析构器/类型免疫已被剥离")
        audio.play("cast")
        return True

    def do_reflect(self, e, dmg):
        if isinstance(e, (list, tuple)):
            e = e[0] if e else None
        if e is None or not e.alive:
            return False
        pos = (e.dst.x, e.dst.y)
        if not self.cut_edge(e):
            return False
        targets = [n for n in self.graph.hostiles() if n.alive]
        targets.sort(key=lambda n: vdist(n.x, n.y, pos[0], pos[1]))
        if targets:
            self.apply_damage(targets[0], dmg, GOLD, source="reflect")
            self.fx.add_spark(pos, (targets[0].x, targets[0].y), GOLD, 0.4, 3)
        return True

    def do_steal(self, e, up=False):
        if isinstance(e, (list, tuple)):
            e = e[0] if e else None
        if e is None or not e.alive:
            return False
        dst = e.dst
        if dst.data.get("cut_immune") and not dst.data.get("cast_stripped"):
            return False
        if dst.data.get("barrier") and not dst.data.get("barrier_used"):
            dst.data["barrier_used"] = True
            self.nope("屏障吸收了这次窃取")
            return False
        self.graph.remove_edge(e)
        self.graph.add_edge(self.player_node, dst, STRONG)
        dst.data["held"] = True
        self.fx.add_spark((e.src.x, e.src.y), (dst.x, dst.y), GREEN, 0.35, 3)
        self.fx.add_text(dst.x, dst.y - dst.r - 12, "STOLEN", GREEN, 15, 1.1)
        if up:
            self.work_used = max(0.0, self.work_used - 1)
        self.toast("引用窃取：它现在归你持有")
        audio.play("hijack")
        self.gc_dirty = True
        return True

    def do_compress(self, up=False):
        free = self.deck.grid.free_count()
        if free <= 0:
            self.nope("没有空闲格可以压缩")
            return False
        self.work_used = max(self.work_used, free * (0.9 if not up else 0.95))
        self.compress_t = 12.0 if (up or self.run.has("compressor")) else 8.0
        self.fx.add_flash(0.15, RED, 5)
        self.fx.add_glitch(0.35)
        self.fx.add_text(self.player_node.x, self.player_node.y - 42,
                         "COMPRESS +30%", RED, 18, 1.2)
        self.toast("压缩：工作内存拉到 90%，伤害提升，画质正在掉")
        audio.play("glitch")
        return True

    def do_ecc(self, n):
        dead = list(self.deck.grid.dead)
        if not dead:
            self.nope("没有坏死格需要修复")
            return False
        # 优先修脚下的卡，避免把整张卡腐蚀掉
        cards = [c for c in self.deck.grid.all_cards()
                 if c.anchor and any(cell in self.deck.grid.dead for cell in c.cells())]
        cells = []
        if cards:
            for c in cards:
                for cell in c.cells():
                    if cell in self.deck.grid.dead and cell not in cells:
                        cells.append(cell)
        for cell in dead:
            if cell not in cells:
                cells.append(cell)
        for cell in cells[:n]:
            self.deck.grid.dead.discard(cell)
            self.fx.add_parts(self.player_node.x, self.player_node.y,
                              GREEN, 12, 160, 0.6, 2.0)
        self.fx.add_ring(self.player_node.x, self.player_node.y, 8, 80,
                         GREEN, 0.5, 3)
        self.toast(f"纠错码：修复 {min(n, len(cells))} 个坏死格")
        audio.play("clear")
        return True

    # ================================================================ 伤害
    def apply_damage(self, n, dmg, color=WHITE, source=None):
        if n is None or not n.alive:
            return
        if n.kind == "ROOT":
            return
        if n.data.get("weak_mark"):
            dmg *= 1.35
        if n.data.get("shield_t", 0) > 0:
            dmg *= 0.55
        if n.data.get("boss") == "gc" and any(
                p.alive and p.kind == "PYLON" for p in self.graph.nodes):
            self.fx.add_text(n.x, n.y - n.r - 14, "IMMUNE", DIM, 14, 0.7)
            return
        if n.data.get("boss") == "auditor" and self.quality() < 75.0:
            q = self.quality()
            dmg *= max(0.2, 1.0 - (75.0 - q) * 0.04)
            self.fx.add_text(n.x, n.y - n.r - 14, "SHIELD", AMBER, 14, 0.6)
        if n.alias:
            pool = n.alias
            pool.hp -= dmg
            pool.sync()
            n.hit_flash = 1.0
            self.fx.add_text(n.x, n.y - n.r, f"-{int(dmg)}", color, 15, 0.6)
            if pool.hp <= 0:
                self.kill_pool(pool)
            return
        n.hp -= dmg
        n.hit_flash = 1.0
        self.stats["dmg"] += dmg
        self.run.stats["dmg"] += dmg
        self.fx.add_text(n.x, n.y - n.r, f"-{int(dmg)}", color, 15, 0.6)
        self.fx.add_parts(n.x, n.y, color, 5, 110, 0.3, 1.6)
        if n.hp <= 0:
            self.kill_node(n, source=source)

    def kill_pool(self, pool):
        members = list(pool.alive_members())
        pool.clear()
        self.aliases = [a for a in self.aliases if a is not pool]
        if pool is self.alias_pool:
            self.alias_pool = None
        for m in members:
            if m is self.player_node:
                self.die("alias")
            elif m.alive:
                self.kill_node(m, source="alias")
        self.fx.add_flash(0.35, MAGENTA, 3)
        self.fx.add_glitch(0.5)
        audio.play("death")

    def kill_node(self, n, source=None):
        if n is None or not n.alive:
            return
        if n is self.player_node:
            self.die("self")
            return
        x, y, kind = n.x, n.y, n.kind
        dtor = (n.data.get("destructor") and
                not n.data.get("cast_stripped")) or kind == "BOMB"
        if dtor:
            if self.run.has("exception") and not self.exception_used:
                self.exception_used = True
                self.pending_explosions.append((x, y, 150, 0, "exception"))
                self.toast("异常捕获：第一次析构伤害被吃掉")
            else:
                self.pending_explosions.append((x, y, 160, 26, "dtor"))
        self.graph.remove_node(n)
        self.fx.add_parts(x, y, NODE_COLOR.get(kind, WHITE), 12, 160, 0.5, 2.0)
        self.fx.add_ring(x, y, 6, 46, NODE_COLOR.get(kind, WHITE), 0.35, 2)
        self.fx.add_flash(0.03, NODE_COLOR.get(kind, WHITE), 12)
        self.fx.add_hitstop(0.015)
        self.fx.add_shake(2.0, 8)
        if n.data.get("boss"):
            self.fx.slow(0.28, 0.9)
            self.fx.add_flash(0.28, WHITE, 3)
            self.fx.add_shake(16, 2.5)
        self.note_erase(n, source)
        if source in ("write", "lossy") and not self.run.has("inline") and \
                (n.data.get("boss") or n.max_hp >= 100 or self.run.rng.random() < 0.15):
            if self.run.add_dead_cells(1):
                self.fx.add_text(x, y - 20, "LEAK", DIM, 14, 1.0)
        self.gc_dirty = True
        self.resolve_gc()

    def note_erase(self, n, source=None):
        self.erase_streak += 1
        self.streak_t = 3.0 if self.run.has_rule("window") else 2.0
        self.run.stats["gc"] += 1
        self.stats["gc"] += 1
        score = 60 * self.erase_streak
        self.run.score += score
        self.fx.add_text(n.x + 18, n.y, f"+{score}", GREEN, 13, 0.7)
        if self.erase_streak >= 3 and 3 not in self.cascade_marks:
            self.cascade_marks.add(3)
            self.work_used = max(0.0, self.work_used - 1)
            self.run.shards += 1
            self.fx.add_text(self.player_node.x, self.player_node.y - 44,
                             "CASCADE x3  工作内存 +1", GREEN, 18, 1.2)
            audio.play("clear")
        if self.erase_streak >= 5 and 5 not in self.cascade_marks:
            self.cascade_marks.add(5)
            self.work_used = max(0.0, self.work_used - 2)
            self.draw_one()
            self.fx.add_text(self.player_node.x, self.player_node.y - 44,
                             "CASCADE x5  抽 1 张", GREEN, 19, 1.3)
            audio.play("clear")
        if self.erase_streak >= 8 and 8 not in self.cascade_marks:
            self.cascade_marks.add(8)
            self.run.shards += 2
            self.gc_dirty = True
            self.extra_gc = True
            self.fx.add_flash(0.3, GREEN, 4)
            self.fx.add_glitch(0.8)
            self.fx.slow(0.35, 0.55)
            self.fx.add_text(self.player_node.x, self.player_node.y - 50,
                             "CASCADE x8  免费 GC", GREEN, 22, 1.5)
            audio.play("hijack")

    def explode(self, x, y, rad, dmg, color=GOLD, hit_player=True):
        hit = set()
        for n in list(self.graph.hostiles()):
            if not n.alive:
                continue
            if n.alias:
                if n.alias.gid in hit:
                    continue
                hit.add(n.alias.gid)
            d = vdist(n.x, n.y, x, y)
            if d <= rad + n.r * 0.5:
                self.apply_damage(n, dmg * (1 - 0.35 * d / rad), color,
                                  source="lossy" if dmg > 40 else "boom")
        if hit_player:
            d = vdist(self.player_node.x, self.player_node.y, x, y)
            if d <= rad:
                self.damage_player(dmg * 0.25 * (1 - d / rad), force=True)
        self.fx.add_ring(x, y, 10, rad, color, 0.55, 5)
        self.fx.add_parts(x, y, color, 28, 280, 0.7, 2.6)
        self.fx.add_flash(0.25, color, 3)
        self.fx.add_shake(8, 4)

    def flush_explosions(self):
        while self.pending_explosions:
            x, y, rad, dmg, kind = self.pending_explosions.pop(0)
            if dmg > 0:
                self.explode(x, y, rad, dmg, GOLD)
            else:
                self.fx.add_ring(x, y, 10, rad, GREEN, 0.4, 3)
                audio.play("weak")

    def resolve_gc(self):
        if not self.gc_dirty:
            return
        if self._resolving:
            return
        self._resolving = True
        self.gc_dirty = False
        try:
            for _ in range(120):
                victim = None
                for n in self.graph.nodes:
                    if not n.alive or n is self.player_node or n.kind == "ROOT":
                        continue
                    if not n.collectible or n.immortal:
                        continue
                    if self.graph.refcount(n) == 0:
                        victim = n
                        break
                if victim is None:
                    self.flush_explosions()
                    if self.gc_dirty:
                        self.gc_dirty = False
                        continue
                    break
                self.gc_erase(victim)
            if self.extra_gc:
                self.extra_gc = False
                self.gc_dirty = True
        finally:
            self._resolving = False
        if self.gc_dirty:
            self.resolve_gc()
        self.check_clear()

    def gc_erase(self, n):
        x, y, kind = n.x, n.y, n.kind
        dtor = (n.data.get("destructor") and
                not n.data.get("cast_stripped")) or kind == "BOMB"
        if dtor:
            self.pending_explosions.append((x, y, 160, 26, "dtor"))
        self.graph.remove_node(n)
        self.fx.add_ring(x, y, n.r * 0.3, n.r * 2.8, CYAN, 0.5, 2)
        self.fx.add_parts(x, y, CYAN, 10, 130, 0.5, 1.8)
        self.fx.add_text(x, y - n.r - 14, "GC", CYAN, 14, 0.8)
        self.fx.add_flash(0.025, CYAN, 14)
        self.fx.add_hitstop(0.012)
        self.fx.add_shake(3, 6)
        audio.play("gc")
        self.note_erase(n, source="gc")
        self.gc_dirty = True

    def check_clear(self):
        if self.state not in ("playing", "intro"):
            return
        for n in self.graph.nodes:
            if not n.alive or not n.hostile or n.kind == "ROOT":
                continue
            return
        self.state = "clear"
        self.ending = "clear"
        self.end_t = 1.8
        self.aim = None
        self.fx.add_flash(0.35, GREEN, 2.4)
        self.fx.add_glitch(0.25)
        self.fx.add_text(self.player_node.x, self.player_node.y - 70,
                         "ROOM CLEARED", GREEN, 30, 2.0)
        audio.play("clear")

    # ================================================================ 战斗更新
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

    def update_player(self, dt, inp):
        if self.iframe > 0:
            self.iframe -= dt
        if self.hurt_flash > 0:
            self.hurt_flash -= dt
        if self.spawn_flash > 0:
            self.spawn_flash -= dt
        if self.compress_t > 0:
            self.compress_t -= dt
        if self.slow_t > 0:
            self.slow_t -= dt
        if self.write_cd > 0:
            self.write_cd -= dt
        if self.dash_t > 0:
            self.dash_t -= dt
            self.iframe = max(self.iframe, 0.12)
        if self.dash_cd > 0:
            self.dash_cd -= dt
        mvx = inp.get("mvx", 0)
        mvy = inp.get("mvy", 0)
        l = math.hypot(mvx, mvy)
        if l > 1e-6:
            mvx /= l
            mvy /= l
        sp = self.speed
        self.player_node.vx = approach(getattr(self.player_node, "vx", 0.0),
                                       mvx * sp, 2600 * dt)
        self.player_node.vy = approach(getattr(self.player_node, "vy", 0.0),
                                       mvy * sp, 2600 * dt)
        self.player_node.x += self.player_node.vx * dt
        self.player_node.y += self.player_node.vy * dt
        if inp.get("dash") and self.dash_cd <= 0:
            self.dash_cd = 1.8
            self.dash_t = 0.16
            dx = self.mouse[0] - self.player_node.x
            dy = self.mouse[1] - self.player_node.y
            d = math.hypot(dx, dy) or 1
            self.player_node.x += dx / d * 150
            self.player_node.y += dy / d * 150
            self.fx.add_spark((self.player_node.x - dx / d * 140,
                               self.player_node.y - dy / d * 140),
                              (self.player_node.x, self.player_node.y), CYAN, 0.3, 4)
            self.fx.add_ring(self.player_node.x, self.player_node.y, 8, 40, CYAN, 0.3, 2)
            audio.play("dash")
        self.player_node.x = clamp(self.player_node.x, PLAY.x + 16, PLAY.right - 16)
        self.player_node.y = clamp(self.player_node.y, PLAY.y + 16, PLAY.bottom - 16)
        # 玩家不能穿过敌人
        for n in self.graph.hostiles():
            d = vdist(self.player_node.x, self.player_node.y, n.x, n.y)
            rr = PLAYER_R + n.r
            if 0.01 < d < rr:
                push = (rr - d)
                self.player_node.x += (self.player_node.x - n.x) / d * push
                self.player_node.y += (self.player_node.y - n.y) / d * push

    def update_work(self, dt):
        if self.work_used > 0:
            self.work_used = max(0.0, self.work_used - dt / self.work_regen)

    def update_draw(self, dt):
        self.draw_timer -= dt
        if self.draw_timer <= 0:
            # 手牌满时不浪费抽牌；一旦空出槽位立刻补
            if self.hand.free_slots() <= 0:
                self.draw_timer = 0.25
                return
            self.draw_one()
            self.draw_timer = max(1.2, 2.4 - self.run.draw_bonus)

    def update_status(self, dt):
        if self.banner_t > 0:
            self.banner_t -= dt
        if self.toast_t > 0:
            self.toast_t -= dt
        self.quality_drain = 0.0
        for n in self.graph.nodes:
            if n.alive and n.kind == "QUANTIZER":
                self.quality_drain += 10.0
            if n.alive:
                n.data["weak_mark"] = any(
                    e.alive and e.dst is n and e.kind == WEAK
                    for e in self.graph.edges)
                if n.data.get("shield_t", 0) > 0:
                    n.data["shield_t"] = max(0.0, n.data["shield_t"] - dt)
            if n.stun > 0:
                n.stun -= dt
            if n.hit_flash > 0:
                n.hit_flash -= dt
            n.spin += dt
            if n.born_anim > 0:
                n.born_anim = max(0.0, n.born_anim - dt)
            if n.data.get("cast_disable", 0) > 0:
                n.data["cast_disable"] -= dt

    def update_cascade(self, dt):
        if self.streak_t > 0:
            self.streak_t -= dt
        else:
            self.erase_streak = 0

    def update_quality(self, dt):
        if self.redundancy_t > 0:
            self.redundancy_t -= dt
        q = self.quality()
        self.run.note_quality(q)
        if q <= 0.05:
            self.crash_t += dt
            if self.crash_t > 1.2:
                self.die("render")
        else:
            self.crash_t = max(0.0, self.crash_t - dt)
        total = self.deck.grid.w * self.deck.grid.h
        if len(self.deck.grid.dead) >= total * 0.5:
            self.die("necro")
        if self.run.has("redundancy") and q < 25 and not self.run._redundancy_used_room():
            self.run.mark_redundancy()
            self.redundancy_t = 2.0
            self.work_used = max(0.0, self.work_used - 1)
            self.fx.add_flash(0.2, GREEN, 4)
            self.toast("冗余校验：画质从崩溃边缘被拉回 50%")

    def update_pending(self, dt):
        for item in list(self.pending_cuts):
            item["t"] -= dt
            if item["t"] <= 0:
                self.pending_cuts.remove(item)
                if item["edge"].alive:
                    self.cut_edge(item["edge"])

    def update_aliases(self, dt):
        for pool in list(self.aliases):
            pool.t -= dt
            if pool.t <= 0:
                pool.clear()
                self.aliases.remove(pool)
                if pool is self.alias_pool:
                    self.alias_pool = None
                self.fx.add_text(self.player_node.x, self.player_node.y - 30,
                                 "ALIAS EXPIRED", MAGENTA, 13, 0.8)

    # ================================================================ 玩家受伤
    def damage_player(self, amount, force=False):
        if amount <= 0:
            return
        if self.iframe > 0 and not force:
            return
        linked = [n for n in self.graph.hostiles()
                  if n.alive and self.graph.between(self.player_node, n, STRONG)]
        share = min(0.45, 0.15 * len(linked))
        taken = amount * (1.0 - share)
        if linked and share > 0:
            each = amount * share / len(linked)
            for n in linked:
                self.apply_damage(n, each, CYAN)
        if self.alias_pool and any(m is self.player_node for m in self.alias_pool.members):
            self.alias_pool.hp -= taken
            self.alias_pool.sync()
            self.hp = max(0.0, self.alias_pool.hp)
            self.fx.add_text(self.player_node.x, self.player_node.y - 30,
                             f"-{int(taken)}", RED, 17, 0.7)
            if self.alias_pool.hp <= 0:
                self.kill_pool(self.alias_pool)
            return
        self.hp -= taken
        self.run.hp = max(0.0, self.hp)
        self.run.note_damage()
        self.iframe = 0.7
        self.hurt_flash = 1.0
        self.fx.add_flash(0.10, RED, 6)
        self.fx.add_shake(5, 6)
        self.fx.add_text(self.player_node.x, self.player_node.y - 34,
                         f"-{int(taken)}", RED, 17, 0.8)
        if linked:
            self.fx.add_text(self.player_node.x, self.player_node.y - 52,
                             f"HOLD -{int(share * 100)}%", CYAN, 11, 0.6)
        audio.play("hurt")
        if self.hp <= 0:
            self.die("hp")

    def die(self, reason="hp"):
        if self.state in ("dead", "clear"):
            return
        self.state = "dead"
        self.ending = reason
        self.end_t = 1.6
        self.hp = 0
        self.run.hp = 0
        self.fx.add_flash(0.55, (255, 40, 50), 2.2)
        self.fx.add_glitch(1.2)
        self.fx.add_shake(20, 2.2)
        self.fx.add_hitstop(0.16)
        self.fx.add_text(self.player_node.x, self.player_node.y - 60,
                         "SEGFAULT" if reason == "hp" else "RENDER CRASH",
                         RED, 34, 2.0)
        audio.play("death")

    # ================================================================ WRITE
    def write_attack(self):
        if self.write_cd > 0:
            return
        self.write_cd = 0.38
        px, py = self.player_node.x, self.player_node.y
        mx, my = self.mouse
        ang = math.atan2(my - py, mx - px)
        best = None
        bestd = 1e9
        for n in self.graph.hostiles():
            if not n.alive:
                continue
            d = vdist(px, py, n.x, n.y)
            if d > 460 or d < 1:
                continue
            a = math.atan2(n.y - py, n.x - px)
            diff = abs((a - ang + math.pi) % math.tau - math.pi)
            if diff < 0.55 and d < bestd:
                best = n
                bestd = d
        tx, ty = (best.x, best.y) if best else (mx, my)
        self.fx.add_spark((px, py), (tx, ty), CYAN, 0.18, 3)
        self.fx.add_parts((px + tx) / 2, (py + ty) / 2, CYAN, 4, 90, 0.25, 1.5)
        if best:
            dmg = 16.0 * self.damage_mult()
            if self.run.has("inline"):
                dmg *= 1.5
            if self.run.has("lossless") and self.quality() >= 75:
                dmg *= 1.2
            if self.run.has("wreck"):
                dmg *= 1.0 + min(0.30, len(self.deck.grid.dead) * 0.03)
            self.apply_damage(best, dmg, CYAN, source="inline" if self.run.has("inline") else "write")
            self.fx.add_flash(0.018, CYAN, 16)
            self.fx.add_hitstop(0.012)
            self.fx.add_shake(1.8, 10)
        audio.play("write")

    # ================================================================ 敌人
    def update_enemies(self, dt):
        for n in list(self.graph.nodes):
            if not n.alive or not n.hostile or n.kind == "ROOT":
                continue
            if n.stun > 0:
                continue
            held = self.graph.between(self.player_node, n, STRONG)
            if held:
                n.data["held"] = True
                continue
            n.data["held"] = False
            if n.data.get("cast_disable", 0) > 0:
                continue
            if n.data.get("boss"):
                self.update_boss(n, dt)
                continue
            if n.kind == "MINION":
                self.enemy_move(n, dt, 72.0, 175.0)
                self.enemy_attack(n, dt, 2.2, 180, 4.0, RED)
            elif n.kind == "SENTINEL":
                self.enemy_attack(n, dt, 2.6, 210, 5.0, AMBER)
            elif n.kind == "PYLON":
                self.enemy_attack(n, dt, 3.2, 190, 4.0, MAGENTA)
            elif n.kind == "CYCLER":
                self.cycler_tick(n, dt)
                self.enemy_attack(n, dt, 2.8, 220, 5.0, PURPLE)
            elif n.kind == "ALLOCATOR":
                self.enemy_attack(n, dt, 3.4, 160, 3.0, TEAL)
                n.timers["special"] -= dt
                if n.timers["special"] <= 0:
                    n.timers["special"] = 5.0
                    self.spawn_minion(n)
            elif n.kind == "WARD":
                # 支援位：周期性给最近友军套盾，而不是自己站桩
                n.timers["special"] = n.timers.get("special", 0.0) - dt
                if n.timers["special"] <= 0:
                    n.timers["special"] = 4.0
                    allies = [x for x in self.graph.hostiles()
                              if x.alive and x is not n and x.kind != "ROOT"]
                    if allies:
                        allies.sort(key=lambda x: vdist(n.x, n.y, x.x, x.y))
                        t = allies[0]
                        t.data["shield_t"] = 4.0
                        self.fx.add_ring(t.x, t.y, t.r + 4, t.r + 26,
                                         BLUE, 0.4, 2)
                        self.fx.add_text(t.x, t.y - t.r - 12, "WARD",
                                         BLUE, 10, 0.5)
            elif n.kind == "KERNEL":
                self.enemy_attack(n, dt, 2.0, 230, 6.0, CYAN)
            elif n.kind == "BOMB":
                self.enemy_move(n, dt, 60.0, 90.0)
            elif n.kind == "QUANTIZER":
                self.enemy_attack(n, dt, 3.0, 170, 4.0, GREEN)
            elif n.kind == "GLITCH":
                self.enemy_move(n, dt, 90.0, 140.0)
                self.enemy_attack(n, dt, 2.4, 180, 4.0, PURPLE)
            elif n.kind == "TEAR":
                self.enemy_attack(n, dt, 2.8, 200, 5.0, RED)
            elif n.kind == "CRAWLER":
                self.enemy_move(n, dt, 110.0, 120.0)
                self.enemy_attack(n, dt, 2.8, 180, 5.0, AMBER, necro=True)
            elif n.kind == "ERASER":
                self.enemy_attack(n, dt, 2.2, 240, 6.0, WHITE)

    def enemy_move(self, n, dt, speed, keep):
        dx = self.player_node.x - n.x
        dy = self.player_node.y - n.y
        d = math.hypot(dx, dy) or 1
        if d > keep:
            n.x += dx / d * speed * dt
            n.y += dy / d * speed * dt
        elif d < keep * 0.65:
            n.x -= dx / d * speed * 0.5 * dt
            n.y -= dy / d * speed * 0.5 * dt
        n.x = clamp(n.x, PLAY.x + n.r, PLAY.right - n.r)
        n.y = clamp(n.y, PLAY.y + n.r, PLAY.bottom - n.r)

    def enemy_attack(self, n, dt, period, speed, dmg, color, necro=False):
        n.timers["atk"] = n.timers.get("atk", 0.0) - dt
        if n.timers["atk"] > 0:
            return
        n.timers["atk"] = period * self.run.rng.uniform(0.85, 1.15)
        rank = int(self.room.get("danger", 1))
        shots = 1 + (1 if rank >= 3 else 0) + (1 if rank >= 6 else 0)
        if rank >= 9:
            shots += 1
        if self.room.get("boss"):
            shots = max(shots, 2)
        n.timers["atk"] *= max(0.62, 1.0 - 0.045 * rank)
        if n.data.get("weak_mark"):
            dmg *= 0.65
        dmg *= 1.0 + max(0, rank - 3) * 0.04
        ang0 = math.atan2(self.player_node.y - n.y, self.player_node.x - n.x)
        sp = speed * (0.65 if self.slow_t > 0 else 1.0) * 1.06
        for i in range(shots):
            ang = ang0 + (i - (shots - 1) / 2) * 0.14
            p = Projectile(n.x, n.y, math.cos(ang) * sp,
                           math.sin(ang) * sp,
                           5 if dmg < 5 else 7, dmg, color, necro=necro)
            self.projectiles.append(p)
        audio.play("write", 0.35)

    def cycler_tick(self, n, dt):
        partner_id = n.data.get("partner")
        if not partner_id:
            return
        other = self.by_id.get(partner_id)
        if other is None or not other.alive:
            return
        if self.graph.between(n, other, WEAK):
            return
        if self.graph.between(n, other, STRONG):
            return
        n.timers["special"] -= dt
        if n.timers["special"] <= 0:
            n.timers["special"] = 1.6
            self.graph.add_edge(n, other, STRONG, unique=False)
            self.fx.add_spark((n.x, n.y), (other.x, other.y), PURPLE, 0.3, 2)
            self.toast("CYCLER 重建了强引用环")

    def spawn_minion(self, parent):
        if not parent.alive:
            return
        alive = [n for n in self.graph.nodes if n.alive and n.kind == "MINION"]
        if len(alive) > 8:
            return
        ang = self.run.rng.uniform(0, math.tau)
        x = clamp(parent.x + math.cos(ang) * 80, PLAY.x + 24, PLAY.right - 24)
        y = clamp(parent.y + math.sin(ang) * 80, PLAY.y + 24, PLAY.bottom - 24)
        m = Node("MINION", x, y, "SPAWN.{}".format(len(alive) + 1))
        m.hp = m.max_hp = 22.0 + self.run.bosses_cleared * 8
        m.r = 20
        m.timers["atk"] = 1.8
        self.graph.add_node(m)
        self.graph.add_edge(parent, m, STRONG, unique=False)
        self.fx.add_ring(x, y, 4, 34, TEAL, 0.4, 2)
        self.fx.add_text(x, y - 24, "ALLOC", TEAL, 12, 0.8)
        audio.play("link", 0.5)

    def update_boss(self, n, dt):
        boss = n.data.get("boss")
        if boss == "gc":
            alive_pylons = [p for p in self.graph.nodes if p.alive and p.kind == "PYLON"]
            if alive_pylons:
                n.data["invuln"] = True
                return
            n.data["invuln"] = False
            if not n.data.get("exposed_announced"):
                n.data["exposed_announced"] = True
                self.fx.add_flash(0.22, MAGENTA, 4)
                self.fx.add_shake(12, 3.5)
                self.fx.add_ring(n.x, n.y, 20, 220, MAGENTA, 0.7, 5)
                self.fx.slow(0.5, 0.5)
                self.fx.add_text(n.x, n.y - 70, "CORE EXPOSED", MAGENTA, 24, 1.6)
                audio.play("gcstart")
                self.toast("三根塔架已断：核心失去免疫")
            n.timers["special"] -= dt
            if n.timers["special"] <= 0:
                n.timers["special"] = 4.0
                for i in range(10):
                    ang = i * math.tau / 10 + self.time * 0.2
                    self.projectiles.append(Projectile(
                        n.x, n.y, math.cos(ang) * 150, math.sin(ang) * 150,
                        7, 5.0, MAGENTA))
                self.fx.add_ring(n.x, n.y, 20, 120, MAGENTA, 0.5, 4)
            n.timers["phase"] -= dt
            if n.timers["phase"] <= 0:
                n.timers["phase"] = 8.0
                self.spawn_minion(n)
            self.enemy_attack(n, dt, 2.4, 220, 6.0, MAGENTA)
        elif boss == "auditor":
            self.enemy_attack(n, dt, 2.4, 210, 6.0, AMBER)
            n.timers["special"] -= dt
            if n.timers["special"] <= 0:
                n.timers["special"] = 6.5
                if len(self.deck.grid.dead) - self.start_dead < 3:
                    if self.run.add_dead_cells(1):
                        self.fx.add_glitch(0.4)
                        self.toast("审计员烧坏了 1 个空闲格｜用 ECC 修回来")
                self.fx.add_text(n.x, n.y - n.r - 16, "AUDIT", AMBER, 15, 0.9)
        elif boss == "kernel":
            self.enemy_attack(n, dt, 2.6, 230, 6.0, CYAN)
            n.timers["special"] -= dt
            if n.timers["special"] <= 0:
                n.timers["special"] = 3.5
                ang = math.atan2(self.player_node.y - n.y, self.player_node.x - n.x)
                for off in (-0.25, 0, 0.25):
                    self.projectiles.append(Projectile(
                        n.x, n.y, math.cos(ang + off) * 210,
                        math.sin(ang + off) * 210, 6, 5.0, CYAN))

    def update_projectiles(self, dt):
        slow = 0.7 if self.slow_t > 0 else 1.0
        for p in list(self.projectiles):
            p.x += p.vx * dt * slow
            p.y += p.vy * dt * slow
            p.life -= dt
            if p.life <= 0 or not PLAY.collidepoint(p.x, p.y):
                self.projectiles.remove(p)
                continue
            if vdist(p.x, p.y, self.player_node.x, self.player_node.y) < p.r + PLAYER_R:
                self.projectiles.remove(p)
                self.damage_player(p.dmg, force=True)
                if p.necro:
                    if len(self.deck.grid.dead) - self.start_dead < 3:
                        if self.run.add_dead_cells(1):
                            self.fx.add_text(self.player_node.x,
                                             self.player_node.y - 40,
                                             "BAD ACCESS", RED, 14, 1.0)

    # ================================================================ 结算
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
