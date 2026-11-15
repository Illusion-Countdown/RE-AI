# -*- coding: utf-8 -*-
"""无头模拟测试：不渲染，直接驱动 Battle 检查核心机制。"""
import os
import sys
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
pygame.init()

from dangle.const import *
from dangle.content import BODIES, ROOMS
from dangle.battle import Battle, Run, AliasPool
from dangle.model import STRONG, WEAK, DANGLING

OK = []
BAD = []


def check(cond, msg):
    if cond:
        OK.append(msg)
        print("  [ok]", msg)
    else:
        BAD.append(msg)
        print("  [FAIL]", msg)


def new_battle(room=0, body=0, mods=()):
    run = Run(BODIES[body])
    for mid in mods:
        from dangle.content import MODULES
        run.add([m for m in MODULES if m["id"] == mid][0])
    b = Battle(run, room)
    b.state = "playing"
    b.intro_t = 0
    b.max_slices = 99
    b.slices = 99
    b.max_heap = 99
    b.heap = 99
    b.gc_timer = 999
    return b, run


def step(b, n=1, dt=1 / 60):
    for _ in range(n):
        b.fx.hitstop = 0.0   # 测试里跳过顿帧，只看逻辑
        b.update(dt, {"mvx": 0, "mvy": 0, "plan": False, "dash": False})


def by_name(b, name):
    for n in b.graph.nodes:
        if n.alive and n.name == name:
            return n
    return None


def alive_names(b):
    return sorted(n.name for n in b.graph.nodes if n.alive and n.kind != "PLAYER")


def edge(b, a, c, kind=STRONG):
    for e in b.graph.edges:
        if e.alive and e.src is a and e.dst is c and e.kind == kind:
            return e
    return None


print("== R01 基础：剪边 -> GC 级联 ==")
b, run = new_battle(0)
step(b, 3)
check(len(b.alive_hostiles()) == 3, "开局 3 个敌人")
s = by_name(b, "SENTINEL.01")
m1 = by_name(b, "MINION.02")
m2 = by_name(b, "MINION.03")
check(b.graph.refcount(m1) == 1, "minion refcount=1")
b.cut_edge(edge(b, s, m1))
step(b, 2)
check(not m1.alive, "剪断 s->m1 后 m1 被擦除")
b.cut_edge(edge(b, s, m2))
step(b, 2)
check(not m2.alive, "剪断 s->m2 后 m2 被擦除")
check(b.graph.refcount(s) == 1, "sentinel 仍有 1 条入边")
scope = by_name(b, "SCOPE")
b.cut_edge(edge(b, scope, s))
step(b, 3)
check(not s.alive, "剪断 scope->s 后 sentinel 被擦除")
check(b.state == "clear", "房间清空")
check(run.score > 0, "获得分数 %d" % run.score)

print("== R02 环：WEAK 破环 ==")
b, run = new_battle(1)
step(b, 2)
a = by_name(b, "CYCLER.A")
c = by_name(b, "CYCLER.B")
check(a is not None and c is not None, "两个 Cycler 存在")
b.cut_edge(edge(b, a, c))
step(b, 1)
check(edge(b, a, c, STRONG) is None, "强边已剪断")
b.timers_dummy = 0
a.timers["rebuild"] = 0.0
step(b, 2)
check(edge(b, a, c, STRONG) is not None, "Cycler 自动重建强边")
b.action_link(a, c, WEAK)
b.cut_edge(edge(b, a, c))
a.timers["rebuild"] = 0.0
step(b, 2)
check(edge(b, a, c, STRONG) is None, "有 WEAK 时强边不再重建")
scope = by_name(b, "SCOPE")
b.cut_edge(edge(b, scope, c))
step(b, 2)
check(not c.alive, "B 引用归零被擦除")
check(a.alive, "A 还剩一条锚定入边")
b.cut_edge(edge(b, scope, a))
step(b, 2)
check(not a.alive, "A 随之级联擦除")
check(b.state == "clear", "环房间清空")

print("== R03 分配器：父节点死亡级联 ==")
b, run = new_battle(2)
step(b, 2)
al = by_name(b, "ALLOCATOR.01")
m1 = by_name(b, "MINION.02")
check(len(b.alive_hostiles()) == 3, "3 个敌人")
scope = by_name(b, "SCOPE")
b.cut_edge(edge(b, scope, al))
step(b, 2)
check(not al.alive, "分配器被擦除")
check(not m1.alive, "子节点被级联擦除")
check(b.state == "clear", "清空")

