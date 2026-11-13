"""生成 demo 截图（无窗口）。"""

from __future__ import annotations

import os
import random

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

import settings
from app import App


def save(surface: pygame.Surface, name: str) -> None:
    settings.SHOTS_DIR.mkdir(parents=True, exist_ok=True)
    pygame.image.save(surface, str(settings.SHOTS_DIR / name))
    print("saved", settings.SHOTS_DIR / name)


def deploy_three(scene) -> None:
    for cell in sorted(scene.run.memory):
        if not scene.run.bench:
            break
        scene.selected_bench = 0
        scene._place_selected(cell)


def main() -> None:
    random.seed(20261111)
    app = App()
    app.scene.draw(app.logical)
    save(app.logical, "01_boot.png")

    app.start_game()
    scene = app.scene
    scene.draw(app.logical)
    save(app.logical, "02_map.png")

    scene._choose_node(scene._map_layer().nodes[0])
    scene.draw(app.logical)
    save(app.logical, "03_compile_empty.png")

    deploy_three(scene)
    scene.draw(app.logical)
    save(app.logical, "04_compile_deployed.png")

    scene._run_battle()
    for _ in range(4):
        scene.update(0.05)
    scene.draw(app.logical)
    save(app.logical, "05_battle.png")

    scene._open_shop()
    scene.draw(app.logical)
    save(app.logical, "06_shop.png")
    scene._after_node()
    scene._open_event()
    scene.draw(app.logical)
    save(app.logical, "07_event.png")

    scene.guide.help_visible = True
    scene.draw(app.logical)
    save(app.logical, "09_help.png")

    # Boss 单独开一局
    app.start_game()
    boss_scene = app.scene
    deploy_three(boss_scene)
    boss_scene._choose_node(app.content.layers[3].nodes[0])
    boss_scene._run_battle()
    for _ in range(18):
        boss_scene.update(0.05)
    boss_scene.draw(app.logical)
    save(app.logical, "08_boss.png")
    boss_scene.paused = True
    boss_scene.draw(app.logical)
    save(app.logical, "10_pause.png")
    pygame.quit()


if __name__ == "__main__":
    main()
