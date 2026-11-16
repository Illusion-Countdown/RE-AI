# -*- coding: utf-8 -*-
"""无头验证：自动抽牌、CUT 代价、LINK 分摊、WEAK 增伤。"""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame

from memory_run.app import App
from memory_run.cards import CARD_DEFS

pygame.init()
app = App(fullscreen=False, headless=True)
app.new_run(False)
app.start_battle()
b = app.battle

# auto draw
for c in list(b.hand.slots):
    if c:
        b.used.append(c)
b.hand.slots = [None] * 5
b.draw_timer = 0.01
b.update_draw(0.1)
assert any(b.hand.slots), "auto draw failed"
print("auto draw ok", b.hand.slots[0].key)

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

print("MECHANICS OK")
pygame.quit()
