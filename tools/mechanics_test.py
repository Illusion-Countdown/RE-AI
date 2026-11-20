# -*- coding: utf-8 -*-
"""无头验证：三张手牌、单次回收、CUT 代价、LINK 分摊、WEAK 增伤。"""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame

from memory_run.app import App
from memory_run.cards import CARD_DEFS
from memory_run.content import ROOMS, BOSS_RULES
from memory_run.core.cards import Deck
from memory_run.battle.constants import DEFAULT_HP, WRITE_RANGE

# content consistency
zones = {
    "T1": 0, "T2": 0, "T3": 0, "T4": 0,
    "R01": 1, "R02": 1, "R03": 1, "B1": 1,
    "R04": 2, "R05": 2, "R06": 2, "B2": 2,
    "R07": 3, "R08": 3, "R09": 3, "B3": 3,
    "R10": 4, "R11": 4, "B4": 4,
    "R12": 5, "R13": 5, "B5": 5,
}
assert {r["code"]: r["zone"] for r in ROOMS} == zones
assert not any(r["id"] == "discount" for r in BOSS_RULES)
assert "ZOMBIE" not in DEFAULT_HP
assert not hasattr(Deck(), "register")
print("content consistency ok")

pygame.init()
app = App(fullscreen=False, headless=True)
app.new_run(False)
app.start_battle()
b = app.battle
b.state = "playing"
b.intro_t = 0

# 3-card hand, no overflow; C/Space rotate selection
assert len(b.hand.slots) == 3
assert b.hand.total() == 3
assert not hasattr(b.hand, "overflow")
assert b.selected == 1
assert b.aim and b.aim["card"] is b.hand.slots[1]
first = b.selected
b.cycle_card(1)
assert b.selected == (first + 1) % 3
assert b.aim["card"] is b.hand.slots[b.selected]
b.cycle_card(-1)
assert b.selected == first
print("hand rotation ok")

# first use returns to pile; second use retires for this room
card = b.hand.slots[0]
b.hand.take_slot(0)
b.recycle_after_use(card)
assert card in b.pile, "first use should return card to pile"
b.pile.remove(card)
b.hand.slots[0] = card
b.hand.take_slot(0)
b.recycle_after_use(card)
assert card not in b.pile, "second use must not return card"
assert card in b.used, "second use should retire card"
assert b.card_uses[card.uid] == 2
print("single recycle ok")

# next room recalculates use counts and starts with 3 cards
b.shuffle_room()
assert b.hand.total() == 3
assert b.card_uses == {}
assert b.used == []
print("room reset ok")

# cut cost
cut = next(c for c in b.deck.cards if c.key == "CUT")
assert b.card_work(cut) == 1, b.card_work(cut)
print("cut cost ok")

# weak +35%
n = next(x for x in b.graph.hostiles() if x.alive)
b.do_weak(b.player_node, n)
b.update_status(0.01)
hp = n.hp
b.apply_damage(n, 10)
assert abs((hp - n.hp) - 13.5) < 0.2, hp - n.hp
print("weak amp ok", round(hp - n.hp, 2))

# link: player takes 85%, held edge not counted as refcount
b2 = app.battle
n2 = next(x for x in b2.graph.hostiles() if x.alive)
base_rc = b2.graph.refcount(n2)
b2.do_link(b2.player_node, n2)
assert b2.graph.refcount(n2) == base_rc, "player hold leaked into refcount"
hp0 = b2.hp
b2.damage_player(10)
assert abs((hp0 - b2.hp) - 8.5) < 0.2, hp0 - b2.hp
print("link share ok", round(hp0 - b2.hp, 2))

# ECC can repair a dead cell even if the card itself sits in the grid
b2.state = "playing"
b2.deck.grid.dead.add((0, 0))
from memory_run.cards import Card
ecc = Card("ECC")
b2.hand.slots[0] = ecc
before_dead = len(b2.deck.grid.dead)
assert b2.use_card(ecc, ("slot", 0)), b2.toast_msg
assert len(b2.deck.grid.dead) == before_dead - 1
print("ecc repair ok")

# using a card immediately draws one replacement while the pile has cards
b2.shuffle_room()
b2.hand.slots[0] = Card("COMPRESS")
before_pile = len(b2.pile)
assert b2.use_card(b2.hand.slots[0], ("slot", 0)), b2.toast_msg
assert b2.hand.total() == 3, "use should refill the hand"
assert len(b2.pile) == before_pile - 1, "use should draw exactly one card"
print("use draw ok")

# empty pile: no replacement draw
b2.shuffle_room()
b2.pile = []
empty = Card("COMPRESS")
b2.hand.slots[0] = empty
assert b2.use_card(empty, ("slot", 0)), b2.toast_msg
assert b2.hand.total() == 2, "empty pile must not draw"
assert empty in b2.used
print("empty pile no draw ok")

# the middle card is already aimed: click a target without selecting the card first
b2.hand.slots[1] = Card("TRUNC")
b2.selected = 1
b2.aim_selected()
b2.work_used = 0.0
target = next(n for n in b2.graph.hostiles()
              if n.alive and not n.data.get("boss"))
b2.on_mouse_down((target.x, target.y), 1)
assert target.data.get("cast_stripped") or target.stun > 0
print("default aim click ok")

# self-target card: left click anywhere releases it
b2.state = "playing"
b2.work_used = 0.0
b2.hand.slots[1] = Card("COMPRESS")
b2.selected = 1
b2.aim_selected()
assert b2.on_mouse_down((10, 10), 1), b2.toast_msg
assert b2.compress_t > 0
print("self card click anywhere ok")

# Shift now cycles to the previous card
b2.hand.slots = [Card("CUT"), Card("LINK"), Card("WEAK")]
b2.selected = 1
b2.aim_selected()
b2.on_key(pygame.K_LSHIFT)
assert b2.selected == 0
print("shift previous card ok")

# non-connection card can be released without a target
b2.state = "playing"
b2.work_used = 0.0
cut_empty = Card("CUT")
b2.hand.slots[1] = cut_empty
b2.selected = 1
b2.aim_selected()
before_cards = b2.stats["cards"]
b2.on_mouse_down((10, 10), 1)
b2.on_mouse_up((10, 10), 1)
assert b2.stats["cards"] == before_cards + 1
print("no-target release ok")

# connection card still needs a real object
b2.state = "playing"
b2.work_used = 0.0
link = Card("LINK")
b2.hand.slots[1] = link
b2.selected = 1
b2.aim_selected()
b2.on_mouse_down((10, 10), 1)
assert b2.hand.slots[1] is link
print("connection target required ok")

# WRITE has a shorter range: 380 px misses, 320 px hits
b2.state = "playing"
shoot = next(n for n in b2.graph.hostiles()
             if n.alive and not n.data.get("boss"))
others = [n for n in b2.graph.hostiles() if n.alive and n is not shoot]
saved = [(n, n.x, n.y) for n in others]
for n in others:
    n.x, n.y = 5000, 5000
px, py = b2.player_node.x, b2.player_node.y
shoot.x, shoot.y = px + WRITE_RANGE + 40, py
b2.write_cd = 0
b2.mouse = (shoot.x, shoot.y)
hp = shoot.hp
b2.write_attack()
assert shoot.hp == hp, "WRITE should miss outside its range"
shoot.x = px + WRITE_RANGE - 40
b2.write_cd = 0
b2.mouse = (shoot.x, shoot.y)
b2.write_attack()
assert shoot.hp < hp, "WRITE should hit inside its range"
for n, x, y in saved:
    n.x, n.y = x, y
print("write range ok")

print("MECHANICS OK")
pygame.quit()
