# -*- coding: utf-8 -*-
"""Play the four tutorial rooms with real card/mouse actions."""
import os
import sys

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame

from memory_run.runstate import RunState
from memory_run.ui.battle_factory import create_battle
from memory_run.cards import Card
from memory_run.model import STRONG


def tick(b, n=12):
    for _ in range(n):
        b.fx.update(1 / 60)
        b.update(1 / 60, {"mouse": (800, 400), "mvx": 0, "mvy": 0})


def edge_point(b, e):
    pts = e.points(18)
    return pts[len(pts) // 2]


def edge_card(b, key, e):
    b.hand.slots[0] = Card(key)
    b.select_slot(0)
    p = edge_point(b, e)
    b.on_mouse_down(p, 1)
    b.on_mouse_up(p, 1)
    tick(b)


def node_card(b, key, n):
    b.hand.slots[0] = Card(key)
    b.select_slot(0)
    b.on_mouse_down((n.x, n.y), 1)
    b.on_mouse_up((n.x, n.y), 1)
    tick(b)


def two_card(b, key, a, c):
    b.hand.slots[0] = Card(key)
    b.select_slot(0)
    b.on_mouse_down((a.x, a.y), 1)
    b.on_mouse_up((a.x, a.y), 1)
    b.on_mouse_down((c.x, c.y), 1)
    b.on_mouse_up((c.x, c.y), 1)
    tick(b)


def make(step):
    r = RunState(tutorial=True, seed=5, body_id="tree")
    r.step = step
    b = create_battle(r)
    b.state = "playing"
    b.intro_t = 0
    return b


def test_t1():
    b = make(0)
    e = next(e for e in b.graph.edges if e.src.kind == "ROOT")
    edge_card(b, "CUT", e)
    assert b.state == "clear", b.state
    print("T1 ok")


def test_t2():
    b = make(1)
    a = next(n for n in b.graph.nodes if n.name == "CYCLER.A")
    c = next(n for n in b.graph.nodes if n.name == "CYCLER.B")
    two_card(b, "WEAK", a, c)
    for target in (c, a):
        e = next(e for e in b.graph.edges
                 if e.src.kind == "ROOT" and e.dst is target)
        edge_card(b, "CUT", e)
        if b.state == "clear":
            break
    assert b.state == "clear", [n.name for n in b.graph.nodes if n.alive]
    print("T2 ok")


def test_t3():
    b = make(2)
    brute = next(n for n in b.graph.nodes if n.name == "BRUTE.04")
    two_card(b, "LINK", b.player_node, brute)
    e = next(e for e in b.graph.edges if e.src.kind == "ROOT" and e.dst is brute)
    edge_card(b, "CUT", e)
    e2 = next(e for e in b.graph.edges
              if e.src is b.player_node and e.dst is brute)
    edge_card(b, "CUT", e2)
    assert b.state == "clear", [n.name for n in b.graph.nodes if n.alive]
    print("T3 ok")


def test_t4():
    b = make(3)
    elite = next(n for n in b.graph.nodes if n.name.startswith("DESTRUCTOR"))
    node_card(b, "TRUNC", elite)
    e = next(e for e in b.graph.edges if e.src.kind == "ROOT" and e.dst is elite)
    edge_card(b, "CUT", e)
    assert b.state == "clear", [n.name for n in b.graph.nodes if n.alive]
    print("T4 ok")


def main():
    pygame.init()
    pygame.display.set_mode((1600, 900))
    test_t1()
    test_t2()
    test_t3()
    test_t4()
    print("TUTORIAL OK")


if __name__ == "__main__":
    main()
