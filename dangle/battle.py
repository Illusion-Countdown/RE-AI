# -*- coding: utf-8 -*-
"""战斗核心：引用图操作、GC 级联、别名、UAF、泄漏、越界、敌人 AI 与 Boss。"""
import math
import random
import pygame
from .const import *
from .model import Node, Edge, Graph, STRONG, WEAK, DANGLING
from .content import ROOMS, META, BOSS_PHASE2_NODES, BOSS_PHASE2_EDGES
from .fx import FX

TOOL_NAMES = ["LINK", "CUT", "WEAK", "ALIAS", "CAST"]
TOOL_CN = ["建立引用", "剪断引用", "弱引用", "别名", "类型强转"]
TOOL_KEYS = ["1", "2", "3", "4", "5"]

PLAYER_R = 13


class Run:
    """一局的持久状态。"""

    def __init__(self, body):
        self.body = body
        self.modules = []
        self.room_index = 0
        self.score = 0
        self.lives = 3
        self.max_hp = body["hp"]
        self.hp = body["hp"]
        self.heap = body["heap"]
        self.stats = {"gc": 0, "hp_kill": 0, "leaks": 0, "dmg": 0,
                      "cuts": 0, "links": 0, "alias": 0, "hijack": 0,
                      "rooms": 0, "time": 0.0}

    def has(self, mid):
        return any(m["id"] == mid for m in self.modules)

    def add(self, mod):
        self.modules.append(mod)


class AliasPool:
    _next = [1]

    def __init__(self, members):
        self.gid = AliasPool._next[0]
        AliasPool._next[0] += 1
        self.members = []
        self.hp = 0.0
        self.max = 0.0
        for m in members:
            self.add_member(m)

    def add_member(self, n):
        if n in self.members:
            return
        self.members.append(n)
        self.hp += max(0.0, n.hp)
        self.max += max(1.0, n.max_hp)
        n.hp = 0.0
        n.alias = self

    def alive_members(self):
        return [m for m in self.members if m.alive]


class Projectile:
    __slots__ = ("x", "y", "vx", "vy", "r", "dmg", "color", "life", "homing",
                 "target", "kind", "spin", "dead")

    def __init__(self, x, y, vx, vy, r, dmg, color, life=5.0, homing=0.0,
                 target=None, kind="orb"):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.r = r
        self.dmg = dmg
        self.color = color
        self.life = life
        self.homing = homing
        self.target = target
        self.kind = kind
        self.spin = 0.0
        self.dead = False


class Beam:
    """Boss 的扫射激光。"""

    def __init__(self, node, angle, length=900, width=13, dmg=14, sweep=0.0,
                 warn=0.8, active=1.1):
        self.node = node
        self.angle = angle
        self.length = length
        self.width = width
        self.dmg = dmg
        self.sweep = sweep
        self.warn = warn
        self.active = active
        self.t = 0.0
        self.dead = False
        self.hit_cd = 0.0


class Leak:
    __slots__ = ("x", "y", "r", "born", "absorbed")

    def __init__(self, x, y, r=25):
        self.x = x
        self.y = y
        self.r = r
        self.born = 0.0
        self.absorbed = 0


