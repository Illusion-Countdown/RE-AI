# -*- coding: utf-8 -*-
"""Render every single-player screen headlessly."""
import os
import sys

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame

from memory_run.app import App
from memory_run.content import TUTORIAL_COUNT


def save(app, name):
    app.draw()
    pygame.image.save(app.screen, os.path.join("screenshots", name))


def main():
    os.makedirs("screenshots", exist_ok=True)
    app = App(fullscreen=False, headless=True)
    app.state = "title"
    save(app, "ui_title.png")
    app.new_run(False)
    save(app, "ui_deck.png")
    app.start_battle()
    for _ in range(140):
        app.update(1 / 60)
    save(app, "ui_battle.png")
    app.state = "pause"
    save(app, "ui_pause.png")
    app.state = "help"
    save(app, "ui_help.png")
    # reward / module / rule
    app.result = {"cleared": True, "perfect": True, "score": 300,
                  "quality": 88, "damage": 0, "new_dead": 0, "shards": 1}
    app.reward_options = app.run.make_card_rewards(3, True)
    app.choice_mode = "card"
    app.state = "reward"
    save(app, "ui_reward.png")
    app.choice_mode = "module"
    app.reward_options = app.run.make_module_rewards()
    app.state = "module"
    save(app, "ui_module.png")
    app.choice_mode = "rule"
    app.reward_options = app.run.make_rule_rewards()
    app.state = "rule"
    save(app, "ui_rule.png")
    # retry
    app.run.refs = 2
    app.death_reason = "render"
    app.state = "retry"
    save(app, "ui_retry.png")
    # tutorial clear / end
    app.run.tutorial = True
    app.run.step = 0
    app.state = "tutorial_clear"
    save(app, "ui_tutorial_clear.png")
    app.run.step = TUTORIAL_COUNT - 1
    app.state = "tutorial_end"
    save(app, "ui_tutorial_end.png")
    # end screens
    app.run.victory = True
    app.run.ended = True
    app.state = "end"
    save(app, "ui_victory.png")
    app.run.victory = False
    save(app, "ui_defeat.png")
    print("SCREENS OK")


if __name__ == "__main__":
    main()
