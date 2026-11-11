# -*- coding: utf-8 -*-
"""全局常量。改数值先来这里。"""

WIDTH, HEIGHT = 1280, 720
FPS = 60
DT = 1.0 / FPS

# 战场区域（留白给 HUD 和手牌）
ARENA = (60, 60, 960, 530)

# ---------------- 核心数值 ----------------
BASE_ATTACK = 6.0          # 基础单发伤害
BASE_RATE = 2.0            # 基础每秒攻击次数
DRAW_INTERVAL = 4.0        # 抽卡间隔（秒）
HAND_MAX = 5
START_QUOTA = 6            # 名额
CORRUPTION_STEP = 0.10     # 每次 revert 的腐化

# ---------------- 色板 ----------------
BG = (11, 14, 20)
GRID = (22, 27, 34)
PANEL = (22, 27, 34)
LINE = (48, 54, 61)

TEXT = (201, 209, 217)
MUTED = (139, 148, 158)

PLAYER = (88, 166, 255)
ENEMY = (248, 81, 73)
ELITE = (255, 123, 114)
BULLET = (63, 185, 80)
CARD = (210, 153, 34)
PURPLE = (163, 113, 247)

MEM_GOOD = (31, 111, 235)
MEM_BROKEN = (48, 54, 61)