class Battle:
    def __init__(self, run, room_index, fx=None):
        self.run = run
        self.room_index = room_index
        self.room = ROOMS[room_index]
        self.fx = fx or FX()
        self.graph = Graph()
        self.time = 0.0
        self.state = "intro"
        self.intro_t = 2.1
        self.end_t = 0.0
        self.ending = None
        self.tool = 0
        self.drag = None          # (src_node, current_pos)
        self.slash = []           # 剪线轨迹
        self.slash_cut = []
        self.cast_menu = None     # (node, options)
        self.hover_node = None
        self.hover_edge = None
        self.mouse = (0, 0)
        self.gc_dirty = True
        self.gc_timer = run.body["gc_period"]
        self.gc_active = 0.0
        self.gc_flash = 0.0
        self.gc_count = 0
        self.plan = False
        self.focus = 4.0
        self.focus_max = 4.0
        self.max_slices = run.body["slices"] + (2 if run.has("overclock") else 0)
        self.slices = min(self.max_slices, max(3.0, self.max_slices * 0.6))
        self.regen = run.body["regen"] * (1.25 if run.has("overclock") else 1.0)
        self.max_heap = run.body["heap"] + (2 if run.has("heap_x") else 0)
        self.heap = min(self.max_heap, run.heap)
        self.projectiles = []
        self.beams = []
        self.leaks = []
        self.dangling = []        # 悬垂指针 {x,y,life,edge_dir}
        self.memory = 0.0
        self.doom = 0.0
        self.write_cd = 0.0
        self.erase_streak = 0
        self.erase_streak_t = 0.0
        self.heap_frac = 0.0
        self.banner = None
        self.toast_msg = ""
        self.toast_t = 0.0
        self.oob = False
        self.oob_entered = False
        self.ub_done = False
        self.meta_cd = 0.0
        self.boss_phase = 0
        self.boss_intro = 0.0
        self.boss_wave = 0.0
        self.boss_spawned = False
        self.realloc_queue = []
        self.dead_code_used = False
        self.pending_explosions = []
        self.hit_flash = 0.0
        self.root = None
        self.player_held = []
        self.body = run.body
        self.bod_id = run.body["id"]
        self.deg = 0               # 树退化层数
        self.rooted = 0.0
        self.chain_hist = []
        self.banner_t = 0.0
        self.load = 0.0
        self._hijacked_uids = set()
        self._dchain = False
        self._rehash_anim = False
        self.calm = 1.0
        self.tool = 1 if room_index == 0 else 0   # 第一关默认 CUT，教学优先
        self.disaster_t = self.body.get("disaster_t", 0.0)
        self.stats = {"gc": 0, "hp_kill": 0, "leaks": 0, "dmg": 0, "cuts": 0,
                      "links": 0, "alias": 0, "hijack": 0}

        # 玩家
        self.px = PLAY.centerx
        self.py = PLAY.centery + 120
        self.pvx = 0.0
        self.pvy = 0.0
        self.hp = run.hp
        self.max_hp = run.max_hp
        self.lives = run.lives
        self.iframe = 0.0
        self.dash_cd = 0.0
        self.hurt_flash = 0.0
        self.spawn_flash = 1.0
        self.alias_pool = None

        self.disaster_t = {"list": 15.0, "array": 18.0,
                           "hash": 12.0}.get(self.bod_id, 999.0)
        self.build_room()

    # ================================================================ 构建
    def build_room(self):
        g = self.graph
        r = self.room
        self.root = None
        self.calm = r.get("calm", 1.0)
        nodes = {}
        for d in r["nodes"]:
            hpk = d.get("hp")
            n = Node(d["kind"], 0, 0, d.get("name") or d["kind"])
            if hpk is not None:
                n.hp = n.max_hp = float(hpk)
            else:
                n.hp = n.max_hp = 1.0
            n.data["def"] = d
            nodes[d["id"]] = n
            g.add_node(n)
            if d["kind"] == "ROOT" and self.root is None:
                self.root = n
            if d["kind"] == "ROOT":
                n.immortal = True
                n.collectible = False
                n.hostile = False
                n.targetable = True
                n.r = 17
            if d["kind"] == "ZOMBIE":
                n.collectible = False
                n.immortal = True
                n.r = 24
                n.hp = n.max_hp = 1
            if d["kind"] == "BOMB":
                n.r = 23
            if d["kind"] == "CORE":
                n.r = 42
            if d["kind"] == "PYLON":
                n.r = 26
            if d["kind"] == "ALLOCATOR":
                n.r = 28
            if d["kind"] == "SENTINEL":
                n.r = 30
            if d["kind"] == "CYCLER":
                n.r = 26
            # 高血量单位视觉上更大
            if d["kind"] in ("MINION", "SENTINEL") and n.max_hp > 40:
                n.r = min(40, 20 + math.sqrt(n.max_hp) * 1.15)
        # 位置（百分比 -> 绝对）
        for d in r["nodes"]:
            n = nodes[d["id"]]
            n.x = PLAY.x + d["p"][0] * PLAY.w
            n.y = PLAY.y + d["p"][1] * PLAY.h
        # 玩家节点
        self.player_node = Node("PLAYER", self.px, self.py, "SELF", hp=self.hp, r=PLAYER_R)
        self.player_node.immortal = True
        self.player_node.collectible = False
        self.player_node.hostile = False
        self.player_node.targetable = True
        g.add_node(self.player_node)
        g.player = self.player_node
        # 边
        for a, b, kind in r["edges"]:
            if a in nodes and b in nodes:
                g.add_edge(nodes[a], nodes[b], kind)
        # 初始数据
        for d in r["nodes"]:
            n = nodes[d["id"]]
            n.data.update({k: v for k, v in d.items() if k not in
                           ("id", "kind", "p", "name", "hp")})
            n.timers["atk"] = random.uniform(2.3, 3.6) * self.calm
            n.timers["spawn"] = random.uniform(4.0, 7.0) * self.calm
            n.timers["rebuild"] = 1.6
            n.timers["act"] = random.uniform(1.0, 3.0)
            n.spawn_t = self.time
        # 泄漏
        lr = 36 if self.run.has("leak_cover") else 25
        for (px, py) in r.get("leaks", []):
            lk = Leak(PLAY.x + px * PLAY.w, PLAY.y + py * PLAY.h, lr)
            lk.born = 0.0
            self.leaks.append(lk)
            self.memory += self.leak_pressure()
        self.graph.time = self.time
        if r.get("boss"):
            self.enter_boss_phase1()
        if self.run.has("bomb_cache") and self.root:
            self.spawn_bomb()
        self.gc_dirty = True

    def leak_pressure(self):
        return 7.0 if self.run.has("leak_cover") else 14.0

    def node_at(self, x, y, pad=10):
        return self.graph.pick_at(x, y, pad)

    # ================================================================ 常量
    def cost(self, what):
        c = {"LINK": 1, "CUT": 1, "WEAK": 1, "ALIAS": 2, "CAST": 3,
             "WRITE": 1, "META": 2}[what]
        if what == "WEAK" and self.run.has("weak_f"):
            c = 0
        if what == "ALIAS" and self.run.has("alias_e"):
            c = 1
        if what == "META" and self.run.has("ptr_prec"):
            c = max(1, c - 1)
        return c

    def can_pay(self, what):
        if self.gc_active > 0:
            return True
        return self.slices >= self.cost(what) - 1e-6

    def pay(self, what):
        if self.gc_active > 0:
            return True
        c = self.cost(what)
        if self.slices + 1e-6 < c:
            self.nope("时间片不足")
            return False
        self.slices -= c
        return True

    def nope(self, msg):
        self.toast(msg)
        self.fx.add_text(self.px, self.py - 40, msg, AMBER, 15, 0.8)
        self.fx.add_flash(0.06, AMBER, 8)

    def toast(self, msg):
        self.toast_msg = msg
        self.toast_t = 2.6

    # ================================================================ 操作
    def action_link(self, a, b, kind=STRONG):
        if a is None or b is None or a is b:
            self.nope("无效目标")
            return False
        if not a.alive or not b.alive:
            return False
        if self.graph.between(a, b, kind):
            self.nope("已有同类型引用")
            return False
        what = "WEAK" if kind == WEAK else "LINK"
        if not self.pay(what):
            return False
        e = self.graph.add_edge(a, b, kind)
        if not e:
            return False
        self.stats["links"] += 1
        self.fx.add_dir_parts(a.x, a.y, math.atan2(b.y - a.y, b.x - a.x),
                              PURPLE if kind == WEAK else CYAN, 8, 200, 0.4, 2.0, 0.5)
        self.fx.add_ring(b.x, b.y, 6, 34, PURPLE if kind == WEAK else CYAN, 0.35, 2)
        self.fx.add_text(b.x, b.y - b.r - 14, "ref+1", CYAN if kind == STRONG else PURPLE, 13, 0.7)
        self.fx.add_shake(1.6, 8)
        self.gc_dirty = True
        sfx("link")
        return True

    def cut_edge(self, e, silent=False):
        if e is None or not e.alive:
            return False
        if e.kind == DANGLING:
            return self.cut_dangling(e)
        if not self.pay("CUT"):
            return False
        pts = e.points(10)
        self.graph.remove_edge(e)
        self.stats["cuts"] += 1
        col = e.color
        self.fx.add_spark(pts[0], pts[5], WHITE, 0.26, 3)
        self.fx.add_spark(pts[5], pts[-1], col, 0.26, 3)
        for i in range(3):
            k = random.uniform(0.15, 0.85)
            p = bezier(pts[0], e.ctrl(), pts[-1], k)
            self.fx.add_parts(p[0], p[1], col, 6, 170, 0.45, 2.2)
        self.fx.add_shake(3.2, 7)
        self.fx.add_hitstop(0.025)
        self.fx.add_text(e.dst.x, e.dst.y - e.dst.r - 16, "ref-1", RED, 13, 0.7)
        self.gc_dirty = True
        sfx("cut")
        if self.bod_id == "hash" and not silent and random.random() < 0.28:
            # 冲突：连锁剪断一条同源边
            sib = [x for x in self.graph.outgoing(e.src) if x.alive and x is not e]
            if sib:
                s2 = random.choice(sib)
                self.graph.remove_edge(s2)
                self.stats["cuts"] += 1
                p = s2.points(10)
                self.fx.add_spark(p[0], p[5], CYAN, 0.3, 2)
                self.fx.add_text(s2.dst.x, s2.dst.y - 30, "冲突！", CYAN, 15, 0.8)
                self.fx.add_shake(4)
                self.gc_dirty = True
        return True

    def cut_dangling(self, e):
        """剪断悬垂边：对应的僵尸/脏对象消失。"""
        if not self.pay("CUT"):
            return False
        z = e.dst
        self.graph.remove_edge(e)
        if z.alive and z.kind == "ZOMBIE":
            self.kill_special(z, "悬垂边剪断")
        self.fx.add_shake(3)
        return True

    def action_alias(self, a, b):
        if a is None or b is None or a is b:
            return False
        if not a.alive or not b.alive:
            return False
        if a.kind == "ROOT" or b.kind == "ROOT":
            self.nope("不能与 SCOPE 别名")
            return False
        if self.heap < 1:
            self.nope("堆不足")
            return False
        if a.alias and b.alias and a.alias is b.alias:
            self.nope("已在同一别名组")
            return False
        if not self.pay("ALIAS"):
            return False
        self.heap -= 1
        self.stats["alias"] += 1
        self.run.stats["alias"] += 1
        if a.alias and b.alias:
            pa, pb = a.alias, b.alias
            for m in list(pb.members):
                pa.add_member(m)
            pool = pa
        elif a.alias:
            a.alias.add_member(b)
            pool = a.alias
        elif b.alias:
            b.alias.add_member(a)
            pool = b.alias
        else:
            pool = AliasPool([a, b])
        if a.kind == "PLAYER" or b.kind == "PLAYER":
            self.alias_pool = pool
        # 视觉
        mid = ((a.x + b.x) / 2, (a.y + b.y) / 2)
        self.fx.add_ring(mid[0], mid[1], 10, 90, MAGENTA, 0.55, 3)
        self.fx.add_parts(mid[0], mid[1], MAGENTA, 22, 240, 0.6, 2.6)
        self.fx.add_text(mid[0], mid[1] - 26, "ALIAS", MAGENTA, 18, 1.0)
        self.fx.add_shake(6, 5)
        self.fx.add_flash(0.12, MAGENTA, 5)
        self.fx.add_hitstop(0.06)
        sfx("alias")
        self.gc_dirty = True
        return True

    def action_cast(self, n, mode):
        if n is None or not n.alive:
            return False
        if not self.pay("CAST"):
            return False
        if mode == "NULL":
            n.stun = 3.0
            n.stun_max = 3.0
            n.data["cast_null"] = True
            detached = []
            for e in self.graph.outgoing(n):
                if e.alive:
                    detached.append((e.src, e.dst, e.kind))
                    self.graph.remove_edge(e)
            n.data["detached"] = detached
            self.fx.add_glitch(0.9)
            self.fx.add_flash(0.16, (180, 240, 255), 6)
            self.fx.add_shake(8, 5)
            self.fx.add_hitstop(0.09)
            self.fx.add_ring(n.x, n.y, 10, 120, CYAN, 0.5, 3)
            self.fx.add_text(n.x, n.y - n.r - 20, "SEGFAULT // NULL", CYAN, 16, 1.2)
            self.toast("空指针解引用：目标眩晕 3 秒，出边暂时悬空")
            sfx("cast")
            self.gc_dirty = True
            return True
        elif mode == "INT":
            n.data["int"] = True
            self.area_damage(n.x, n.y, 120, 34, AMBER, exclude=n)
            n.hit_flash = 1.0
            for i in range(14):
                a = random.uniform(0, math.tau)
                self.fx.add_dir_parts(n.x, n.y, a, AMBER, 4, 320, 0.6, 2.4)
            self.fx.add_text(n.x, n.y - n.r - 20, "CAST<int>", AMBER, 16, 1.2)
            self.fx.add_text(n.x + 40, n.y + 18, "小数部分溢出", AMBER, 13, 1.1)
            self.fx.add_glitch(0.5)
            self.fx.add_shake(7, 5)
            self.fx.add_hitstop(0.05)
            self.fx.add_flash(0.1, AMBER, 7)
            self.toast("类型强转：目标的行为被截断，无法再重建引用")
            sfx("cast")
            self.gc_dirty = True
            return True
        return False

    def write_attack(self):
        if self.write_cd > 0:
            return False
        mx, my = self.mouse
        best = None
        bd = 1e9
        for n in self.graph.nodes:
            if not n.alive or not n.hostile or n.hijacked or n.kind == "ROOT":
                continue
            d = math.hypot(n.x - self.px, n.y - self.py)
            if d > 150:
                continue
            d2 = math.hypot(n.x - mx, n.y - my)
            if d2 < bd:
                bd = d2
                best = n
        if best is None:
            self.nope("范围内没有可写入的对象")
            return False
        if not self.pay("WRITE"):
            return False
        self.write_cd = 0.38
        ang = math.atan2(best.y - self.py, best.x - self.px)
        self.fx.add_spark((self.px, self.py), (best.x, best.y), WHITE, 0.2, 2)
        self.fx.add_dir_parts(best.x, best.y, ang, WHITE, 9, 180, 0.35, 2.0, 0.8)
        dmg = 16
        if best.kind == "ZOMBIE" or best.data.get("int"):
            self.fx.add_glitch(0.4)
            self.fx.add_text(best.x, best.y - 30, "脏数据", RED, 15, 0.8)
            self.damage_player(3, source=None, silent=True)
            return True
        self.apply_damage(best, dmg, WHITE, leak=True, source="write")
        if self.run.has("vamp"):
            self.heal_player(4)
        self.fx.add_shake(2.5, 9)
        self.fx.add_hitstop(0.02)
        sfx("write")
        return True

    # ================================================================ 伤害
    def apply_damage(self, n, dmg, color=WHITE, leak=False, source=None):
        if n is None or not n.alive:
            return
        if n.kind == "ROOT" or n.kind == "PLAYER":
            return
        n.hit_flash = 1.0
        self.fx.add_text(n.x, n.y - n.r - 8, f"-{int(dmg)}", color, 15, 0.7)
        self.fx.add_parts(n.x, n.y, color, 8, 160, 0.4, 2.0)
        if n.alias:
            pool = n.alias
            mult = 1.25 if self.run.has("alias_e") else 1.0
            pool.hp -= dmg * mult
            for m in pool.alive_members():
                m.hit_flash = 1.0
            self.fx.add_parts(n.x, n.y, MAGENTA, 10, 200, 0.45, 2.2)
            if pool.hp <= 0:
                self.kill_alias_pool(pool)
            return
        n.hp -= dmg
        if n.hp <= 0:
            self.kill_by_damage(n, leak=leak)

    def kill_by_damage(self, n, leak=True):
        if not n.alive:
            return
        if leak and n.kind not in ("ROOT", "BOMB"):
            self.add_leak(n.x, n.y)
            self.stats["leaks"] += 1
            self.run.stats["leaks"] += 1
        self.kill_special(n, "写入击杀")
        self.stats["hp_kill"] += 1
        self.run.stats["hp_kill"] += 1
        self.fx.add_text(n.x, n.y - 46, "DIRECT WRITE", AMBER, 13, 0.9)
        self.fx.add_shake(5, 6)
        self.fx.add_hitstop(0.04)

    def kill_alias_pool(self, pool):
        if pool is self.alias_pool:
            self.alias_pool = None
        for m in pool.alive_members():
            self.fx.add_ring(m.x, m.y, 8, 60, MAGENTA, 0.4, 2)
            if m.kind == "PLAYER":
                self.damage_player(999, source=None, force=True)
                continue
            self.kill_special(m, "别名同步死亡")
        self.fx.add_flash(0.14, MAGENTA, 4)
        self.fx.add_shake(9, 4)
        pool.members = []

    def kill_special(self, n, why=""):
        """非 GC 的直接移除（爆炸/别名同步/僵尸）。"""
        if not n.alive:
            return
        x, y = n.x, n.y
        self.fx.add_parts(x, y, n.color, 20, 260, 0.6, 2.6)
        self.fx.add_ring(x, y, 8, 62, n.color, 0.4, 2)
        has_weak = any(e.alive and e.src is self.player_node and e.dst is n
                       and e.kind == WEAK for e in self.graph.edges)
        self.graph.remove_node(n)
        if has_weak:
            self.schedule_realloc(x, y)
            self.convert_dangling(n, x, y)
        self.gc_dirty = True
        self.check_clear()

    # ================================================================ GC
    def gc_erase(self, n, cascade=1):
        if not n.alive:
            return
        pts = [(n.x + random.uniform(-n.r, n.r),
                n.y + random.uniform(-n.r, n.r)) for _ in range(16)]
        for p in pts:
            self.fx.add_parts(p[0], p[1], CYAN, 2, 90, 0.7, 2.0,
                              spread=None, drag=1.2)
        self.fx.add_ring(n.x, n.y, n.r * 0.4, n.r * 3.2, CYAN, 0.55, 2)
        self.fx.add_text(n.x, n.y - n.r - 12, "GARBAGE COLLECTED", CYAN, 14, 1.0)
        self.fx.add_shake(3.5 + min(6, cascade * 1.5), 6)
        self.fx.add_hitstop(0.03)
        self.stats["gc"] += 1
        self.run.stats["gc"] += 1
        self.erase_streak += 1
        self.erase_streak_t = 0.45
        score = 60 * cascade
        self.run.score += score
        self.fx.add_text(n.x + 30, n.y + 4, f"+{score}", GREEN, 16, 0.9)
        # 悬垂指针：玩家指向它的弱引用保留下来，槽位之后会被重新分配
        has_weak = any(e.alive and e.src is self.player_node and e.dst is n
                       and e.kind == WEAK for e in self.graph.edges)
        if has_weak:
            self.schedule_realloc(n.x, n.y)
        self.graph.remove_node(n)
        if has_weak:
            self.convert_dangling(n, n.x, n.y)
        # 资源返还
        self.heap_frac += 1
        if self.heap_frac >= 3:
            self.heap_frac = 0
            self.heap = min(self.max_heap, self.heap + 1)
        if self.run.has("gc_bat"):
            self.slices = min(self.max_slices + 2, self.slices + 1)
        sfx("gc")
        self.gc_dirty = True
        self.check_clear()

    def schedule_realloc(self, x, y):
        if not self.room.get("realloc"):
            return
        if any(abs(r["x"] - x) < 30 and abs(r["y"] - y) < 30 for r in self.realloc_queue):
            return
        self.realloc_queue.append({"x": x, "y": y, "t": 3.0, "kind": "realloc"})

    def _near(self, x, y, np_):
        return (abs(x - (PLAY.x + np_[0] * PLAY.w)) < 90 and
                abs(y - (PLAY.y + np_[1] * PLAY.h)) < 90)

    def convert_dangling(self, n, x, y):
        """玩家指向已回收对象的弱引用 -> 悬垂指针。"""
        for e in list(self.graph.edges):
            if e.alive and e.src is self.player_node and e.dst is n and e.kind == WEAK:
                self.graph.remove_edge(e)
        self.dangling.append({"x": x, "y": y, "life": 9.0,
                              "kind": n.kind, "name": n.name})
        self.fx.add_text(x, y - 40, "DANGLING", RED, 14, 1.3)
        self.fx.add_glitch(0.35)
        self.fx.add_parts(x, y, RED, 10, 120, 0.6, 2.0)

    def resolve_gc(self):
        if not self.gc_dirty:
            return
        for _ in range(40):
            self.gc_dirty = False
            changes = False
            victim = None
            for n in list(self.graph.nodes):
                if not n.alive:
                    continue
                if n.kind == "ZOMBIE":
                    if not self.graph.incoming(n, DANGLING):
                        victim = n
                        break
                    continue
                if not n.collectible or n.immortal:
                    continue
                if self.graph.refcount(n) == 0:
                    victim = n
                    break
            if victim is None:
                break
            changes = True
            n = victim
            if n.kind == "CORE" and self.boss_phase == 1 and \
                    self.room.get("boss"):
                self.boss_phase_transition(n)
                continue
            if n.kind == "BOMB":
                self.detonate(n)
                continue
            self.gc_erase(n)
        # 连环擦除奖励
        if self.erase_streak >= 2 and self.erase_streak_t > 0:
            if self.run.has("cascade"):
                self.slices = min(self.max_slices + 2, self.slices + 2)
                self.heal_player(8)
                self.run.score += 80
                self.fx.add_text(self.player_node.x, self.player_node.y - 40,
                                 f"级联 x{self.erase_streak}", GREEN, 20, 1.2)
            else:
                self.fx.add_text(self.player_node.x, self.player_node.y - 40,
                                 f"CASCADE x{self.erase_streak}", GREEN, 17, 1.0)
        self.erase_streak = 0
        self.flush_explosions()
        self.check_clear()

    def flush_explosions(self):
        while self.pending_explosions:
            x, y, rad, dmg = self.pending_explosions.pop(0)
            self.area_damage(x, y, rad, dmg, GOLD)

    def detonate(self, n):
        x, y = n.x, n.y
        pool = n.alias
        has_weak = any(e.alive and e.src is self.player_node and e.dst is n
                       and e.kind == WEAK for e in self.graph.edges)
        self.graph.remove_node(n)
        if has_weak:
            self.convert_dangling(n, x, y)
        self.fx.add_flash(0.5, (255, 220, 150), 3.2)
        self.fx.add_shake(17, 3)
        self.fx.add_hitstop(0.11)
        self.fx.add_ring(x, y, 12, 210, GOLD, 0.6, 6)
        self.fx.add_ring(x, y, 6, 120, WHITE, 0.35, 3)
        self.fx.add_parts(x, y, GOLD, 46, 520, 0.9, 3.0)
        self.fx.add_parts(x, y, WHITE, 22, 320, 0.6, 2.2)
        self.fx.add_text(x, y - 50, "FREE()", GOLD, 24, 1.2)
        # 别名：爆炸直接结算进共享血池
        if pool and pool.hp > 0:
            pool.hp -= 260
            for m in pool.alive_members():
                m.hit_flash = 1.0
                self.fx.add_ring(m.x, m.y, 6, 70, GOLD, 0.5, 3)
            if pool is self.alias_pool:
                self.hp = pool.hp
            if pool.hp <= 0:
                self.kill_alias_pool(pool)
        self.pending_explosions.append((x, y, 200, 240))
        self.gc_dirty = True
        sfx("boom")

    def area_damage(self, x, y, rad, dmg, color=WHITE, exclude=None):
        hit_pools = set()
        for n in list(self.graph.nodes):
            if not n.alive or n is exclude or n.kind == "ROOT":
                continue
            d = math.hypot(n.x - x, n.y - y)
            if d <= rad + n.r * 0.5:
                if n.alias and n.alias.gid in hit_pools:
                    continue
                if n.alias:
                    hit_pools.add(n.alias.gid)
                fall = 1.0 - 0.3 * (d / max(1, rad))
                self.apply_damage(n, dmg * fall, color)
        d = math.hypot(self.px - x, self.py - y)
        if d <= rad and exclude is not self.player_node:
            self.damage_player(int(dmg * 0.28 * (1 - d / rad)), source=None, silent=True)

    # ================================================================ 泄漏
    def add_leak(self, x, y):
        lr = 36 if self.run.has("leak_cover") else 25
        lk = Leak(x + random.uniform(-6, 6), y + random.uniform(-6, 6), lr)
        lk.born = self.time
        self.leaks.append(lk)
        self.memory += self.leak_pressure()
        self.fx.add_ring(x, y, 30, 8, DIM, 0.4, 2)
        self.fx.add_text(x, y - 36, "LEAK", DIM, 14, 1.0)
        if self.memory >= 100:
            self.oom()

    def oom(self):
        self.memory = 0
        self.leaks.clear()
        self.fx.add_glitch(1.4)
        self.fx.add_flash(0.4, (255, 60, 70), 2.4)
        self.fx.add_shake(14, 3)
        self.toast("OUT OF MEMORY — 泄漏清零，代价是一条命")
        self.lose_life(oom=True)

    # ================================================================ 玩家
    def heal_player(self, amount):
        if self.alias_pool:
            self.alias_pool.hp = min(self.alias_pool.max,
                                     self.alias_pool.hp + amount)
            self.fx.add_text(self.px, self.py - 30, f"+{int(amount)}", GREEN, 15, 0.8)
            return
        self.hp = min(self.max_hp, self.hp + amount)
        self.fx.add_text(self.px, self.py - 30, f"+{int(amount)}", GREEN, 15, 0.8)

    def damage_player(self, amount, source=None, silent=False, force=False):
        if self.iframe > 0 and not force:
            return
        if self.alias_pool:
            mult = 1.25 if self.run.has("alias_e") else 1.0
            self.alias_pool.hp -= amount * mult
            self.hp = self.alias_pool.hp
            if self.alias_pool.hp <= 0:
                self.lose_life()
                if self.alias_pool:
                    self.alias_pool.members = [m for m in self.alias_pool.members
                                               if m.kind == "PLAYER"]
                    self.alias_pool = None
                self.hp = self.max_hp * 0.4
            return
        self.hp -= amount
        self.run.stats["dmg"] += amount
        self.stats["dmg"] += amount
        self.hurt_flash = 1.0
        self.iframe = 0.85 if not force else 0.2
        self.fx.vignette_red = 1.0
        self.fx.add_shake(6, 5)
        self.fx.add_flash(0.10, (255, 60, 70), 7)
        self.fx.add_hitstop(0.03)
        self.fx.add_text(self.px, self.py - 34, f"-{int(amount)}", RED, 18, 0.9)
        sfx("hurt")
        # 持有者分摊
        for n in self.held_nodes():
            if n.alive:
                self.apply_damage(n, amount * 0.4, CYAN)
        # 空指针护盾
        if self.run.has("null_shield") and source is not None and \
                source.alive and random.random() < 0.35:
            source.stun = max(source.stun, 1.5)
            source.stun_max = 1.5
            self.fx.add_text(source.x, source.y - 30, "SEGFAULT", CYAN, 14, 1.0)
        if self.hp <= 0:
            self.lose_life()

    def lose_life(self, oom=False):
        self.lives -= 1
        self.run.lives = self.lives
        self.fx.add_flash(0.55, (255, 40, 50), 2.2)
        self.fx.add_glitch(1.2)
        self.fx.add_shake(20, 2.2)
        self.fx.add_hitstop(0.16)
        if self.lives <= 0:
            self.hp = 0
            self.state = "dead"
            self.ending = "dead"
            self.end_t = 0.0
            self.fx.add_text(self.px, self.py - 60, "SEGFAULT", RED, 40, 2.0)
            sfx("death")
            return
        self.hp = self.max_hp * 0.55
        self.run.hp = self.hp
        self.iframe = 2.0
        self.slices = self.max_slices
        self.fx.add_text(self.px, self.py - 70, f"REF 剩余 {self.lives}", RED, 22, 1.6)
        self.toast(f"进程崩溃，回滚到快照（剩余 {self.lives} 次）")

    def held_nodes(self):
        out = []
        for e in self.graph.edges:
            if e.alive and e.src is self.player_node and e.kind == STRONG:
                if e.dst.alive and e.dst.kind != "PLAYER":
                    out.append(e.dst)
        return out

    def is_held(self, n):
        return bool(self.graph.between(self.player_node, n, STRONG))

    # ================================================================ 移动
    def update_player(self, dt, inp):
        if self.rooted > 0:
            self.rooted -= dt
            inp = {"mvx": 0, "mvy": 0, "plan": inp.get("plan"), "dash": False}
        speed = self.body["speed"]
        if self.bod_id == "tree":
            speed *= max(0.55, 1 - 0.12 * self.deg)
        if self.oob:
            speed *= 0.7
        mvx = inp.get("mvx", 0)
        mvy = inp.get("mvy", 0)
        l = math.hypot(mvx, mvy)
        if l > 1:
            mvx /= l
            mvy /= l
        accel = 2400.0
        self.pvx = approach(self.pvx, mvx * speed, accel * dt)
        self.pvy = approach(self.pvy, mvy * speed, accel * dt)
        self.px += self.pvx * dt
        self.py += self.pvy * dt
        # 边界：PLAY 内正常，进入 BAND 即越界
        nx = clamp(self.px, ARENA.x + 8, ARENA.right - 8)
        ny = clamp(self.py, ARENA.y + 8, ARENA.bottom - 8)
        self.px, self.py = nx, ny
        # 泄漏物挡路
        for lk in self.leaks:
            d = math.hypot(self.px - lk.x, self.py - lk.y)
            rr = lk.r + PLAYER_R
            if d < rr and d > 1e-3:
                push = (rr - d)
                self.px += (self.px - lk.x) / d * push
                self.py += (self.py - lk.y) / d * push
        was_oob = self.oob
        self.oob = not PLAY.collidepoint(self.px, self.py)
        if self.oob and not was_oob:
            self.enter_oob()
        if self.oob:
            drain = 0.0 if self.run.has("ptr_prec") else 5.0
            if drain:
                self.hp -= drain * dt
                if self.hp <= 0:
                    self.lose_life()
            if random.random() < dt * 6:
                self.fx.add_glitch(0.12)
        self.player_node.x = self.px
        self.player_node.y = self.py
        # 冲刺
        if inp.get("dash") and self.bod_id == "list" and self.dash_cd <= 0:
            self.dash_cd = 2.2
            dx = self.mouse[0] - self.px
            dy = self.mouse[1] - self.py
            d = math.hypot(dx, dy) or 1
            dist = min(230, d)
            tx = clamp(self.px + dx / d * dist, PLAY.x + 10, PLAY.right - 10)
            ty = clamp(self.py + dy / d * dist, PLAY.y + 10, PLAY.bottom - 10)
            self.fx.add_spark((self.px, self.py), (tx, ty), CYAN, 0.3, 4)
            self.fx.add_parts(self.px, self.py, CYAN, 16, 220, 0.5, 2.4)
            self.px, self.py = tx, ty
            self.fx.add_ring(tx, ty, 8, 46, CYAN, 0.3, 2)
            sfx("dash")

    def enter_oob(self):
        self.fx.add_glitch(0.6)
        self.fx.add_flash(0.12, (120, 255, 220), 8)
        self.fx.add_shake(5, 6)
        if not self.ub_done:
            self.ub_done = True
            if random.random() < 0.45 and not self.run.has("ptr_prec"):
                self.fx.add_glitch(1.1)
                roll = random.random()
                if roll < 0.4:
                    self.hp -= 10
                    self.fx.add_text(self.px, self.py - 44, "UB: 越界写入自身 -10", RED, 16, 1.4)
                elif roll < 0.7:
                    self.slices = max(0, self.slices - 2)
                    self.fx.add_text(self.px, self.py - 44, "UB: 时间片被覆写", AMBER, 16, 1.4)
                else:
                    self.heap = min(self.max_heap, self.heap + 1)
                    self.fx.add_text(self.px, self.py - 44, "UB: 读到一块好内存 +1 堆", GREEN, 16, 1.4)
                sfx("glitch")
        self.toast("越界：你正在读写竞技场之外的那一格")

    def try_metadata(self, which):
        if not self.oob:
            self.nope("站到边界之外才能读写元数据")
            return False
        if self.meta_cd > 0:
            return False
        meta = META[which]
        if which not in self.room.get("oob", []):
            self.nope("本关没有可用的元数据")
            return False
        if not self.pay("META"):
            return False
        self.meta_cd = 1.0
        self.fx.add_glitch(0.5)
        self.fx.add_flash(0.14, meta["color"], 7)
        self.fx.add_shake(5, 6)
        self.fx.add_text(self.px, self.py - 50, meta["cn"], meta["color"], 18, 1.3)
        if which == "spawn":
            for n in self.graph.hostiles():
                n.timers["atk"] = max(n.timers.get("atk", 0), 8.0)
                n.timers["spawn"] = max(n.timers.get("spawn", 0), 8.0)
            self.toast("刷新表已冻结：敌人 8 秒内不会行动")
        elif which == "refcount":
            cnt = 0
            for n in self.graph.hostiles():
                ins = self.graph.incoming(n, STRONG)
                if ins:
                    self.graph.remove_edge(random.choice(ins))
                    cnt += 1
                    self.fx.add_spark((n.x - 30, n.y - 20), (n.x + 30, n.y + 20), CYAN, 0.3, 2)
            self.toast(f"引用计数表：{cnt} 个敌人各失去 1 条入边")
            self.gc_dirty = True
        elif which == "heap":
            self.slices = min(self.max_slices, self.slices + 3)
            self.heap = min(self.max_heap, self.heap + 2)
            self.toast("竞技场元数据：+3 时间片，+2 堆")
        elif which == "boss":
            for n in self.graph.nodes:
                if n.alive and n.kind == "CORE":
                    for e in list(self.graph.outgoing(n)):
                        self.graph.remove_edge(e)
            self.toast("Boss 元数据：核心的全部出边被抹除")
            self.gc_dirty = True
        sfx("meta")
        return True

    # ================================================================ 输入
    def on_mouse_down(self, pos, button, mods):
        if self.state != "playing":
            return
        mx, my = pos
        self.mouse = pos
        if self.cast_menu:
            self.handle_cast_click(pos, button)
            return
        if button == 3:
            self.write_attack()
            return
        if button != 1:
            return
        # 元数据
        if self.oob:
            for which, (mxx, myy) in META_POS.items():
                if math.hypot(mx - mxx, my - myy) < 26:
                    self.try_metadata(which)
                    return
        n = self.node_at(mx, my)
        tool = self.tool
        if tool == 1:      # CUT
            if n is not None:
                if self.bod_id == "array":
                    return self.special_cut(n, "in")
                if self.bod_id == "tree":
                    return self.special_cut(n, "out")
            e = self.graph.edge_at(mx, my, 15)
            if e:
                self.cut_edge(e)
                return
            self.slash = [(mx, my)]
            return
        if tool == 4:      # CAST
            if n is not None:
                self.cast_menu = {"node": n, "t": 0.0}
            return
        if n is not None and n.alive:
            self.drag = {"src": n, "pos": (mx, my)}

    def handle_cast_click(self, pos, button):
        n = self.cast_menu["node"]
        x = min(max(n.x + 50, 12), W - 300)
        y = min(max(n.y - 40, 100), H - 160)
        r = pygame.Rect(int(x), int(y), 286, 118)
        if button == 3:
            self.cast_menu = None
            return
        for i, mode in enumerate(("NULL", "INT")):
            rr = pygame.Rect(r.x + 8, r.y + 46 + i * 32, r.w - 16, 28)
            if rr.collidepoint(pos):
                self.action_cast(n, mode)
                self.cast_menu = None
                return
        if not r.collidepoint(pos):
            self.cast_menu = None

    def on_mouse_move(self, pos):
        self.mouse = pos
        if self.state != "playing":
            return
        mx, my = pos
        if self.drag:
            self.drag["pos"] = (mx, my)
            self.hover_node = self.node_at(mx, my)
        else:
            self.hover_node = self.node_at(mx, my)
            self.hover_edge = self.graph.edge_at(mx, my, 13) if not self.hover_node else None
        if self.slash:
            a = self.slash[-1]
            if math.hypot(mx - a[0], my - a[1]) > 2:
                self.slash.append((mx, my))
                if len(self.slash) > 22:
                    self.slash.pop(0)
                # 剪断穿过的边
                for e in list(self.graph.edges):
                    if not e.alive:
                        continue
                    if e.segment_cross(a, (mx, my)):
                        if self.gc_active > 0 or self.can_pay("CUT"):
                            if self.cut_edge(e):
                                self.slash_cut.append(math.hypot(mx - a[0], my - a[1]))

    def on_mouse_up(self, pos, button):
        if button == 1 and self.drag:
            self.mouse = pos
            b = self.node_at(pos[0], pos[1])
            a = self.drag["src"]
            self.drag = None
            if b is None or not b.alive:
                return
            t = self.tool
            if t == 0:
                self.action_link(a, b, STRONG)
            elif t == 2:
                self.action_link(a, b, WEAK)
            elif t == 3:
                self.action_alias(a, b)
        self.slash = []

    def special_cut(self, n, mode):
        """数组：剪全部入边；树：剪全部出边。"""
        extra = 1
        if not self.pay("CUT"):
            return False
        if self.gc_active <= 0:
            if self.slices < extra:
                self.nope("时间片不足")
                return False
            self.slices -= extra
        if mode == "in":
            es = [e for e in self.graph.incoming(n) if e.alive]
        else:
            es = [e for e in self.graph.outgoing(n) if e.alive]
            self.deg += 1
            if self.deg == 4:
                self.fx.add_text(self.px, self.py - 60, "退化：链表", PURPLE, 20, 1.6)
            self.fx.add_text(n.x, n.y - 40, f"范围失效 x{len(es)}", PURPLE, 15, 1.0)
        for e in es:
            self.graph.remove_edge(e)
        if es:
            for e in es:
                d = e.dst
                self.fx.add_parts(d.x, d.y, PURPLE if mode == "out" else CYAN,
                                  8, 180, 0.5, 2.2)
            self.fx.add_shake(4 + len(es), 5)
            self.fx.add_flash(0.08, CYAN, 8)
            self.fx.add_hitstop(0.03)
            self.gc_dirty = True
            sfx("cut")
        return True

    def choose_tool(self, idx):
        self.tool = idx
        self.cast_menu = None
        self.drag = None
        sfx("ui")

    def refresh(self):
        self.gc_dirty = True

    # ================================================================ 更新
    def update(self, dt, inp):
        if self.fx.hitstop > 0:
            self.fx.hitstop -= dt
            self.fx.update(dt * 0.22)
            self.player_node.x = self.px
            self.player_node.y = self.py
            return
        self.fx.update(dt)
        if self.state == "intro":
            self.intro_t -= dt
            self.update_world(dt, inp, frozen=True)
            if self.intro_t <= 0:
                self.state = "playing"
            return
        if self.state in ("dead", "victory"):
            self.end_t += dt
            self.update_world(dt, inp, frozen=True)
            return
        if self.state == "clear":
            self.end_t += dt
            self.update_world(dt, inp, frozen=True)
            if self.end_t > 2.2:
                self.state = "done"
            return

        self.run.stats["time"] += dt
        self.plan = bool(inp.get("plan")) and self.focus > 0.02 and self.gc_active <= 0
        if self.plan:
            self.focus = max(0.0, self.focus - dt)
        else:
            self.focus = min(self.focus_max, self.focus + dt * 0.4)
        frozen = self.plan or self.gc_active > 0

        self.update_world(dt, inp, frozen=frozen)
        # 时间片
        if not frozen:
            self.slices = min(self.max_slices, self.slices + self.regen * dt)
        if self.gc_active > 0:
            self.slices = self.max_slices
        self.write_cd = max(0, self.write_cd - dt)
        self.meta_cd = max(0, self.meta_cd - dt)
        self.dash_cd = max(0, self.dash_cd - dt)
        self.iframe = max(0, self.iframe - dt)
        self.hurt_flash = max(0, self.hurt_flash - dt * 2)
        self.spawn_flash = max(0, self.spawn_flash - dt * 1.5)
        if self.toast_t > 0:
            self.toast_t -= dt
        if self.erase_streak_t > 0:
            self.erase_streak_t -= dt
        if self.banner_t > 0:
            self.banner_t -= dt
        if self.cast_menu:
            self.cast_menu["t"] += dt
        self.player_node.hp = self.max_hp if not self.alias_pool else self.alias_pool.hp

    def update_world(self, dt, inp, frozen=False):
        self.time += dt
        self.graph.time = self.time
        if not frozen:
            self.update_player(dt, inp)
            self.update_enemies(dt)
            self.update_disaster(dt)
            self.update_gc_timer(dt)
            self.update_boss(dt)
        else:
            # 冻结时仍允许极慢的粒子
            if self.gc_active > 0:
                self.gc_active -= dt
                if self.gc_active <= 0:
                    self.gc_active = 0
                    self.gc_timer = self.body["gc_period"]
                    self.fx.add_flash(0.1, (120, 200, 255), 6)
                    self.fx.add_ring(self.px, self.py, 20, 260, CYAN, 0.5, 2)
                self.fx.add_glitch(dt * 0.4)
        self.update_spawns(dt)
        self.update_projectiles(dt, frozen)
        self.update_beams(dt, frozen)
        self.update_alias(dt)
        self.update_dangling(dt)
        self.resolve_gc()
        if self.memory > 0.01:
            self.memory = max(0.0, self.memory - dt * 0.35)
        self.check_clear()

    def update_alias(self, dt):
        if self.alias_pool and self.alias_pool.hp > 0:
            self.hp = self.alias_pool.hp
        self.player_node.x = self.px
        self.player_node.y = self.py
        for n in self.graph.nodes:
            if not n.alive:
                continue
            if n.stun > 0:
                n.stun -= dt
                if n.stun <= 0:
                    n.stun = 0.0
                    self.restore_edges(n)

    def restore_edges(self, n):
        det = n.data.pop("detached", None)
        if not det:
            return
        for (a, b, kind) in det:
            if a.alive and b.alive and not self.graph.between(a, b, kind):
                self.graph.add_edge(a, b, kind)
        self.fx.add_ring(n.x, n.y, 60, 10, CYAN, 0.3, 2)
        self.gc_dirty = True

    def update_dangling(self, dt):
        for d in self.dangling:
            d["life"] -= dt
        self.dangling = [d for d in self.dangling if d["life"] > 0]
        # 新分配 -> UAF 劫持
        for d in list(self.dangling):
            for n in self.graph.nodes:
                if not n.alive or n.hostile is False or n.hijacked:
                    continue
                if n.uid in self._hijacked_uids:
                    continue
                age = self.time - n.spawn_t
                if 0.0 <= age < 1.6 and math.hypot(n.x - d["x"], n.y - d["y"]) < 76:
                    self.hijack(n, d)
                    break

    def hijack(self, n, d):
        if d in self.dangling:
            self.dangling.remove(d)
        self._hijacked_uids.add(n.uid)
        n.hijacked = True
        self.stats["hijack"] += 1
        self.run.stats["hijack"] += 1
        self.run.score += 220
        self.heap = min(self.max_heap, self.heap + 1)
        self.slices = min(self.max_slices, self.slices + 1)
        self.fx.add_flash(0.35, (120, 255, 180), 3)
        self.fx.add_glitch(0.8)
        self.fx.add_shake(12, 3.5)
        self.fx.add_hitstop(0.10)
        self.fx.add_ring(n.x, n.y, 10, 160, GREEN, 0.7, 4)
        self.fx.add_text(n.x, n.y - 40, "UAF HIJACK", GREEN, 26, 1.8)
        self.fx.add_text(n.x, n.y - 8, "该槽位现在归你", GREEN, 14, 1.6)
        self.toast("UAF 劫持：你保留了指向已释放槽位的悬垂指针")
        sfx("hijack")
        # 控制权 = 拔掉它的全部引用，让它被回收
        for e in list(self.graph.incoming(n)):
            self.graph.remove_edge(e)
        n.immortal = False
        n.collectible = True
        self.gc_dirty = True

    def update_gc_timer(self, dt):
        if self.gc_active > 0:
            return
        self.gc_timer -= dt
        if self.gc_timer <= 0:
            self.trigger_gc("周期")

    def trigger_gc(self, why=""):
        if self.gc_active > 0:
            return
        self.gc_active = 2.2
        self.gc_timer = 1e9
        self.slices = self.max_slices
        self.fx.add_flash(0.28, (120, 200, 255), 3.2)
        self.fx.add_glitch(0.8)
        self.fx.add_shake(8, 4)
        self.fx.add_ring(self.px, self.py, 30, 420, CYAN, 0.7, 2)
        self.fx.add_text(PLAY.centerx, PLAY.y + 60, "GC PAUSE", CYAN, 34, 1.8)
        self.fx.add_text(PLAY.centerx, PLAY.y + 94, "STOP THE WORLD · 拓扑操作免费", CYAN, 15, 1.8)
        self.gc_count += 1
        sfx("gcstart")

    def update_disaster(self, dt):
        b = self.body
        self.disaster_t -= dt
        for e in self.graph.edges:
            if e.warn > 0:
                e.warn = max(0.0, e.warn - dt)
        if self.bod_id == "list":
            if self.disaster_t <= 3.0 and not self._dchain:
                self._dchain = True
                mine = [e for e in self.graph.edges
                        if e.alive and e.src is self.player_node
                        and e.kind in (STRONG, WEAK)]
                if mine:
                    self._doomed = random.choice(mine)
                    self._doomed.warn = 3.0
                    dst = self._doomed.dst
                    self.fx.add_text(dst.x, dst.y - dst.r - 30, "断链预警", RED, 14, 1.2)
                self.toast("断链预警：3 秒后你的一条引用会断")
            if self.disaster_t <= 0:
                self.disaster_t = 15.0
                self._dchain = False
                e = getattr(self, "_doomed", None)
                if e is None or not e.alive:
                    mine = [x for x in self.graph.edges
                            if x.alive and x.src is self.player_node
                            and x.kind in (STRONG, WEAK)]
                    e = random.choice(mine) if mine else None
                self._doomed = None
                if e is not None and e.alive:
                    pts = e.points(8)
                    self.fx.add_spark(pts[0], pts[-1], RED, 0.4, 3)
                    self.graph.remove_edge(e)
                    self.fx.add_text(self.px, self.py - 40, "断链！", RED, 20, 1.2)
                    self.fx.add_shake(8, 5)
                    self.gc_dirty = True
                    self.damage_player(8, force=False)
        elif self.bod_id == "array":
            if self.disaster_t <= 0:
                self.disaster_t = 18.0
                self.rooted = 1.2
                self.fx.add_shake(13, 2.4)
                self.fx.add_text(self.px, self.py - 60, "扩容", GREEN, 22, 1.2)
                self.toast("扩容：全场震动，你被钉在原地 1.2 秒")
        elif self.bod_id == "hash":
            load = min(1.0, len(self.graph.alive_nodes()) * 0.055)
            self.load = load
            if load >= 0.75 and self.disaster_t <= 0 and not getattr(self, "_rehash_anim", False):
                self._rehash_anim = True
                self.disaster_t = 12.0
                self.rehash()
        elif self.bod_id == "tree":
            pass

    def rehash(self):
        self.fx.add_glitch(1.0)
        self.fx.add_flash(0.22, BLUE, 4)
        self.fx.add_shake(12, 3)
        self.toast("REHASH：整张图重新洗牌")
        pts = [(n.x, n.y) for n in self.graph.nodes if n.alive and n.kind != "PLAYER"]
        random.shuffle(pts)
        i = 0
        for n in self.graph.nodes:
            if not n.alive or n.kind == "PLAYER":
                continue
            if i < len(pts):
                self.fx.add_parts(n.x, n.y, BLUE, 10, 220, 0.6, 2.4)
                n.x, n.y = pts[i]
                i += 1
        self.fx.add_text(self.px, self.py - 60, "REHASH", BLUE, 24, 1.6)
        self._rehash_anim = False
        self.disaster_t = 12.0

    def update_spawns(self, dt):
        # 重新分配队列（UAF 演示）
        for item in list(self.realloc_queue):
            item["t"] -= dt
            if item["t"] <= 0:
                x, y = item["x"], item["y"]
                self.realloc_queue.remove(item)
                if not any(math.hypot(n.x - x, n.y - y) < 55
                           for n in self.graph.nodes if n.alive):
                    n = self.spawn_minion(x, y, link_from=self.root,
                                          name="REALLOC.%d" % random.randint(10, 99))
                    self.fx.add_text(x, y - 34, "realloc()", TEAL, 13, 1.0)
                    self.fx.add_glitch(0.2)

    def spawn_minion(self, x, y, link_from=None, name=None):
        n = Node("MINION", x, y, name or f"MINION.{random.randint(30, 99)}", 24)
        n.r = 21
        n.spawn_t = self.time
        n.born_anim = 1.0
        n.timers["atk"] = random.uniform(1.8, 3.0)
        n.timers["spawn"] = 99
        self.graph.add_node(n)
        if link_from is not None and link_from.alive:
            self.graph.add_edge(link_from, n, STRONG)
        self.fx.add_ring(x, y, 4, 46, RED, 0.4, 2)
        self.fx.add_parts(x, y, RED, 12, 150, 0.5, 2.2)
        self.gc_dirty = True
        return n

    def spawn_bomb(self):
        ang = random.uniform(0, math.tau)
        x = clamp(self.px + math.cos(ang) * 120, PLAY.x + 40, PLAY.right - 40)
        y = clamp(self.py + math.sin(ang) * 120, PLAY.y + 40, PLAY.bottom - 40)
        n = Node("BOMB", x, y, "BOMB.CACHE", 20)
        n.r = 23
        n.spawn_t = self.time
        self.graph.add_node(n)
        if self.root:
            self.graph.add_edge(self.root, n, STRONG)
        self.fx.add_ring(x, y, 6, 60, GOLD, 0.5, 2)
        self.gc_dirty = True

    # ---------------------------------------------------------------- 敌人
    def update_enemies(self, dt):
        for n in list(self.graph.nodes):
            if not n.alive or not n.hostile or n.hijacked:
                continue
            if n.kind == "ROOT" or n.kind == "BOMB":
                continue
            n.spin += dt * 0.6
            n.hit_flash = max(0, n.hit_flash - dt * 3)
            n.born_anim = max(0, n.born_anim - dt * 2)
            if n.stun > 0:
                continue
            if self.is_held(n):
                continue
            if n.data.get("int") and n.kind in ("CYCLER", "ALLOCATOR", "SENTINEL"):
                # 整型化：行为被截断，只剩基本攻击
                self.tick_attack(n, dt, basic=True)
                continue
            if n.kind == "MINION":
                self.tick_attack(n, dt)
            elif n.kind == "SENTINEL":
                self.tick_attack(n, dt, burst=True)
                self.tick_sentinel_spawn(n, dt)
            elif n.kind == "CYCLER":
                self.tick_cycler(n, dt)
                self.tick_attack(n, dt, lance=True)
            elif n.kind == "ALLOCATOR":
                self.tick_attack(n, dt, big=True)
                self.tick_alloc(n, dt)
            elif n.kind == "ZOMBIE":
                self.tick_zombie(n, dt)
            elif n.kind == "PYLON":
                self.tick_attack(n, dt, spread=True)
            elif n.kind == "CORE":
                self.tick_core(n, dt)
        # 软分离
        ns = [n for n in self.graph.nodes if n.alive and n.kind != "PLAYER"]
        for i in range(len(ns)):
            a = ns[i]
            for j in range(i + 1, len(ns)):
                b = ns[j]
                dx, dy = b.x - a.x, b.y - a.y
                d = math.hypot(dx, dy)
                mind = a.r + b.r + 10
                if 0.01 < d < mind:
                    push = (mind - d) * 0.5
                    ux, uy = dx / d, dy / d
                    a.x -= ux * push * 0.12
                    a.y -= uy * push * 0.12
                    b.x += ux * push * 0.12
                    b.y += uy * push * 0.12
        for n in ns:
            n.x = clamp(n.x, PLAY.x + n.r * 0.6, PLAY.right - n.r * 0.6)
            n.y = clamp(n.y, PLAY.y + n.r * 0.6, PLAY.bottom - n.r * 0.6)

    def tick_attack(self, n, dt, basic=False, burst=False, lance=False,
                    big=False, spread=False):
        cal = self.calm
        n.timers["atk"] = n.timers.get("atk", 2.5) - dt
        if n.timers["atk"] > 0:
            return
        if n.kind == "MINION":
            n.timers["atk"] = 2.9 * cal
            self.fire_at(n, self.px, self.py, 150, 0.028, 7, RED, 13)
        elif n.kind == "SENTINEL":
            n.timers["atk"] = 4.8 * cal
            self.radial(n, 12, 145, 6, AMBER, 11)
        elif n.kind == "CYCLER":
            n.timers["atk"] = 3.4 * cal
            self.fire_at(n, self.px, self.py, 300, 0.012, 10, PURPLE, 10, fast=True)
        elif n.kind == "ALLOCATOR":
            n.timers["atk"] = 4.2 * cal
            self.fire_at(n, self.px, self.py, 95, 0.006, 13, TEAL, 19, big=True)
        elif n.kind == "PYLON":
            n.timers["atk"] = 3.6 * cal
            ang = math.atan2(self.py - n.y, self.px - n.x)
            for i in range(5):
                a = ang + (i - 2) * 0.17
                self.fire_dir(n, a, 190, 7, MAGENTA, 9)
        elif n.kind == "CORE":
            pass

    def fire_at(self, n, tx, ty, speed, homing, dmg, color, r, fast=False, big=False):
        ang = math.atan2(ty - n.y, tx - n.x)
        vx, vy = math.cos(ang) * speed, math.sin(ang) * speed
        p = Projectile(n.x + math.cos(ang) * (n.r + 4),
                       n.y + math.sin(ang) * (n.r + 4),
                       vx, vy, r, dmg, color, 6.0, homing, None,
                       "big" if big else "orb")
        self.projectiles.append(p)
        self.fx.add_dir_parts(n.x, n.y, ang, color, 5, 130, 0.3, 2.0, 0.5)

    def fire_dir(self, n, ang, speed, dmg, color, r):
        vx, vy = math.cos(ang) * speed, math.sin(ang) * speed
        self.projectiles.append(Projectile(
            n.x + math.cos(ang) * (n.r + 4), n.y + math.sin(ang) * (n.r + 4),
            vx, vy, r, dmg, color, 6.0, 0.0, None, "orb"))

    def radial(self, n, count, speed, dmg, color, r, offset=0.0):
        for i in range(count):
            a = offset + i * math.tau / count
            self.fire_dir(n, a, speed, dmg, color, r)
        self.fx.add_ring(n.x, n.y, n.r, n.r + 40, color, 0.35, 2)

    def tick_sentinel_spawn(self, n, dt):
        n.timers["spawn"] = n.timers.get("spawn", 9.0) - dt
        if n.timers["spawn"] > 0:
            return
        n.timers["spawn"] = 9.5 * self.calm
        kids = [c for c in self.graph.nodes
                if c.alive and c.hostile and c.kind == "MINION" and
                self.graph.between(n, c, STRONG)]
        if len(kids) >= 4:
            return
        ang = random.uniform(0, math.tau)
        x = clamp(n.x + math.cos(ang) * 105, PLAY.x + 40, PLAY.right - 40)
        y = clamp(n.y + math.sin(ang) * 105, PLAY.y + 40, PLAY.bottom - 40)
        m = self.spawn_minion(x, y, link_from=n)
        self.fx.add_text(n.x, n.y - n.r - 20, "分配", AMBER, 12, 0.9)

    def tick_alloc(self, n, dt):
        n.timers["spawn"] = n.timers.get("spawn", 6.5) - dt
        if n.timers["spawn"] > 0:
            return
        n.timers["spawn"] = 7.0
        # 优先放进空闲槽位
        slot = None
        best = 1e9
        for (sx, sy) in self.room.get("free_slots", []):
            wx = PLAY.x + sx * PLAY.w
            wy = PLAY.y + sy * PLAY.h
            if not any(math.hypot(m.x - wx, m.y - wy) < 60
                       for m in self.graph.nodes if m.alive):
                d = math.hypot(wx - n.x, wy - n.y)
                if d < best:
                    best = d
                    slot = (wx, wy)
        if slot is None:
            ang = random.uniform(0, math.tau)
            slot = (clamp(n.x + math.cos(ang) * 90, PLAY.x + 40, PLAY.right - 40),
                    clamp(n.y + math.sin(ang) * 90, PLAY.y + 40, PLAY.bottom - 40))
        self.spawn_minion(slot[0], slot[1], link_from=n)
        self.fx.add_text(n.x, n.y - n.r - 20, "malloc()", TEAL, 12, 0.9)

    def tick_cycler(self, n, dt):
        part = n.data.get("partner")
        if not part:
            return
        partner = None
        for m in self.graph.nodes:
            if m.alive and m.name.endswith(part.upper()) and m.kind == "CYCLER":
                partner = m
                break
        if partner is None:
            for m in self.graph.nodes:
                if m.alive and m is not n and m.kind == "CYCLER":
                    partner = m
                    break
        if partner is None:
            return
        n.timers["rebuild"] = n.timers.get("rebuild", 2.5) - dt
        if n.timers["rebuild"] > 0:
            return
        n.timers["rebuild"] = 2.5
        if n.data.get("int"):
            return
        strong = self.graph.between(n, partner, STRONG)
        weak = self.graph.between(n, partner, WEAK)
        if not strong and not weak:
            self.graph.add_edge(n, partner, STRONG)
            self.fx.add_spark((n.x, n.y), (partner.x, partner.y), PURPLE, 0.35, 2)
            self.fx.add_text(n.x, n.y - 30, "环重建", PURPLE, 13, 0.9)
            self.gc_dirty = True

    def tick_zombie(self, n, dt):
        if n.stun > 0:
            return
        ang = math.atan2(self.py - n.y, self.px - n.x)
        sp = 62
        n.x += math.cos(ang) * sp * dt
        n.y += math.sin(ang) * sp * dt
        n.angle = ang
        d = math.hypot(n.x - self.px, n.y - self.py)
        if d < n.r + PLAYER_R and self.iframe <= 0:
            self.damage_player(11, source=n)
            self.fx.add_parts(self.px, self.py, RED, 12, 200, 0.5, 2.4)
            ang2 = math.atan2(n.y - self.py, n.x - self.px)
            n.x += math.cos(ang2) * 90
            n.y += math.sin(ang2) * 90
            self.fx.add_glitch(0.4)

    def tick_core(self, n, dt):
        if n.kind != "CORE":
            return
        # 重新锚定自己：被剪掉的塔架引用会被重建
        n.timers["relink"] = n.timers.get("relink", 5.0) - dt
        if n.timers["relink"] <= 0 and n.stun <= 0:
            n.timers["relink"] = 6.0
            ins = self.graph.incoming(n, STRONG)
            if self.boss_phase == 1 and len(ins) < 3:
                pyl = [p for p in self.graph.nodes
                       if p.alive and p.kind == "PYLON"
                       and not self.graph.between(p, n, STRONG)]
                if pyl:
                    p = random.choice(pyl)
                    self.graph.add_edge(p, n, STRONG)
                    self.fx.add_spark((p.x, p.y), (n.x, n.y), MAGENTA, 0.4, 2)
                    self.fx.add_text(n.x, n.y - n.r - 22, "RE-ANCHOR", MAGENTA, 13, 1.0)
                    self.gc_dirty = True
            elif self.boss_phase == 2:
                partners = [m for m in self.graph.nodes if m.alive and m.kind == "CORE"
                            and m is not n]
                if partners:
                    p = partners[0]
                    if not self.graph.between(n, p, STRONG) and \
                            not self.graph.between(n, p, WEAK) and not n.data.get("int"):
                        self.graph.add_edge(n, p, STRONG)
                        self.fx.add_spark((n.x, n.y), (p.x, p.y), MAGENTA, 0.4, 2)
                        self.fx.add_text(n.x, n.y - n.r - 22, "RE-CYCLE", MAGENTA, 13, 1.0)
                        self.gc_dirty = True
        n.timers["atk"] = n.timers.get("atk", 3.0) - dt
        if n.timers["atk"] <= 0:
            self.boss_wave += 1
            n.timers["atk"] = 2.9 if self.boss_phase == 2 else 3.4
            self.radial(n, 16 if self.boss_phase == 2 else 12, 150, 8, MAGENTA, 9,
                        offset=n.spin)
            self.spin_boss = getattr(self, "spin_boss", 0) + 0.27
            self.fx.add_ring(n.x, n.y, 30, 210, MAGENTA, 0.4, 3)
        if self.boss_phase == 2:
            n.timers["gc"] = n.timers.get("gc", 9.0) - dt
            if n.timers["gc"] <= 0:
                n.timers["gc"] = 10.0
                self.trigger_gc("Boss")
            n.timers["beam"] = n.timers.get("beam", 8.0) - dt
            if n.timers["beam"] <= 0:
                n.timers["beam"] = 9.5
                ang = math.atan2(self.py - n.y, self.px - n.x)
                self.beams.append(Beam(n, ang, dmg=16,
                                       sweep=random.choice([-0.85, 0.85]),
                                       warn=0.85, active=1.0))
                self.fx.add_text(n.x, n.y - n.r - 24, "LASER", MAGENTA, 14, 1.0)
            # 召唤
            n.timers["summon"] = n.timers.get("summon", 8.0) - dt
            if n.timers["summon"] <= 0:
                n.timers["summon"] = 9.0
                self.spawn_minion(clamp(n.x + random.uniform(-90, 90), PLAY.x + 40, PLAY.right - 40),
                                  clamp(n.y + random.uniform(-90, 90), PLAY.y + 40, PLAY.bottom - 40),
                                  link_from=n)

    def update_projectiles(self, dt, frozen=False):
        if frozen:
            return
        px, py = self.px, self.py
        for p in self.projectiles:
            if p.dead:
                continue
            if p.homing:
                ang = math.atan2(py - p.y, px - p.x)
                cur = math.atan2(p.vy, p.vx)
                d = (ang - cur + math.pi) % math.tau - math.pi
                cur += clamp(d, -p.homing * 60, p.homing * 60) * dt
                sp = math.hypot(p.vx, p.vy)
                p.vx, p.vy = math.cos(cur) * sp, math.sin(cur) * sp
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.spin += dt * 8
            p.life -= dt
            if p.life <= 0:
                p.dead = True
                continue
            # 出界
            if not (PLAY.x - 10 < p.x < PLAY.right + 10 and
                    PLAY.y - 10 < p.y < PLAY.bottom + 10):
                p.dead = True
                continue
            # 泄漏吸收
            for lk in self.leaks:
                rr = lk.r + p.r
                if (p.x - lk.x) ** 2 + (p.y - lk.y) ** 2 < rr * rr:
                    p.dead = True
                    lk.absorbed += 1
                    self.fx.add_parts(p.x, p.y, DIM, 5, 90, 0.4, 2.0)
                    break
            if p.dead:
                continue
            # 命中玩家
            rr = p.r + PLAYER_R
            if (p.x - px) ** 2 + (p.y - py) ** 2 < rr * rr:
                p.dead = True
                self.damage_player(p.dmg)
                self.fx.add_parts(p.x, p.y, p.color, 10, 180, 0.4, 2.2)
        self.projectiles = [p for p in self.projectiles if not p.dead]

    def update_beams(self, dt, frozen=False):
        for b in self.beams:
            b.t += dt
            if b.t < b.warn:
                continue
            if frozen:
                continue
            b.angle += b.sweep * dt
            # 命中判定
            n = b.node
            if not n.alive:
                b.dead = True
                continue
            ex = n.x + math.cos(b.angle) * b.length
            ey = n.y + math.sin(b.angle) * b.length
            d = seg_point_dist(self.px, self.py, n.x, n.y, ex, ey)
            b.hit_cd -= dt
            if d < b.width * 0.5 + PLAYER_R and b.hit_cd <= 0 and b.t < b.warn + b.active:
                b.hit_cd = 0.5
                self.damage_player(b.dmg)
            if b.t > b.warn + b.active:
                b.dead = True
        self.beams = [b for b in self.beams if not b.dead]

    # ================================================================ Boss
    def enter_boss_phase1(self):
        self.boss_phase = 1
        self.banner = ("GC BOSS", "PHASE 1 // 三根塔架支撑着它", 3.0)
        self.banner_t = 3.0

    def boss_phase_transition(self, core):
        x, y = core.x, core.y
        self.graph.remove_node(core)
        self.boss_phase = 2
        self.boss_intro = 4.0
        self.fx.add_flash(0.7, (255, 255, 255), 2)
        self.fx.add_glitch(1.4)
        self.fx.add_shake(22, 2)
        self.fx.add_hitstop(0.2)
        self.fx.add_ring(x, y, 20, 480, MAGENTA, 1.0, 5)
        self.fx.add_text(PLAY.centerx, PLAY.centery, "REALLOCATE", MAGENTA, 40, 2.2)
        self.banner = ("PHASE 2", "它把自己的核心拆成了两个——并从内部互相引用", 3.2)
        self.banner_t = 3.2
        self.toast("它不会死。它重构了自己。")
        nodes = {}
        for d in BOSS_PHASE2_NODES:
            n = Node(d["kind"], x, y, d["name"], d["hp"])
            n.r = 36
            n.spawn_t = self.time
            n.born_anim = 1.0
            n.timers["atk"] = 2.5
            n.timers["gc"] = 11.0
            n.timers["summon"] = 9.0
            n.data["phase2"] = True
            self.graph.add_node(n)
            nodes[d["id"]] = n
        for a, b, kind in BOSS_PHASE2_EDGES:
            self.graph.add_edge(nodes[a], nodes[b], kind)
        # 从塔架残留拉两条锚定边
        anchors = [n for n in self.graph.nodes if n.alive and n.kind == "PYLON"]
        for i, key in enumerate(("core_a", "core_b")):
            if i < len(anchors):
                self.graph.add_edge(anchors[i], nodes[key], STRONG)
        self.slices = self.max_slices
        self.gc_dirty = True
        self.boss_spawned = True
        sfx("boom")

    def update_boss(self, dt):
        if self.boss_intro > 0:
            self.boss_intro -= dt

    # ================================================================ 清关
    def check_clear(self):
        if self.state != "playing":
            return
        if self.room.get("boss"):
            if self.boss_phase == 2 and self.boss_spawned:
                if not any(n.alive and n.kind == "CORE" for n in self.graph.nodes):
                    self.win()
            return
        if not any(n.alive and n.hostile and not n.hijacked
                   for n in self.graph.nodes):
            self.state = "clear"
            self.end_t = 0.0
            self.run.score += 150 + int(self.hp)
            self.fx.add_flash(0.2, (140, 255, 220), 4)
            self.fx.add_text(PLAY.centerx, PLAY.centery - 30, "ROOM CLEAR",
                             GREEN, 36, 2.0)
            sfx("clear")

    def win(self):
        if self.state == "victory":
            return
        self.state = "victory"
        self.ending = "victory"
        self.end_t = 0.0
        self.run.score += 2000
        self.fx.add_flash(0.6, (255, 255, 255), 1.6)
        self.fx.add_glitch(1.2)
        self.fx.add_shake(18, 1.6)
        sfx("win")

    # ================================================================ 其它
    def alive_hostiles(self):
        return [n for n in self.graph.nodes
                if n.alive and n.hostile and not n.hijacked]

    def load_ratio(self):
        return min(1.0, len([n for n in self.graph.nodes if n.alive]) * 0.055)

    def display_hp(self, n):
        if n.alias:
            return n.alias.hp, n.alias.max
        return n.hp, n.max_hp


META_POS = {
    "spawn": (PLAY.x + PLAY.w * 0.20, ARENA.y + BAND * 0.5),
    "refcount": (PLAY.x + PLAY.w * 0.50, ARENA.y + BAND * 0.5),
    "heap": (PLAY.centerx, ARENA.bottom - BAND * 0.5),
    "boss": (PLAY.x + PLAY.w * 0.80, ARENA.y + BAND * 0.5),
}


_SFX = None


def set_sfx(fn):
    global _SFX
    _SFX = fn


def sfx(name):
    if _SFX:
        _SFX(name)
