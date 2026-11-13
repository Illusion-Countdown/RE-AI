"""无窗口 smoke：数据、棋盘、卡牌、4 层流程、Boss。"""

from __future__ import annotations

import os
import random
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

import settings
from app import App
from core import hex as hx
from core.battle import Battle
from core.models import EnemyInstance


def assert_counts(app: App) -> None:
    assert len(app.content.pieces) == 26, len(app.content.pieces)
    assert len(app.content.cards) == 32, len(app.content.cards)
    assert len(app.content.enemies) == 6, len(app.content.enemies)
    assert len(app.content.languages) == 2, len(app.content.languages)
    assert len(app.content.layers) == 4, len(app.content.layers)


def assert_hex() -> None:
    assert len(hx.cells()) == 37
    assert all(len(hx.sector_cells(i)) == 2 for i in range(6))
    assert len({c for i in range(6) for c in hx.sector_cells(i)}) == 12
    for i in range(6):
        path = hx.port_path(i)
        assert len(path) == 4, (i, path)
        assert path[-1] == (0, 0)
        assert hx.port_index(path[0]) == i
    for cell in hx.cells():
        px, py = hx.hex_to_pixel(cell[0], cell[1], 39, (330, 360))
        assert hx.pixel_to_hex((px, py), 39, (330, 360)) == cell


def deploy_all(scene) -> None:
    run = scene.run
    for _ in range(12):
        if not run.bench:
            break
        placed = False
        for bench_index in range(len(run.bench)):
            for cell in sorted(run.memory):
                before = len(run.pieces)
                scene.selected_bench = bench_index
                scene.selected_piece = run.bench[bench_index]
                scene._place_selected(cell)
                if len(run.pieces) > before:
                    placed = True
                    break
            if placed:
                break
        if not placed:
            break


def battle_to_end(scene, limit: int = 12000) -> None:
    scene._run_battle()
    for _ in range(limit):
        if scene.mode != "battle":
            return
        scene.update(0.05)
    raise AssertionError("battle timeout")


def test_all_cards_and_pieces(app: App) -> None:
    run = app.content.make_run()
    node = app.content.layers[0].nodes[0]
    from core.run import start_node

    start_node(run, node, random.Random(1))
    b = Battle(run, app.content, node)
    b.enemies = [EnemyInstance(app.content.enemies["bug"], path=[(0, 0)], cell=(0, 0))]
    b.enemies[0].hp = b.enemies[0].max_hp = 99999
    from core.models import PieceInstance

    for piece_def in app.content.pieces.values():
        p = PieceInstance(piece_def, cells=[(0, 0)])
        run.pieces = [p]
        b.enemies = [EnemyInstance(app.content.enemies["bug"], path=[(0, 0)], cell=(0, 0))]
        b.enemies[0].hp = 99999
        b.piece_attack(p)
    run.pieces = [PieceInstance(app.content.pieces["greedy"], cells=[(0, 0)])]
    for card in app.content.cards.values():
        run.compute = 99
        if card.kind == "single":
            target = run.pieces[0]
        elif card.kind == "area":
            target = (0, 0)
        else:
            target = None
        b.use_card(card, target)


def main() -> None:
    random.seed(20261111)
    app = App()
    assert_counts(app)
    assert_hex()
    app.scene.update(1 / 60)
    app.scene.draw(app.logical)
    app.start_game()
    scene = app.scene
    test_all_cards_and_pieces(app)
    # 引导 / 手册 / 暂停 UI 冒烟
    scene.guide.toggle_help()
    scene.draw(app.logical)
    scene.guide.help_visible = False
    scene.paused = True
    scene.draw(app.logical)
    scene.paused = False
    # 事件 / 商店界面
    scene._open_event()
    scene._choose_event(scene.event_options[0])
    scene._open_shop()
    scene._after_node()
    # 4 层主线
    for layer in range(4):
        if scene.mode == "result":
            break
        if scene.mode == "map":
            scene._choose_node(scene._map_layer().nodes[0])
        if scene.mode == "compile":
            deploy_all(scene)
            battle_to_end(scene)
        if scene.mode == "draft":
            scene._draft(scene.draft_ids[0])
    assert scene.mode == "result", scene.mode
    assert scene.result_won, scene.result_text
    assert len(scene.run.completed) >= 4
    app.scene.draw(app.logical)
    settings.SHOTS_DIR.mkdir(parents=True, exist_ok=True)
    pygame.image.save(app.logical, str(settings.SHOTS_DIR / "smoke_result.png"))
    pygame.quit()
    print("SMOKE OK")
    print("pieces=26 cards=32 enemies=6 languages=2 layers=4")
    print("completed=", scene.run.completed)
    print("core_hp=", scene.run.core_hp, "tech_debt=", scene.run.tech_debt, "quota=", scene.run.quota)


if __name__ == "__main__":
    main()
