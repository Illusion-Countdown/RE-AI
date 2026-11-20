# -*- coding: utf-8 -*-
"""引用图的数据模型：节点、边、图。refcount 只数 STRONG 入边。"""
import math
from memory_run.const import *

STRONG, WEAK, DANGLING, ALIAS = "STRONG", "WEAK", "DANGLING", "ALIAS"

_uid = [0]


def next_uid():
    _uid[0] += 1
    return _uid[0]


class Node:
    def __init__(self, kind, x, y, name="", hp=1.0, r=26):
        self.uid = next_uid()
        self.kind = kind
        self.name = name
        self.x = float(x)
        self.y = float(y)
        self.vx = 0.0
        self.vy = 0.0
        self.r = r
        self.hp = float(hp)
        self.max_hp = float(hp)
        self.alive = True
        self.immortal = False       # 无法被 GC 擦除
        self.collectible = True     # 引用归零时被回收
        self.targetable = True      # 可被玩家工具选中
        self.hostile = True         # 需要清空的对象
        self.alias = None           # AliasPool
        self.stun = 0.0
        self.stun_max = 0.0
        self.timers = {}
        self.data = {}
        self.angle = 0.0
        self.spawn_t = 0.0
        self.hit_flash = 0.0
        self.born_anim = 0.0
        self.dead_t = 0.0
        self.hijacked = False
        self.leak_mark = False
        self.beam = 0.0
        self.spin = 0.0

    # -------------------------------------------------- 便捷
    @property
    def pos(self):
        return (self.x, self.y)

    @property
    def color(self):
        if self.hijacked:
            return KIND_COLOR["HIJACK"]
        return KIND_COLOR.get(self.kind, DIM)

    def timer(self, key, default=0.0):
        return self.timers.get(key, default)

    def tick(self, key, dt):
        if key in self.timers:
            self.timers[key] -= dt
            return self.timers[key]
        return 0.0

    def dist(self, other):
        return math.hypot(self.x - other.x, self.y - other.y)

    def __repr__(self):
        return f"<{self.kind} {self.name}#{self.uid}>"


class Edge:
    def __init__(self, src, dst, kind=STRONG, bend=None):
        self.uid = next_uid()
        self.src = src
        self.dst = dst
        self.kind = kind
        self.alive = True
        self.born = 0.0
        self.bend = bend if bend is not None else \
            (0.20 if (src.uid + dst.uid) % 2 == 0 else -0.20)
        self.flow = (src.uid * 0.37 + dst.uid * 0.11) % 1.0
        self.cut_anim = 0.0
        self.warn = 0.0          # 断链预警

    @property
    def color(self):
        if self.kind == STRONG:
            return CYAN
        if self.kind == WEAK:
            return PURPLE
        if self.kind == DANGLING:
            return RED
        return MAGENTA

    def ctrl(self):
        ax, ay = self.src.x, self.src.y
        bx, by = self.dst.x, self.dst.y
        mx, my = (ax + bx) / 2, (ay + by) / 2
        dx, dy = bx - ax, by - ay
        l = math.hypot(dx, dy) or 1.0
        return (mx - dy / l * l * self.bend, my + dx / l * l * self.bend)

    def points(self, n=16):
        p1 = self.ctrl()
        return bezier_pts((self.src.x, self.src.y), p1,
                          (self.dst.x, self.dst.y), n)

    def hit_test(self, px, py, tol=13.0):
        pts = self.points(18)
        for i in range(len(pts) - 1):
            if seg_point_dist(px, py, pts[i][0], pts[i][1],
                              pts[i + 1][0], pts[i + 1][1]) <= tol:
                return True
        return False

    def segment_cross(self, a, b):
        """线段 a-b 是否与这条边相交（剪线用）。"""
        pts = self.points(18)
        for i in range(len(pts) - 1):
            if seg_intersect(a, b, pts[i], pts[i + 1]):
                return True
        return False

    def __repr__(self):
        return f"<{self.kind} {self.src.uid}->{self.dst.uid}>"


class Graph:
    def __init__(self):
        self.nodes = []
        self.edges = []
        self.player = None
        self.time = 0.0

    # -------------------------------------------------- 增删
    def add_node(self, node):
        self.nodes.append(node)
        return node

    def node_by_uid(self, uid):
        for n in self.nodes:
            if n.uid == uid:
                return n
        return None

    def add_edge(self, src, dst, kind=STRONG, bend=None, quiet=False,
                 unique=True):
        if not src.alive or not dst.alive:
            return None
        if unique:
            for e in self.edges:
                if e.alive and e.src is src and e.dst is dst and e.kind == kind:
                    return None      # 同一对节点同一类边只留一条
        e = Edge(src, dst, kind, bend)
        e.born = self.time
        self.edges.append(e)
        return e

    def remove_edge(self, e):
        if e.alive:
            e.alive = False
        return e

    def remove_node(self, n):
        n.alive = False
        n.dead_t = self.time
        for e in self.edges:
            if e.alive and (e.src is n or e.dst is n):
                e.alive = False

    # -------------------------------------------------- 查询
    def incoming(self, n, kind=None, alive_only=True):
        out = []
        for e in self.edges:
            if e.dst is n and (not alive_only or e.alive):
                if kind is None or e.kind == kind:
                    out.append(e)
        return out

    def outgoing(self, n, kind=None, alive_only=True):
        out = []
        for e in self.edges:
            if e.src is n and (not alive_only or e.alive):
                if kind is None or e.kind == kind:
                    out.append(e)
        return out

    def between(self, a, b, kind=None):
        out = []
        for e in self.edges:
            if not e.alive:
                continue
            if e.src is a and e.dst is b:
                if kind is None or e.kind == kind:
                    out.append(e)
        return out

    def refcount(self, n):
        c = 0
        for e in self.edges:
            # 玩家自己的 HOLD 边不把敌人锚在内存里；否则 LINK 会变成自锁
            if e.src.kind == "PLAYER":
                continue
            if e.alive and e.dst is n and e.kind == STRONG:
                c += 1
        return c

    def depth_from_roots(self, target):
        """目标到任意 ROOT 的最短引用距离；不可达返回 99。"""
        roots = [n for n in self.nodes if n.alive and n.kind == "ROOT"]
        if target in roots:
            return 0
        seen = set(roots)
        queue = [(n, 0) for n in roots]
        while queue:
            cur, depth = queue.pop(0)
            for e in self.outgoing(cur):
                if not e.alive or not e.dst.alive:
                    continue
                if e.dst is target:
                    return depth + 1
                if e.dst not in seen:
                    seen.add(e.dst)
                    queue.append((e.dst, depth + 1))
        return 99

    def alive_nodes(self):
        return [n for n in self.nodes if n.alive]

    def hostiles(self):
        return [n for n in self.nodes if n.alive and n.hostile and not n.hijacked]

    def pick_at(self, x, y, pad=10):
        """命中检测，优先半径小的。"""
        best = None
        bd = 1e9
        for n in self.nodes:
            if not n.alive or not n.targetable:
                continue
            d = math.hypot(n.x - x, n.y - y)
            if d <= n.r + pad and d < bd:
                best = n
                bd = d
        return best

    def edge_at(self, x, y, tol=13.0):
        for e in self.edges:
            if e.alive and e.hit_test(x, y, tol):
                return e
        return None
