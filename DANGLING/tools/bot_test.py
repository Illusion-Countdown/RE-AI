# -*- coding: utf-8 -*-
"""自动解题机器人：验证 9 个房间 + Boss 是否可通关，并统计用时与承伤。"""
import os
import sys
import math
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
pygame.init()

from dangle.const import *
from dangle.content import BODIES, MODULES, ROOMS
from dangle.battle import Battle, Run
from dangle.model import STRONG, WEAK, DANGLING

random.seed(1234)


def strong_in(b, n, overrides=None):
    c = 0
    for e in b.graph.edges:
        if not e.alive or e.kind != STRONG or e.dst is not n:
            continue
        if overrides and e in overrides:
            continue
        if overrides:
            # 源节点若会死，这条边也会消失
            pass
        c += 1
    return c


def predict(b, cut_edges):
    """返回会因这批剪断而消失的节点集合。"""
    alive = {n.uid: n for n in b.graph.nodes if n.alive and n.kind != "PLAYER"}
    dead = set()
    for _ in range(12):
        changed = False
        for uid, n in alive.items():
            if uid in dead or n.kind == "ROOT":
                continue
            if not n.collectible or n.immortal:
                continue
            cnt = 0
            for e in b.graph.edges:
                if not e.alive or e.kind != STRONG or e.dst is not n:
                    continue
                if e in cut_edges:
                    continue
                if e.src.uid in dead:
                    continue
                cnt += 1
            if cnt == 0:
                dead.add(uid)
                changed = True
        if not changed:
            break
    return dead


def pick_move(b):
    """返回 ('cut', edge) / ('weak', a, b) / ('alias', a, b) / None"""
    E = [e for e in b.graph.edges if e.alive]
    # 1. 炸弹别名
    all_bombs = [n for n in b.graph.nodes if n.alive and n.kind == "BOMB"]
    new_bombs = [n for n in all_bombs if not n.alias]
    brutes = [n for n in b.graph.nodes if n.alive and n.hostile and n.max_hp >= 150 and not n.alias]
    if new_bombs and brutes and b.heap >= 1:
        return ("alias", new_bombs[0], brutes[0])
    for bm in all_bombs:
        if bm.alias:
            for e in b.graph.incoming(bm, STRONG):
                return ("cut", e)
    # 2. Cycler 破环
    for n in b.graph.nodes:
        if not n.alive or n.kind != "CYCLER" or n.data.get("int"):
            continue
        for m in b.graph.nodes:
            if not m.alive or m is n or m.kind != "CYCLER":
                continue
            if b.graph.between(n, m, STRONG) and not b.graph.between(n, m, WEAK):
                if b.graph.between(m, n, STRONG) or True:
                    return ("weak", n, m)
    # 3. 选能造成最大级联的一刀
    best = None
    best_score = -1
    for e in E:
        if e.kind == DANGLING:
            continue
        if e.src.kind == "BOMB" or e.dst.kind == "BOMB":
            continue
        dead = predict(b, {e})
        score = len(dead) * 10
        # 优先剪到只剩 1 条入边的节点
        if e.dst.uid in dead:
            score += 3
        # 优先让 kids 多的节点失去支撑
        score += len(b.graph.outgoing(e.dst)) * 0.5
        if score > best_score:
            best_score = score
            best = e
    if best is not None:
        return ("cut", best)
    # 4. 悬垂边
    for e in E:
        if e.kind == DANGLING:
            return ("cut", e)
    return None


def run_room(idx, body_idx=0, mods=(), max_t=240, invincible=True, verbose=True):
    run = Run(BODIES[body_idx])
    for mid in mods:
        run.add([m for m in MODULES if m["id"] == mid][0])
    b = Battle(run, idx)
    b.state = "playing"
    b.intro_t = 0
    if invincible:
        b.hp = 99999
        b.max_hp = 99999
    rng = random.Random(7 + idx)
    t = 0.0
    moves = 0
    idle = 0.0
    while t < max_t:
        if b.state in ("clear", "dead", "victory"):
            break
        did = False
        if b.gc_active <= 0 and b.slices >= 1:
            mv = pick_move(b)
            if mv:
                if mv[0] == "cut":
                    if b.cut_edge(mv[1]):
                        moves += 1
                        did = True
                elif mv[0] == "weak":
                    if b.action_link(mv[1], mv[2], WEAK):
                        moves += 1
                        did = True
                elif mv[0] == "alias":
                    if b.action_alias(mv[1], mv[2]):
                        moves += 1
                        did = True
        if not did:
            idle += 1 / 60
        # 玩家做一点随机走位，避免站桩
        ang = rng.uniform(0, 6.283)
        inp = {"mvx": math.cos(ang), "mvy": math.sin(ang), "plan": False, "dash": False}
        b.update(1 / 60, inp)
        t += 1 / 60
        if idle > 6.0:
            break
    return b, t, moves


def main():
    print("=== 自动通关测试 ===")
    total_t = 0
    for i in range(8):
        b, t, moves = run_room(i)
        st = b.state
        dmg = int(b.stats["dmg"])
        print(f"R{i+1:02d} {ROOMS[i]['title']:<16} state={st:<8} time={t:6.1f}s "
              f"moves={moves:3d} dmg={dmg:4d} score={b.run.score}")
        total_t += t
        if st not in ("clear", "victory"):
            print("   !! 未通关，剩余：", [n.name for n in b.alive_hostiles()])
            print("   边：", [(e.src.name, e.dst.name, e.kind) for e in b.graph.edges if e.alive])
    b, t, moves = run_room(8)
    print(f"R09 {ROOMS[8]['title']:<16} state={b.state:<8} time={t:6.1f}s "
          f"moves={moves:3d} dmg={int(b.stats['dmg'])} phase={b.boss_phase}")
    if b.state != "victory":
        print("   !! Boss 未击败，剩余：", [n.name for n in b.alive_hostiles()])
        print("   边：", [(e.src.name, e.dst.name, e.kind) for e in b.graph.edges if e.alive])
    print("总战斗时长 %.1fs" % (total_t + t))

    if "--normal" in sys.argv:
        print()
        print("=== 正常血量（不闪避的机器人） ===")
        for body in (0, 2):
            print("身体:", BODIES[body]["name"])
            for i in range(9):
                b, t, moves = run_room(i, body_idx=body, invincible=False)
                st = b.state
                alive = len(b.alive_hostiles())
                print(f"  R{i+1:02d} state={st:<8} hp={max(0,int(b.hp)):3d}/{b.max_hp} "
                      f"lives={b.lives} dmg={int(b.stats['dmg']):4d} left={alive}")
                if st == "dead":
                    print("    -> 死亡，后续跳过")
                    break


main()
