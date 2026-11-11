# -*- coding: utf-8 -*-
"""App：场景切换 + 全局状态。

场景只有四个：menu / map / battle / reward / result。
切换由这里统一管，别的文件不互相 import。
"""
import random

import pygame

import config
from core import actions
from core.state import GameState, card_shape
from data import CARDS
from ui import theme


class App:
    def __init__(self, screen):
        self.screen = screen
        self.running = True
        self.state = None
        self.scene = None
        self.toast_text = ""
        self.toast_timer = 0.0
        self.to_menu()

    # ---------------------------------------------------------------- 场景

    def _set_scene(self, scene):
        self.scene = scene

    def to_menu(self):
        from ui.menu import MenuScreen
        self.state = None
        self._set_scene(MenuScreen(self))

    def start_run(self, character_id):
        self.state = GameState.new(character_id)
        self.goto_map()

    def goto_map(self):
        from ui.mapview import MapScreen
        self._set_scene(MapScreen(self))

    def enter_node(self):
        from ui.battle import BattleScreen
        self._set_scene(BattleScreen(self))

    def goto_reward(self):
        from ui.reward import RewardScreen
        pool = [c for c in CARDS if c not in self.state.memory.placed]
        random.shuffle(pool)
        choices = pool[:3] or [c for c in CARDS][:3]
        self._set_scene(RewardScreen(self, choices))

    def take_card(self, cid):
        cw, ch = card_shape(CARDS[cid])
        if self.state.memory.place(cid, cw, ch):
            self.toast(f"装载 {CARDS[cid]['name']}")
        else:
            self.state.pending_cards += 1
            self.toast("内存放不下，转进手牌")
        self.goto_map()

    def goto_result(self, win):
        from ui.result import ResultScreen
        self.state.win = win
        self.state.over = True
        self._set_scene(ResultScreen(self, win))

    def back_to_menu(self):
        self.to_menu()

    # ---------------------------------------------------------------- 提示

    def toast(self, msg):
        self.toast_text = msg
        self.toast_timer = 2.2

    # ---------------------------------------------------------------- 主循环

    def handle(self, e):
        if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            self.running = False
            return
        self.scene.handle(e)

    def update(self, dt):
        self.scene.update(dt)
        self.toast_timer = max(0.0, self.toast_timer - dt)

    def draw(self):
        self.scene.draw(self.screen)
        self._draw_toast()
        pygame.display.flip()

    def _draw_toast(self):
        if self.toast_timer <= 0:
            return
        from ui import draw
        img = theme.font(18, True).render(self.toast_text, True, theme.TEXT)
        rect = img.get_rect()
        rect.midtop = (config.WIDTH // 2, 74)
        pad = pygame.Rect(rect.x - 16, rect.y - 8, rect.w + 32, rect.h + 16)
        draw.panel(self.screen, pad, (30, 36, 46), theme.ACCENT, 8)
        self.screen.blit(img, rect)
