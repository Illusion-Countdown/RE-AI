# -*- coding: utf-8 -*-
"""无头回归：审查修复涉及的机制边界。"""
import os
import sys

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame

from memory_run.app import App
from memory_run.runstate import RunState
from memory_run.ui.battle_factory import create_battle
from memory_run.content import RUN_ROOMS, TUTORIAL_COUNT, GIRLS
from memory_run.core.model import Node, WEAK, STRONG


def make_battle(step, module=None):
    r = RunState(tutorial=False, seed=11, girl_id="deepseek")
    r.step = TUTORIAL_COUNT + step
    r.begin_room()
    if module:
        r.add_module(module)
    b = create_battle(r)
    b.state = "playing"
    b.intro_t = 0
    return b


def main():
    pygame.init()
    app = App(fullscreen=False, headless=True)
    app.new_run(False)
    app.start_battle()
    app.renderer.cam_offset = (10, 20)
    assert app.renderer.screen_to_world((110, 120)) == (100, 100)
    assert app.renderer.world_to_screen((100, 100)) == (110, 120)
    print("camera offset ok")

    # 自机是 AI 娘，不是数据结构；四名角色当前共享基础属性
    for g in GIRLS:
        r = RunState(seed=1, girl_id=g["id"])
        assert r.girl_id == g["id"]
        assert r.girl["name"] == g["name"]
        assert r.max_hp == 106
        assert not hasattr(r, "body")
    print("ai girl select ok")

    # weak_net: weak target stays visible after the weak edge disappears
    b = make_battle(0, "weak_net")
    hostiles = [n for n in b.graph.hostiles() if n.alive]
    a, c = next((x, y) for x in hostiles for y in hostiles
                if x is not y and not b.graph.between(x, y, STRONG))
    assert b.do_weak(a, c)
    b.update_status(1 / 60)
    assert c.data.get("weak_mark")
    weak = next(e for e in b.graph.edges if e.alive and e.kind == WEAK)
    b.graph.remove_edge(weak)
    b.update_status(1 / 60)
    assert c.data.get("weak_mark")
    print("weak_net ok")

    # cow: first alias hit only changes the hit member, not its partner
    b = make_battle(0, "cow")
    a, c = [n for n in b.graph.hostiles() if n.alive][:2]
    assert b.do_alias(a, c, 6.0)
    a0, c0 = a.hp, c.hp
    b.apply_damage(a, 5.0, (100, 200, 220))
    assert abs((a0 - a.hp) - 5.0) < 1e-6
    assert abs(c.hp - c0) < 1e-6
    assert a.alias.cow_used
    print("cow ok")

    # tail_rec: a cascade stops after 3 erased objects
    b = make_battle(0, "tail_rec")
    b.player_node.x, b.player_node.y = 50, 50
    b.hp = b.max_hp = 9999
    added = []
    for i in range(5):
        n = Node("MINION", 900 + i * 30, 500, f"TAIL.{i}", hp=10)
        b.graph.add_node(n)
        added.append(n)
    b.gc_dirty = True
    b.resolve_gc()
    assert sum(n.alive for n in added) == 2, [n.alive for n in added]
    print("tail_rec ok")

    # WEAK++: both selected targets get the mark
    b = make_battle(0)
    hostiles = [n for n in b.graph.hostiles() if n.alive]
    a, c = next((x, y) for x in hostiles for y in hostiles
                if x is not y and not b.graph.between(x, y, STRONG))
    assert b.do_weak(a, c, up=True)
    b.update_status(1 / 60)
    assert a.data.get("weak_mark") and c.data.get("weak_mark")
    print("weak++ ok")

    # overload: all apply_damage sources get +15% when quality < 50
    b = make_battle(0, "overload")
    b.quality_penalty = 60
    assert b.quality() < 50
    n = next(x for x in b.graph.hostiles() if x.alive)
    hp0 = n.hp
    b.apply_damage(n, 10.0, (100, 200, 220))
    assert abs((hp0 - n.hp) - 11.5) < 1e-6, hp0 - n.hp
    print("overload ok")

    # KERNEL is GC-able, matching B3/B5 room text
    idx = next(i for i, r in enumerate(RUN_ROOMS) if r["code"] == "B3")
    b = make_battle(idx)
    ka, kb = b.by_id["ka"], b.by_id["kb"]
    b.player_node.x, b.player_node.y = 50, 50
    b.hp = b.max_hp = 9999
    b.do_weak(ka, kb)
    b.do_weak(kb, ka)
    for e in list(b.graph.edges):
        if e.alive and e.src is b.root and e.dst in (ka, kb):
            b.cut_edge(e)
    b.resolve_gc()
    assert not ka.alive and not kb.alive
    assert b.state == "clear", b.state
    print("kernel gc ok")

    pygame.quit()
    print("MECHANICS EXTRA OK")


if __name__ == "__main__":
    main()
