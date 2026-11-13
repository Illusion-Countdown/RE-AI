"""RUNTIME 4.0 demo：窗口、色板、字体、六边形布局。"""

from __future__ import annotations

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
SHOTS_DIR = BASE_DIR / "docs" / "shots"

WIDTH, HEIGHT = 1280, 720
FPS = 60
CAPTION = "RUNTIME 4.0 // SCHEDULER DEMO"
FULLSCREEN_DEFAULT = True

# 07 / 01 色板
BG = (7, 9, 15)
BG_DEEP = (4, 6, 10)
PANEL = (13, 18, 27)
PANEL_2 = (18, 24, 35)
GRID = (31, 41, 55)
TEXT = (214, 222, 232)
MUTED = (125, 139, 156)
WHITE = (242, 247, 252)
BLACK = (0, 0, 0)
BLUE = (59, 130, 246)
CYAN = (6, 182, 212)
GREEN = (34, 197, 94)
AMBER = (245, 158, 11)
ORANGE = (249, 115, 22)
RED = (239, 68, 68)
PURPLE = (124, 58, 237)
PINK = (236, 72, 153)
YELLOW = (234, 179, 8)

# 棋盘
HEX_SIZE = 39
HEX_ORIGIN = (330, 360)
BOARD_PANEL = (28, 82, 604, 560)
SIDE_PANEL = (652, 82, 596, 560)
LOG_PANEL = (28, 652, 1224, 48)

# 区域色
CORE_COLOR = (124, 58, 237)
MEM_COLOR = (30, 58, 138)
MEM_DARK = (13, 17, 23)
BUS_COLOR = (51, 65, 85)
SECTOR_COLORS = {
    "compile": (245, 158, 11),
    "cache": (14, 165, 233),
    "concurrency": (34, 197, 94),
    "sandbox": (236, 72, 153),
    "inference": (96, 165, 250),
}
AI_COLOR = (37, 99, 235)
ENEMY_COLOR = (239, 68, 68)
ENEMY_AI_COLOR = (168, 85, 247)
CARD_COLOR = (234, 179, 8)

FONT_CANDIDATES = [
    Path(r"C:\Windows\Fonts\msyh.ttc"),
    Path(r"C:\Windows\Fonts\msyhbd.ttc"),
    Path(r"C:\Windows\Fonts\simhei.ttf"),
    Path(r"C:\Windows\Fonts\consola.ttf"),
]


def font_file() -> Path | None:
    for path in FONT_CANDIDATES:
        if path.exists():
            return path
    return None
