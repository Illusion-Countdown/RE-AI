# -*- coding: utf-8 -*-
"""无头截图：用于检查界面。"""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
from dangle.app import App
from dangle.battle import Battle
from dangle.content import BODIES, ROOMS
from dangle import screens


def sim(app, frames, inp=None):
    if inp is None:
        inp = {"mvx": 0, "mvy": 0, "plan": False, "dash": False}
    for _ in range(frames):
        app.battle.update(1 / 60, inp)
        app.battle.mouse = app.mouse


def run_shots(args):
    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "preview")
    os.makedirs(out, exist_ok=True)
    app = App(fullscreen=False, headless=True)
    app.t = 3.0
    app.title_bg.t = 6.0

    def save(name):
        path = os.path.join(out, name + ".png")
        pygame.image.save(app.screen, path)
        print("saved", path)
    # 标题
    app.state = "title"
    app.title_bg.t = 8.0
    app.draw()
    save("01_title")

    # 选身体
    app.state = "body"
    app.body_idx = 1
    app.draw()
    save("02_body")

    # 战斗
    for i, (room, frames) in enumerate([(0, 40), (1, 60), (6, 40), (8, 40)]):
        app.body_idx = 0
        app.start_run(0)
        app.run.room_index = room
        app.battle = Battle(app.run, room)
        app.battle.state = "playing"
        app.battle.intro_t = 0.0
        app.state = "play"
        app.fade = 0.0
        app.mouse = (900, 420)
        sim(app, frames)
        app.battle.fx.shake = 0
        app.battle.fx.flash = 0
        app.draw()
        save("03_battle_r%02d" % (room + 1))

    # 拖拽预览
    b = app.battle
    b.tool = 0
    b.drag = {"src": b.player_node, "pos": (900, 500)}
    b.hover_node = b.node_at(900, 500)
    app.draw()
    save("04_drag")
    b.drag = None

    # 悬停
    b.mouse = (b.graph.nodes[1].x, b.graph.nodes[1].y)
    b.hover_node = b.graph.nodes[1]
    app.draw()
    save("05_tooltip")

    # GC 停顿
    b.mouse = (800, 300)
    b.hover_node = None
    b.trigger_gc("test")
    sim(app, 8)
    b.fx.shake = 0
    b.fx.flash = 0
    app.draw()
    save("05b_gc")

    # 开场卡片
    app.start_run(0)
    app.run.room_index = 2
    app.battle = Battle(app.run, 2)
    app.state = "play"
    app.fade = 0.0
    app.battle.intro_t = 1.2
    app.draw()
    save("05c_intro")
    app.battle.intro_t = 0.0
    app.battle.state = "playing"

    # 奖励
    app.run.room_index = 2
    app.make_rewards()
    app.state = "reward"
    app.draw()
    save("06_reward")

    # 暂停
    app.state = "play"
    app.paused = True
    app.draw()
    save("07_pause")
    app.paused = False

    # 结局
    app.state = "gameover"
    app.run.score = 4820
    app.draw()
    save("08_gameover")

    app.run.modules = [m for m in __import__("dangle.content", fromlist=["MODULES"]).MODULES[:5]]
    app.state = "victory"
    app.draw()
    save("09_victory")