print("== R04 UAF ==")
b, run = new_battle(3)
step(b, 2)
z = by_name(b, "ZOMBIE.04")
check(z is not None, "僵尸存在")
b.action_link(b.player_node, z, WEAK)
dead = by_name(b, "0xDEAD")
e = None
for ed in b.graph.edges:
    if ed.alive and ed.kind == DANGLING:
        e = ed
check(e is not None, "悬垂边存在")
b.cut_edge(e)
step(b, 2)
check(not z.alive or b.graph.nodes.count(z) == 0, "剪断悬垂边后僵尸消失")
check(len(b.dangling) == 1, "留下 1 个悬垂指针")
b.realloc_queue.clear()
b.realloc_queue.append({"x": z.x, "y": z.y, "t": 0.01})
step(b, 120)
check(run.stats["hijack"] >= 1, "UAF 劫持触发")
check(len(b.dangling) == 0, "悬垂指针被消费")

print("== R05 泄漏 ==")
b, run = new_battle(4)
step(b, 2)
check(len(b.leaks) == 4, "预置 4 个泄漏")
check(abs(b.memory - 4 * 14) < 1, "内存压力 %.1f" % b.memory)
m = by_name(b, "MINION.06")
b.apply_damage(m, 999, leak=True)
step(b, 1)
check(len(b.leaks) == 5, "写入击杀制造泄漏")
check(m.alive is False, "目标死亡")

print("== R07 别名 + 炸弹 ==")
b, run = new_battle(6)
step(b, 2)
bomb = by_name(b, "BOMB.14")
brute = by_name(b, "BRUTE.15")
check(bomb and brute, "炸弹与硬壳存在")
ok = b.action_alias(bomb, brute)
check(ok, "别名成功")
pool = brute.alias
check(pool is not None and pool is bomb.alias, "共享血池")
check(abs(pool.hp - (20 + 220)) < 1, "血池 = 两者之和 %.0f" % pool.hp)
scope = by_name(b, "SCOPE")
b.cut_edge(edge(b, scope, bomb))
step(b, 4)
check(not brute.alive, "炸弹被回收 -> 爆炸 -> 硬壳死亡")
print("   alive:", alive_names(b))

print("== R09 Boss 两阶段 ==")
b, run = new_battle(8)
step(b, 2)
core = by_name(b, "GC.CORE")
check(core is not None, "Boss 核心存在")
for nm in ("PYLON.01", "PYLON.02", "PYLON.03"):
    p = by_name(b, nm)
    b.cut_edge(edge(b, p, core))
step(b, 3)
check(b.boss_phase == 2, "phase 2 触发")
check(by_name(b, "GC.CORE.L") is not None, "核心分裂为两个")
core_a = by_name(b, "GC.CORE.L")
core_b = by_name(b, "GC.CORE.R")
check(core_a and core_b, "双核心存在")
check(edge(b, core_a, core_b) and edge(b, core_b, core_a), "强引用环建立")
# 破环：weak + cut，再剪锚定边
b.action_link(core_a, core_b, WEAK)
b.cut_edge(edge(b, core_a, core_b))
for n in (core_a, core_b):
    for e in list(b.graph.incoming(n, STRONG)):
        b.cut_edge(e)
step(b, 3)
check(not core_a.alive or b.graph.refcount(core_a) == 0, "核心 A 引用归零")
step(b, 5)
check(b.state == "victory" or b.state == "clear", "Boss 被击败 state=%s" % b.state)

print("== CAST NULL ==")
b, run = new_battle(0)
step(b, 2)
s = by_name(b, "SENTINEL.01")
b.action_cast(s, "NULL")
step(b, 1)
check(s.stun > 0, "眩晕生效")
check(len(b.graph.outgoing(s)) == 0, "出边被暂时拔掉")
b.step_null = 0
step(b, 200)
check(s.stun <= 0, "眩晕结束")

print("== 越界 ==")
b, run = new_battle(5)
step(b, 2)
b.px = PLAY.x - 6
b.py = PLAY.centery
step(b, 2)
check(b.oob, "进入越界带")
check(b.enter_oob is not None, "越界回调存在")
names = b.room.get("oob")
check("refcount" in names, "元数据可用")
before = sum(b.graph.refcount(n) for n in b.alive_hostiles())
b.try_metadata("refcount")
step(b, 2)
after = sum(b.graph.refcount(n) for n in b.alive_hostiles())
check(after < before, "引用计数表削弱了敌人 %d -> %d" % (before, after))

print()
print("PASS %d / FAIL %d" % (len(OK), len(BAD)))
for m in BAD:
    print("  FAILED:", m)
sys.exit(1 if BAD else 0)
