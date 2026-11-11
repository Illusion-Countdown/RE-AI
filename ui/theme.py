# -*- coding: utf-8 -*-
"""色板与字体。

改配色只改这里；中文字体一定要显式加载 ttf，否则全是方块。
"""
import os

import pygame

import config

# 直接复用 config 里的色板，避免两处定义打架
BG = config.BG
GRID = config.GRID
PANEL = config.PANEL
LINE = config.LINE
TEXT = config.TEXT
MUTED = config.MUTED

PLAYER = config.PLAYER
ENEMY = config.ENEMY
ELITE = config.ELITE
BULLET = config.BULLET
CARD = config.CARD
PURPLE = config.PURPLE

OK = (63, 185, 80)
WARN = (210, 153, 34)
DANGER = (248, 81, 73)
ACCENT = (88, 166, 255)

_CACHE = {}


def font(size, bold=False):
    key = (size, bold)
    if key in _CACHE:
        return _CACHE[key]

    if not pygame.font.get_init():
        pygame.font.init()

    win = os.environ.get("WINDIR", r"C:\Windows")
    names = ["msyhbd.ttc", "msyh.ttc"] if bold else ["msyh.ttc", "simhei.ttf"]

    f = None
    for name in names:
        path = os.path.join(win, "Fonts", name)
        if os.path.exists(path):
            try:
                f = pygame.font.Font(path, size)
                break
            except Exception:
                continue

    if f is None:
        f = pygame.font.SysFont("microsoftyahei,simhei,arial", size, bold=bold)

    _CACHE[key] = f
    return f
