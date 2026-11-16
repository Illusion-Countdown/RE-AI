# -*- coding: utf-8 -*-
"""Drag-and-drop regression: deck card -> grid, hand card -> edge."""
import os
import sys

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame

from memory_run.app import App


def down(pos):
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN,
                              {"pos": pos, "button": 1})


def move(pos):
    return pygame.event.Event(pygame.MOUSEMOTION,
                              {"pos": pos, "rel": (0, 0),
                               "buttons": (1, 0, 0)})


def up(pos):
    return pygame.event.Event(pygame.MOUSEBUTTONUP,
                              {"pos": pos, "button": 1})


def main():
    a = App(fullscreen=False, headless=True)
    a.new_run(False)
    a.draw()
    ed = a.editor
    card = next(c for c in ed.run.deck.cards if c.key == "WEAK")
    r = next(r for r, c in ed.tray_rects if c is card)
    cell = (3, 4)
    target = (ed.grid_rect.x + int((cell[1] + 0.5) * ed.cell),
              ed.grid_rect.y + int((cell[0] + 0.5) * ed.cell))
    a.handle_event(down(r.center))
    a.handle_event(move(target))
    a.handle_event(up(target))
    assert card.anchor == cell, (card.anchor, cell)

    a.deck_start()
    for _ in range(150):
        a.update(1 / 60)
    a.draw()
    b = a.battle
    cut = next(c for c in b.hand.slots if c and c.key == "CUT")
    rr = next(r for r, w, c in a.renderer.hand_rects if c is cut)
    e = next(e for e in b.graph.edges
             if e.src.kind == "ROOT" and e.dst.name.startswith("SENTINEL"))
    p = e.points(18)[9]
    a.handle_event(down(rr.center))
    a.handle_event(move(p))
    a.handle_event(up(p))
    assert b.state == "clear", b.state
    print("SINGLE DRAG OK")
    pygame.quit()


if __name__ == "__main__":
    main()
