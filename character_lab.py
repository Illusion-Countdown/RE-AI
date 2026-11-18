# -*- coding: utf-8 -*-
"""Character Lab：8 个角色的动画 / 移动 / 状态机验证原型。

设计目标
--------
- 无敌人、无战斗数值，只验证「角色动画 + 移动 + 状态机 + 特效文字」。
- **分辨率策略（按 Lead 2K 审计结论）**：逻辑档 1920×1080，但按窗口物理像素直绘，
  不做「1920 canvas 再整体 transform.scale」。默认窗口 2560×1440，s=4/3：
    · 四个角色每区 480×270 逻辑 → 2K 下 640×360 物理（正好源帧 1:1，永不上采样）；
    · 1080P 窗口下 480×270 物理（源帧 0.75 下采样）。
  所有坐标经 Painter 映射到物理像素；文字按 size*s 物理字号渲染，2K 下清晰。
- 8 个唯一角色（dsh/dsh1 已合并为 dsh），同屏 4 个，顶部角色条翻页查看全部 8 个。
- 每个角色在自己活动区间内左右往返；相邻角色软分离。
- 状态机 idle → move → skill（自动小技能 attack/heal/shield）→ move/idle；
  ULT 由玩家点击角色 / 按 1-4 主动触发，有冷却、不消耗能量，播完回 idle。
- 动作播完自动回 idle，切换带短交叉淡化；不会停在最后一帧、不会硬切。
- 动作读取 ``assets/pets/lab_manifest.json``（pet-assets 任务生成中）。不存在时用
  ``assets/chars/ds``（本地 dsh 资源）fallback；正式 manifest 加载路径始终保留。
- **内存策略**：只加载当前页 4 个可见角色的 idle+move（少量 clip），skill/ult 触发时
  懒加载；LRU 上限约 512MB，翻页时释放隐藏角色引用并按上限淘汰旧 clip。
  禁止 8 角色 × 4 动作全预载。

运行方式（项目根 D:\\Pygame\\RE-AI-AutoChess）
------------------------------------------------
    D:\\Pygame\\.venv\\Scripts\\python.exe character_lab.py                  # 默认全屏（2560×1440 桌面）
    D:\\Pygame\\.venv\\Scripts\\python.exe character_lab.py --windowed       # 2560×1440 窗口
    D:\\Pygame\\.venv\\Scripts\\python.exe character_lab.py --windowed --size 1920x1080
    D:\\Pygame\\.venv\\Scripts\\python.exe character_lab.py --shot shots/character_lab_page1.png --time 4.0
    $env:SDL_VIDEODRIVER='dummy'; D:\\Pygame\\.venv\\Scripts\\python.exe character_lab.py --smoke

本文件独立运行，不 import main.py / battle_demo.py，也不修改 assets。
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pygame


# ---------------------------------------------------------------------------
# 基础常量（全部是 1920×1080 逻辑坐标）
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent
ASSETS = PROJECT_ROOT / "assets"
MANIFEST_PATH = ASSETS / "pets" / "lab_manifest.json"
CHARS_DIR = ASSETS / "chars"
DSH_FALLBACK_DIR = CHARS_DIR / "ds"
ABOUTME_DSH_DIR = PROJECT_ROOT.parent / "aboutme-pets" / "pets" / "dsh" / "spritesheet"
SHOTS_DIR = PROJECT_ROOT / "shots"

W, H = 1920, 1080              # 逻辑坐标（绘制时映射到窗口物理像素）
DEFAULT_WINDOW = (2560, 1440)  # 默认窗口 / 2K 目标
FPS = 60

TOP_H = 196
GROUND_Y = 906
BOTTOM_Y = 934
ZONE_W, ZONE_H = 480, 270      # 每个角色的逻辑绘制区，2K 下 = 源帧 640×360 物理
ZONE_LANES = 4
LANE_CENTER = [ZONE_W // 2 + i * ZONE_W for i in range(4)]
LANE_SLACK = 258               # 活动区间半宽（相邻区间略重叠，用于演示软分离）
EDGE_MARGIN = 40
MIN_GAP = 224                  # 相邻角色软分离最小距离（逻辑）
MOVE_SPEED = 150.0
SKILL_CD = (5.0, 8.5)
ULT_CD = 12.0
SHOT_DEFAULT_TIME = 3.0
SEED = 20261118

SRC_FRAME_W, SRC_FRAME_H = 640, 360   # petit 资源源帧
FOOT_RATIO = 330 / 360                # 源帧内脚底位置（用于让脚落在地面线上）
ZONE_TOP = GROUND_Y - int(ZONE_H * FOOT_RATIO)
PLATE_Y = 528
PLATE_W, PLATE_H = 380, 96

# 动作切片参数（idle/move 播放整段，skill/ult 播一遍）
MAX_FRAMES_PER_CLIP = 120
CLIP_CACHE_CAP_BYTES = 512 * 1024 * 1024   # 512MB，禁止 8×4 全预载
# manifest 里的 skill/ult 是完整 120 帧 @12fps（约 10s）。Lab 为了让状态机/移动可观察，
# 默认把「一遍性动作」按播放速度加速到以下时长（不裁帧、不改尺寸）；--native-timing 可关闭。
ONESHOT_SKILL_SECONDS = 2.4
ONESHOT_ULT_SECONDS = 3.2

# 配色
INK = (7, 11, 17)
BG = (10, 15, 22)
BG2 = (13, 20, 29)
PANEL = (15, 23, 33)
PANEL2 = (19, 29, 41)
LINE = (37, 54, 72)
LINE2 = (52, 74, 96)
TEXT = (221, 236, 246)
MUTED = (120, 143, 162)
DIM = (73, 94, 112)
CYAN = (80, 214, 255)
AMBER = (255, 200, 87)
GREEN = (114, 230, 160)
RED = (255, 92, 105)
PURPLE = (185, 140, 255)
WHITE = (240, 250, 255)
ORANGE = (255, 152, 78)

ROLE_ORDER = ["dsh", "gpt", "claude", "gemini", "qwen", "glm", "grok", "kimi"]
ROLE_DEFAULT_NAMES = {
    "dsh": "蓝毛小女仆", "gpt": "GPT", "claude": "Claude", "gemini": "Gemini",
    "qwen": "Qwen", "glm": "GLM", "grok": "Grok", "kimi": "Kimi",
}
ROLE_DEFAULT_COLORS = {
    "dsh": CYAN, "gpt": GREEN, "claude": AMBER, "gemini": PURPLE,
    "qwen": (96, 160, 255), "glm": (80, 230, 208), "grok": (222, 228, 238),
    "kimi": (255, 140, 190),
}
FALLBACK_SKILL_TYPES = ["heal", "attack", "shield", "heal", "attack", "shield", "heal", "attack"]
FALLBACK_ULT_TYPES = ["summon", "aoe", "buff", "aoe", "summon", "buff", "aoe", "summon"]
ULT_TYPE_LABELS = {"summon": "召唤 SUMMON", "aoe": "范围 AOE", "buff": "强化 BUFF"}
SKILL_TYPE_LABELS = {"attack": "攻击 ATK", "heal": "治疗 HEAL", "shield": "护盾 SHLD"}
SKILL_TYPE_COLORS = {"attack": (255, 140, 96), "heal": GREEN, "shield": CYAN}
SKILL_TYPE_CN = {"attack": "攻击", "heal": "治疗", "shield": "护盾"}
STATE_LABELS = {"idle": "IDLE 待机", "move": "MOVE 移动", "skill": "SKILL 技能", "ult": "ULT 大招"}

# 本地 dsh fallback：(webp 文件名, start, end, step, fps, loop)
FALLBACK_ACTIONS: dict[str, tuple[str, int, int, int, float, bool]] = {
    "idle": ("待机呼吸休闲", 0, 120, 1, 24.0, True),
    "move": ("原地漂浮踏步", 8, 112, 1, 24.0, True),
    "attack": ("原地跳跃抓碎头顶物品", 8, 96, 2, 30.0, False),
    "heal": ("鲸鱼吐泡泡特效", 36, 86, 2, 30.0, False),
    "shield": ("被鼠标拖拽悬空反馈", 24, 112, 2, 30.0, False),
    "ult": ("蓝鲸现世", 24, 104, 2, 40.0, False),
}


# ---------------------------------------------------------------------------
# 字体 / 颜色 / 小工具
# ---------------------------------------------------------------------------
_FONT_CACHE: dict[tuple[int, bool, bool], pygame.font.Font] = {}


def get_font(px_size: int, bold: bool = False, mono: bool = False) -> pygame.font.Font:
    """px_size 是物理像素字号。"""
    key = (max(6, int(px_size)), bool(bold), bool(mono))
    font = _FONT_CACHE.get(key)
    if font is not None:
        return font
    candidates: list[str] = []
    if mono:
        candidates += [r"C:\Windows\Fonts\consola.ttf", r"C:\Windows\Fonts\consolab.ttf"]
    if bold:
        candidates += [r"C:\Windows\Fonts\msyhbd.ttc", r"C:\Windows\Fonts\msyh.ttc"]
    else:
        candidates += [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf"]
    for path in candidates:
        if not os.path.exists(path):
            continue
        try:
            font = pygame.font.Font(path, key[0])
            font.set_bold(bool(bold))
            _FONT_CACHE[key] = font
            return font
        except Exception:
            continue
    try:
        font = pygame.font.SysFont("microsoftyahei", key[0], bold=bool(bold))
    except Exception:
        font = pygame.font.Font(None, key[0])
    _FONT_CACHE[key] = font
    return font


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def blend(c1: tuple[int, int, int], c2: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    t = clamp(t, 0.0, 1.0)
    return (int(lerp(c1[0], c2[0], t)), int(lerp(c1[1], c2[1], t)), int(lerp(c1[2], c2[2], t)))


def parse_color(value: Any, default: tuple[int, int, int]) -> tuple[int, int, int]:
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        try:
            return (int(value[0]), int(value[1]), int(value[2]))
        except (TypeError, ValueError):
            return default
    if isinstance(value, str):
        raw = value.strip()
        if raw.startswith("#"):
            raw = raw[1:]
        if len(raw) == 6:
            try:
                return (int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16))
            except ValueError:
                pass
        named = {"cyan": CYAN, "amber": AMBER, "green": GREEN, "red": RED,
                 "purple": PURPLE, "white": WHITE, "orange": ORANGE}
        if raw.lower() in named:
            return named[raw.lower()]
    return default


def stage_bg_color(y_logical: float) -> tuple[int, int, int]:
    t = clamp((y_logical - TOP_H) / max(1, (BOTTOM_Y - TOP_H)), 0.0, 1.0)
    return blend((8, 12, 18), (16, 26, 38), t)


def tint(color: tuple[int, int, int], y_logical: float, alpha: float) -> tuple[int, int, int]:
    """用局部背景色预混合出「半透明」观感，避免全屏 alpha 层（直接物理像素绘制）。"""
    return blend(stage_bg_color(y_logical), color, clamp(alpha, 0.0, 1.0))


def draw_dashed_rect(painter: "Painter", rect: pygame.Rect, color: tuple[int, int, int],
                     *, dash: int = 12, gap: int = 8, width: int = 1) -> None:
    x, y, w, h = rect
    for start in range(x, x + w, dash + gap):
        end = min(start + dash, x + w)
        painter.line(color, (start, y), (end, y), width)
        painter.line(color, (start, y + h), (end, y + h), width)
    for start in range(y, y + h, dash + gap):
        end = min(start + dash, y + h)
        painter.line(color, (x, start), (x, end), width)
        painter.line(color, (x + w, start), (x + w, end), width)


# ---------------------------------------------------------------------------
# Painter：逻辑坐标 -> 窗口物理像素（不做整幅缩放）
# ---------------------------------------------------------------------------
class Painter:
    def __init__(self, logical_w: int, logical_h: int) -> None:
        self.lw = logical_w
        self.lh = logical_h
        self.target: pygame.Surface | None = None
        self.s = 1.0
        self.ox = 0
        self.oy = 0
        self.view_rect = pygame.Rect(0, 0, logical_w, logical_h)
        self.window_size = (logical_w, logical_h)

    def set_target(self, target: pygame.Surface) -> None:
        self.target = target
        ww, wh = target.get_size()
        self.window_size = (ww, wh)
        scale = min(ww / self.lw, wh / self.lh)
        dw = max(1, int(round(self.lw * scale)))
        dh = max(1, int(round(self.lh * scale)))
        self.s = dw / self.lw
        self.ox = (ww - dw) // 2
        self.oy = (wh - dh) // 2
        self.view_rect = pygame.Rect(self.ox, self.oy, dw, dh)

    @property
    def surface(self) -> pygame.Surface:
        assert self.target is not None
        return self.target

    # -- 坐标映射 --
    def p(self, pos: tuple[float, float]) -> tuple[int, int]:
        return (self.ox + int(round(pos[0] * self.s)), self.oy + int(round(pos[1] * self.s)))

    def r(self, rect: pygame.Rect | tuple[float, float, float, float]) -> pygame.Rect:
        rect = pygame.Rect(rect)
        return pygame.Rect(
            self.ox + int(round(rect.x * self.s)),
            self.oy + int(round(rect.y * self.s)),
            max(1, int(round(rect.w * self.s))),
            max(1, int(round(rect.h * self.s))),
        )

    def w(self, width: float) -> int:
        return max(1, int(round(width * self.s)))

    def logical_rect(self, phys_rect: pygame.Rect) -> pygame.Rect:
        return pygame.Rect(
            int(round((phys_rect.x - self.ox) / self.s)),
            int(round((phys_rect.y - self.oy) / self.s)),
            max(1, int(round(phys_rect.w / self.s))),
            max(1, int(round(phys_rect.h / self.s))),
        )

    # -- 绘制原语（参数均为逻辑坐标 / 逻辑字号）--
    def fill(self, color: tuple[int, int, int], rect: pygame.Rect | tuple) -> None:
        pygame.draw.rect(self.surface, color, self.r(rect))

    def rect(self, color: tuple[int, int, int], rect: pygame.Rect | tuple, *, width: int = 0,
             radius: int = 0) -> None:
        pygame.draw.rect(self.surface, color, self.r(rect), width=self.w(width) if width else 0,
                         border_radius=self.w(radius) if radius else 0)

    def line(self, color: tuple[int, int, int], a: tuple[float, float], b: tuple[float, float],
             width: float = 1) -> None:
        pygame.draw.line(self.surface, color, self.p(a), self.p(b), self.w(width))

    def lines(self, color: tuple[int, int, int], closed: bool,
              points: list[tuple[float, float]], width: float = 1) -> None:
        pygame.draw.lines(self.surface, color, closed, [self.p(pt) for pt in points], self.w(width))

    def circle(self, color: tuple[int, int, int], center: tuple[float, float], radius: float,
               width: float = 0) -> None:
        pygame.draw.circle(self.surface, color, self.p(center), max(1, int(round(radius * self.s))),
                           self.w(width) if width else 0)

    def polygon(self, color: tuple[int, int, int], points: list[tuple[float, float]],
                width: float = 0) -> None:
        pygame.draw.polygon(self.surface, color, [self.p(pt) for pt in points],
                            self.w(width) if width else 0)

    def ellipse(self, color: tuple[int, int, int], rect: pygame.Rect | tuple, *, width: float = 0) -> None:
        pygame.draw.ellipse(self.surface, color, self.r(rect), self.w(width) if width else 0)

    def arc(self, color: tuple[int, int, int], rect: pygame.Rect | tuple, start: float, stop: float,
            width: float = 1) -> None:
        pygame.draw.arc(self.surface, color, self.r(rect), start, stop, self.w(width))

    def blit(self, surface: pygame.Surface, pos: tuple[float, float]) -> None:
        self.surface.blit(surface, self.p(pos))

    def text(self, value: Any, pos: tuple[float, float], color: tuple[int, int, int] = TEXT,
             size: int = 16, *, bold: bool = False, mono: bool = False,
             center: bool = False, right: bool | tuple[float, float] = False,
             alpha: int = 255) -> pygame.Rect:
        px = max(6, int(round(size * self.s)))
        img = get_font(px, bold, mono).render(str(value), True, color)
        if alpha < 255:
            img = img.copy()
            img.set_alpha(alpha)
        rect = img.get_rect()
        anchor = right if isinstance(right, tuple) else pos
        if center:
            rect.center = self.p(pos)
        elif right:
            rect.midright = self.p(anchor)
        else:
            rect.topleft = self.p(pos)
        self.surface.blit(img, rect)
        return self.logical_rect(rect)


# ---------------------------------------------------------------------------
# 资源规格 / 角色定义
# ---------------------------------------------------------------------------
@dataclass
class ClipSpec:
    action: str
    path: Path
    name: str = ""
    columns: int = 8
    rows: int = 15
    frame_w: int = 640
    frame_h: int = 360
    frame_count: int = 120
    fps: float = 24.0
    start: int = 0
    end: int | None = None
    step: int = 1
    loop: bool = False
    source: str = ""

    def frame_indices(self) -> list[int]:
        count = max(1, int(self.frame_count))
        start = clamp(int(self.start), 0, count - 1)
        end = count if self.end is None else clamp(int(self.end), start + 1, count)
        step = max(1, int(self.step))
        indices = list(range(start, end, step))
        if not indices:
            indices = [start]
        if len(indices) > MAX_FRAMES_PER_CLIP:
            stride = int(math.ceil(len(indices) / MAX_FRAMES_PER_CLIP))
            indices = indices[::stride]
        return indices

    def cache_key(self) -> tuple:
        return (
            str(self.path), int(self.start),
            int(self.end if self.end is not None else self.frame_count),
            int(self.step), int(self.columns), int(self.rows),
            int(self.frame_w), int(self.frame_h), int(self.frame_count),
            float(self.fps), bool(self.loop), self.name,
        )


@dataclass
class RoleDef:
    id: str
    name: str
    color: tuple[int, int, int]
    skill_type: str = "attack"
    ult_type: str = "aoe"
    ult_name: str = ""
    clips: dict[str, ClipSpec | None] = field(default_factory=dict)
    from_manifest: bool = False
    source: str = ""
    license: str = ""
    notes: list[str] = field(default_factory=list)

    @property
    def ult_label(self) -> str:
        return self.ult_name or ULT_TYPE_LABELS.get(self.ult_type, self.ult_type)


# ---------------------------------------------------------------------------
# manifest 解析（pet-assets task-8 生成；结构做容错）
# ---------------------------------------------------------------------------
ACTION_ALIASES = {
    "idle": "idle", "stand": "idle", "待机": "idle", "待机呼吸休闲": "idle",
    "move": "move", "walk": "move", "移动": "move", "run": "move", "原地漂浮踏步": "move",
    "skill": "skill", "attack_small": "skill", "小技能": "skill", "action": "skill",
    "ult": "ult", "ultimate": "ult", "大招": "ult", "special": "ult",
}
ID_ALIASES = {
    "dsh": "dsh", "dsh1": "dsh", "dsh-pet": "dsh", "dsh1-pet": "dsh", "ds": "dsh",
    "dsh_pet": "dsh", "dsh1_pet": "dsh",
    "gpt": "gpt", "gpt-pet": "gpt", "gpt_pet": "gpt",
    "claude": "claude", "claude-pet": "claude", "claude_pet": "claude",
    "gemini": "gemini", "gemini-pet": "gemini", "gemini_pet": "gemini",
    "qwen": "qwen", "qwen-pet": "qwen", "qwen_pet": "qwen",
    "glm": "glm", "glm-pet": "glm", "glm_pet": "glm",
    "grok": "grok", "grok-pet": "grok", "grok_pet": "grok",
    "kimi": "kimi", "kimi-pet": "kimi", "kimi_pet": "kimi",
}


def canonical_id(raw: Any) -> str:
    value = str(raw or "").strip().lower().replace(" ", "").replace("_", "-")
    if value in ID_ALIASES:
        return ID_ALIASES[value]
    base = value.split("-pet")[0]
    if base.startswith("dsh1"):
        return "dsh"
    if base in ROLE_ORDER:
        return base
    for key, mapped in ID_ALIASES.items():
        if value.startswith(key):
            return mapped
    return value


def normalize_skill_type(value: Any) -> str | None:
    raw = str(value or "").strip().lower()
    if not raw:
        return None
    if "heal" in raw or "治疗" in raw or "奶" in raw:
        return "heal"
    if "shield" in raw or "盾" in raw or "护" in raw:
        return "shield"
    if "attack" in raw or "攻" in raw or "斩" in raw or "伤" in raw:
        return "attack"
    return None


def normalize_ult_type(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if "summon" in raw or "召唤" in raw or "whale" in raw or "蓝鲸" in raw:
        return "summon"
    if "buff" in raw or "强化" in raw or "buf" in raw or "增" in raw:
        return "buff"
    return "aoe"


def find_first(mapping: dict[str, Any], keys: tuple[str, ...], default: Any = None) -> Any:
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return default


def resolve_asset_path(raw: str | None, extra_dirs: tuple[Path, ...]) -> Path | None:
    if not raw:
        return None
    candidate = Path(str(raw))
    if candidate.is_absolute():
        return candidate
    candidates = [PROJECT_ROOT / candidate, *[d / candidate for d in extra_dirs]]
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


def _read_sheet_meta(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _meta_number(meta: dict[str, Any], keys: tuple[str, ...], default: Any = None) -> Any:
    for key in keys:
        if key in meta and meta[key] is not None:
            return meta[key]
    return default


def parse_clip(value: Any, action: str, role_id: str,
               base_dirs: tuple[Path, ...], warnings: list[str]) -> ClipSpec | None:
    node: dict[str, Any] = {}
    if isinstance(value, str):
        node = {"file": value}
    elif isinstance(value, dict):
        node = dict(value)
        nested = node.get("spritesheet")
        if isinstance(nested, dict):
            merged = dict(nested)
            merged.update({k: v for k, v in node.items() if k != "spritesheet"})
            node = merged
    else:
        return None

    name = str(find_first(node, ("name", "action_name", "title"), action))
    file_raw = find_first(node, ("file", "webp", "path", "src", "source", "sheet", "asset"))
    sources = node.get("sources")
    if not file_raw and isinstance(sources, dict):
        file_raw = sources.get("webp") or sources.get("file")
    meta_path = find_first(node, ("json", "meta", "metafile", "meta_file", "metaFile"))
    meta: dict[str, Any] = {}

    sheet_path: Path | None = None
    if meta_path:
        meta_candidate = resolve_asset_path(str(meta_path), base_dirs)
        if meta_candidate is not None and meta_candidate.exists():
            meta = _read_sheet_meta(meta_candidate)
            if not file_raw and meta_candidate.suffix.lower() == ".json":
                sheet_path = meta_candidate.with_suffix(".webp")
    if file_raw:
        candidate = resolve_asset_path(str(file_raw), base_dirs)
        if candidate is not None and candidate.suffix.lower() == ".json":
            meta = meta or _read_sheet_meta(candidate)
            sheet_path = candidate.with_suffix(".webp")
        else:
            sheet_path = candidate
    if sheet_path is None and file_raw:
        sheet_path = resolve_asset_path(str(file_raw), base_dirs)
    if sheet_path is None:
        guesses = [
            ASSETS / "pets" / role_id / f"{action}.webp",
            ASSETS / "pets" / role_id / f"{name}.webp",
            CHARS_DIR / role_id / f"{name}.webp",
            DSH_FALLBACK_DIR / f"{name}.webp",
        ]
        for guess in guesses:
            if guess.exists():
                sheet_path = guess
                break
    if sheet_path is None or not sheet_path.exists():
        warnings.append(f"{role_id}: 缺少动作资源 {action} ({file_raw or name})")
        return None

    meta = meta or _read_sheet_meta(sheet_path.with_suffix(".json"))
    try:
        frame_count = int(find_first(
            node, ("frame_count", "frameCount", "count", "frames_total"),
            _meta_number(meta, ("FrameCount", "frameCount"), 120),
        ))
    except (TypeError, ValueError):
        frame_count = 120
    raw_frames = node.get("frames")
    if isinstance(raw_frames, (list, tuple)) and raw_frames and isinstance(raw_frames[0], (dict, list)):
        frame_count = len(raw_frames)
    elif isinstance(raw_frames, (int, float)):
        frame_count = int(raw_frames)
    try:
        columns = int(find_first(node, ("columns", "cols"), _meta_number(meta, ("Columns", "columns"), 8)))
        rows = int(find_first(node, ("rows",), _meta_number(
            meta, ("Rows", "rows"), max(1, math.ceil(frame_count / max(1, columns))))))
        frame_w = int(find_first(node, ("frame_width", "frameWidth", "frame_w", "fw"),
                                 _meta_number(meta, ("FrameWidth", "frameWidth"), 640)))
        frame_h = int(find_first(node, ("frame_height", "frameHeight", "frame_h", "fh"),
                                 _meta_number(meta, ("FrameHeight", "frameHeight"), 360)))
    except (TypeError, ValueError):
        columns, rows, frame_w, frame_h = 8, 15, 640, 360
    try:
        fps = float(find_first(node, ("fps", "frame_rate", "frameRate", "sampleFps"),
                               _meta_number(meta, ("SampleFps", "Fps", "fps"), 24.0)))
    except (TypeError, ValueError, OverflowError):
        fps = 24.0
    try:
        start = int(find_first(node, ("start", "frame_start", "frameStart"), 0))
        end_raw = find_first(node, ("end", "frame_end", "frameEnd"), frame_count)
        end = int(end_raw) if end_raw is not None else frame_count
        step = max(1, int(find_first(node, ("step", "frame_step", "frameStep", "stride"), 1)))
    except (TypeError, ValueError):
        start, end, step = 0, frame_count, 1
    loop = bool(find_first(node, ("loop", "looping"), action in ("idle", "move")))
    return ClipSpec(
        action=action, path=sheet_path, name=name, columns=columns, rows=rows,
        frame_w=frame_w, frame_h=frame_h, frame_count=max(1, frame_count),
        fps=max(1.0, fps), start=max(0, start), end=end, step=step, loop=loop,
        source=str(find_first(node, ("source", "origin", "repo"), "")),
    )


def _iter_action_nodes(container: Any) -> list[tuple[str, Any]]:
    result: list[tuple[str, Any]] = []
    if isinstance(container, dict):
        for key, value in container.items():
            result.append((str(key), value))
    elif isinstance(container, (list, tuple)):
        for item in container:
            if not isinstance(item, dict):
                continue
            raw = find_first(item, ("action", "key", "id", "state", "type", "name"), "")
            result.append((str(raw), item))
    return result


def parse_role(raw: dict[str, Any], base_dirs: tuple[Path, ...], warnings: list[str]) -> RoleDef | None:
    raw_id = find_first(raw, ("id", "pet_id", "petId", "key", "slug"))
    if not raw_id:
        return None
    role_id = canonical_id(raw_id)
    if not role_id:
        return None
    name = str(find_first(raw, ("name", "display_name", "displayName", "label"),
                          ROLE_DEFAULT_NAMES.get(role_id, role_id)))
    color = parse_color(find_first(raw, ("color", "colorHex", "accent", "accentColor",
                                         "theme_color", "themeColor")),
                        ROLE_DEFAULT_COLORS.get(role_id, CYAN))
    skill_raw = find_first(raw, ("skill_type", "skillType", "small_skill", "smallSkill"))
    if skill_raw is None:
        alt = raw.get("skill")
        if isinstance(alt, str):
            skill_raw = alt
    default_skill = FALLBACK_SKILL_TYPES[ROLE_ORDER.index(role_id)] if role_id in ROLE_ORDER else "attack"
    skill_type = normalize_skill_type(skill_raw) or default_skill
    ult_raw = find_first(raw, ("ult_type", "ultType"))
    ult_name = ""
    alt_ult = raw.get("ult")
    if isinstance(alt_ult, dict):
        ult_name = str(find_first(alt_ult, ("name", "label", "title"), ""))
        if ult_raw is None:
            ult_raw = find_first(alt_ult, ("type", "kind", "category"))
    elif isinstance(alt_ult, str):
        if ult_raw is None:
            ult_raw = alt_ult
        if not ult_name:
            ult_name = alt_ult
    ult_type = normalize_ult_type(ult_raw)

    clips: dict[str, ClipSpec | None] = {}
    containers = [
        find_first(raw, ("actions", "animations", "clips", "clipsByAction")),
        {k: v for k, v in raw.items()
         if str(k).lower() in ("idle", "move", "skill", "ult", "待机", "移动", "大招")},
    ]
    for container in containers:
        if not container:
            continue
        for action_key, value in _iter_action_nodes(container):
            lowered = action_key.strip().lower()
            canonical = ACTION_ALIASES.get(lowered)
            if canonical is None:
                for alias, mapped in ACTION_ALIASES.items():
                    if alias and alias in lowered:
                        canonical = mapped
                        break
            if canonical is None or canonical in clips:
                continue
            spec = parse_clip(value, canonical, role_id, base_dirs, warnings)
            if spec is not None:
                clips[canonical] = spec

    def _flatten(value: Any) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            return " | ".join(f"{k}: {_flatten(v)}" for k, v in value.items() if v)
        if isinstance(value, (list, tuple)):
            return " | ".join(_flatten(v) for v in value if v)
        return ""

    return RoleDef(
        id=role_id, name=name, color=color, skill_type=skill_type, ult_type=ult_type,
        ult_name=ult_name, clips=clips, from_manifest=True,
        source=_flatten(raw.get("source")), license=_flatten(raw.get("license")),
    )


def load_manifest_roles() -> tuple[list[RoleDef], dict[str, Any]]:
    status: dict[str, Any] = {
        "path": str(MANIFEST_PATH), "ok": False, "from_manifest": False,
        "count": 0, "warnings": [], "error": "",
    }
    if not MANIFEST_PATH.exists():
        status["error"] = "manifest 不存在"
        return [], status
    try:
        with MANIFEST_PATH.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        status["error"] = f"读取失败: {exc}"
        return [], status

    if isinstance(data, dict):
        entries: Any = None
        for key in ("characters", "pets", "roles", "roleList", "entries", "data"):
            value = data.get(key)
            if isinstance(value, (list, tuple)) and value:
                entries = value
                break
            if isinstance(value, dict) and value:
                entries = [dict(v, id=v.get("id", k)) if isinstance(v, dict) else {"id": k, "file": v}
                           for k, v in value.items()]
                break
        if entries is None and data and all(isinstance(v, dict) for v in data.values()):
            entries = [dict(v, id=v.get("id", k)) for k, v in data.items()]
        if entries is None:
            status["error"] = "manifest 中没有 characters/pets 列表"
            return [], status
    elif isinstance(data, list):
        entries = data
    else:
        status["error"] = "manifest 根节点格式不支持"
        return [], status

    warnings: list[str] = status["warnings"]
    base_dirs = (MANIFEST_PATH.parent, ASSETS / "pets", PROJECT_ROOT)
    parsed: dict[str, RoleDef] = {}
    for raw in entries:
        if not isinstance(raw, dict):
            continue
        role = parse_role(raw, base_dirs, warnings)
        if role is None:
            continue
        if role.id in parsed:
            if len(role.clips) > len(parsed[role.id].clips):
                parsed[role.id] = role
            continue
        parsed[role.id] = role

    ordered: list[RoleDef] = []
    for rid in ROLE_ORDER:
        if rid in parsed:
            ordered.append(parsed.pop(rid))
    for rid in sorted(parsed):
        ordered.append(parsed[rid])
    ordered = ordered[:8]
    status["ok"] = bool(ordered)
    status["from_manifest"] = bool(ordered)
    status["count"] = len(ordered)
    if len(ordered) < 8:
        warnings.append(f"manifest 只解析到 {len(ordered)} 个角色，不足的用 dsh fallback 补齐")
    return ordered, status


# ---------------------------------------------------------------------------
# fallback（本地 dsh 资源）
# ---------------------------------------------------------------------------
def dsh_fallback_path(name: str) -> Path | None:
    for base in (DSH_FALLBACK_DIR, ABOUTME_DSH_DIR):
        candidate = base / f"{name}.webp"
        if candidate.exists():
            return candidate
    return None


def fallback_clip(action: str, *, skill_type: str | None = None) -> ClipSpec | None:
    lookup = action
    if action == "skill":
        lookup = skill_type if skill_type in ("attack", "heal", "shield") else "attack"
    entry = FALLBACK_ACTIONS.get(lookup)
    if entry is None:
        return None
    name, start, end, step, fps, loop = entry
    path = dsh_fallback_path(name)
    if path is None:
        return None
    return ClipSpec(
        action=action, path=path, name=name, columns=8, rows=15,
        frame_w=640, frame_h=360, frame_count=120, fps=fps,
        start=start, end=end, step=step, loop=loop, source="local dsh fallback",
    )


def build_fallback_roles() -> tuple[list[RoleDef], dict[str, Any]]:
    roles: list[RoleDef] = []
    status = {
        "path": str(MANIFEST_PATH), "ok": False, "from_manifest": False,
        "count": len(ROLE_ORDER),
        "warnings": ["lab_manifest.json 尚未生成 → 使用 assets/chars/ds 本地 dsh 资源 fallback"],
        "error": "manifest 不存在",
    }
    for index, role_id in enumerate(ROLE_ORDER):
        skill_type = FALLBACK_SKILL_TYPES[index]
        roles.append(RoleDef(
            id=role_id, name=ROLE_DEFAULT_NAMES[role_id],
            color=ROLE_DEFAULT_COLORS[role_id], skill_type=skill_type,
            ult_type=FALLBACK_ULT_TYPES[index], ult_name="蓝鲸现世",
            clips={
                "idle": fallback_clip("idle"), "move": fallback_clip("move"),
                "skill": fallback_clip("skill", skill_type=skill_type),
                "ult": fallback_clip("ult"),
            },
            from_manifest=False, source="assets/chars/ds (local dsh)",
            license="non-commercial, attribution required (aboutme-pets)",
        ))
    return roles, status


def fill_missing_roles(roles: list[RoleDef], status: dict[str, Any]) -> list[RoleDef]:
    fallback_roles, _ = build_fallback_roles()
    by_id = {role.id: role for role in roles}
    result: list[RoleDef] = []
    for index, role_id in enumerate(ROLE_ORDER):
        fallback = fallback_roles[index]
        role = by_id.get(role_id)
        if role is None:
            role = fallback
            status["warnings"].append(f"manifest 缺少 {role_id}，用 fallback 占位")
        else:
            for action in ("idle", "move", "skill", "ult"):
                if role.clips.get(action) is None:
                    role.clips[action] = fallback.clips.get(action)
                    status["warnings"].append(f"{role_id}.{action} 缺失，用 dsh fallback 补")
        result.append(role)
    return result


def load_roles() -> tuple[list[RoleDef], dict[str, Any]]:
    roles, status = load_manifest_roles()
    if roles:
        roles = fill_missing_roles(roles, status)
    else:
        roles, status = build_fallback_roles()
    return roles, status


# ---------------------------------------------------------------------------
# 动画切片（按窗口物理像素预缩放，永不上采样）
# ---------------------------------------------------------------------------
@dataclass
class Clip:
    key: tuple
    action: str
    name: str
    fps: float
    loop: bool
    frames: list[pygame.Surface]     # 已经是物理像素尺寸
    bboxes: list[pygame.Rect]        # 物理像素，帧内 alpha bbox
    pivot: tuple[int, int]           # 物理像素脚底锚点
    size: tuple[int, int]            # 物理尺寸
    bytes_est: int
    path: str

    @property
    def duration(self) -> float:
        return len(self.frames) / max(1.0, self.fps)

    def frame_at(self, frame: float) -> int:
        if not self.frames:
            return 0
        return int(clamp(frame, 0, len(self.frames) - 1))


def build_placeholder_clip(action: str, name: str, color: tuple[int, int, int],
                           *, loop: bool, scale: float = 1.0) -> Clip:
    count = 12
    fw = max(60, int(round(220 * max(scale, 0.4))))
    fh = max(80, int(round(280 * max(scale, 0.4))))
    frames: list[pygame.Surface] = []
    bboxes: list[pygame.Rect] = []
    for index in range(count):
        surface = pygame.Surface((fw, fh), pygame.SRCALPHA)
        bob = int(6 * math.sin(index / count * math.tau))
        body = pygame.Rect(int(fw * 0.19), int(fh * 0.24) + bob, int(fw * 0.62), int(fh * 0.67))
        pygame.draw.ellipse(surface, (*color, 210), body)
        pygame.draw.ellipse(surface, (12, 18, 26, 230),
                            (int(fw * 0.30), int(fh * 0.14) + bob, int(fw * 0.40), int(fh * 0.28)))
        pygame.draw.circle(surface, (*color, 240), (fw // 2, int(fh * 0.16) + bob), max(8, fw // 12))
        letter = name[:1] if name else action[:1].upper()
        img = get_font(max(10, int(fh * 0.16)), True).render(letter, True, (12, 18, 26))
        surface.blit(img, img.get_rect(center=(fw // 2, int(fh * 0.58))))
        frames.append(surface)
        bboxes.append(surface.get_bounding_rect())
    return Clip(
        key=("placeholder", action, name, color, round(scale, 4)),
        action=action, name=f"{name} (placeholder)", fps=8.0, loop=loop,
        frames=frames, bboxes=bboxes, pivot=(fw // 2, fh - max(2, int(fh * 0.05))),
        size=(fw, fh), bytes_est=fw * fh * 4 * count, path="<placeholder>",
    )


class ClipLoadError(Exception):
    pass


def build_clip(spec: ClipSpec, scale: float, key: tuple) -> Clip:
    """切帧：裁掉透明边、按 scale 缩放到物理像素（scale 永远 ≤ 1，不上采样）。"""
    if not spec.path.exists():
        raise ClipLoadError(f"文件不存在: {spec.path}")
    try:
        sheet = pygame.image.load(str(spec.path)).convert_alpha()
    except pygame.error as exc:
        raise ClipLoadError(f"无法加载 {spec.path.name}: {exc}") from exc
    sheet_w, sheet_h = sheet.get_size()
    frame_w = max(1, int(spec.frame_w))
    frame_h = max(1, int(spec.frame_h))
    columns = max(1, int(spec.columns))
    rows = max(1, int(spec.rows))
    if columns * frame_w > sheet_w:
        columns = max(1, sheet_w // frame_w)
    if rows * frame_h > sheet_h:
        rows = max(1, sheet_h // frame_h)
    max_cells = columns * rows
    frame_count = min(max(1, int(spec.frame_count)), max_cells)
    indices = [i for i in spec.frame_indices() if i < frame_count] or [0]

    def frame_rect(index: int) -> pygame.Rect:
        return pygame.Rect((index % columns) * frame_w, (index // columns) * frame_h, frame_w, frame_h)

    sample_step = max(1, len(indices) // 24)
    samples = indices[::sample_step]
    if indices[-1] not in samples:
        samples.append(indices[-1])
    union: pygame.Rect | None = None
    heights: list[int] = []
    lowest: tuple[int, pygame.Rect] | None = None
    for index in samples:
        try:
            frame = sheet.subsurface(frame_rect(index))
        except ValueError:
            continue
        bbox = frame.get_bounding_rect()
        if bbox.width <= 0 or bbox.height <= 0:
            continue
        union = bbox.copy() if union is None else union.union(bbox)
        heights.append(bbox.height)
        if lowest is None or bbox.bottom > lowest[1].bottom:
            lowest = (index, bbox.copy())
    if union is None or not heights:
        union = pygame.Rect(0, 0, frame_w, frame_h)
        heights = [frame_h]
        lowest = (0, union.copy())
    heights.sort()
    body_height = max(40, heights[len(heights) // 2])
    crop = union.inflate(28, 28).clip(pygame.Rect(0, 0, frame_w, frame_h))
    if crop.width <= 4 or crop.height <= 4:
        crop = pygame.Rect(0, 0, frame_w, frame_h)

    # 关键：物理尺寸 = 源帧像素 * scale，绝不放大
    scale = clamp(scale, 0.05, 1.0)
    out_w = max(8, int(round(crop.width * scale)))
    out_h = max(8, int(round(crop.height * scale)))
    pivot_x = int(round((lowest[1].centerx - crop.x) * scale))
    pivot_y = int(round((lowest[1].bottom - crop.y) * scale))
    pivot_x = int(clamp(pivot_x, 0, out_w - 1))
    pivot_y = int(clamp(pivot_y, 0, out_h - 1))

    frames: list[pygame.Surface] = []
    bboxes: list[pygame.Rect] = []
    for index in indices:
        try:
            raw_frame = sheet.subsurface(frame_rect(index)).subsurface(crop)
        except ValueError:
            raw_frame = pygame.Surface((crop.width, crop.height), pygame.SRCALPHA)
        if out_w == crop.width and out_h == crop.height:
            scaled = raw_frame.copy()
        else:
            # 插画帧下采样：smoothscale；任何情况下都不做上采样（scale 上限 1:1）
            scaled = pygame.transform.smoothscale(raw_frame, (out_w, out_h))
        frames.append(scaled)
        bbox = scaled.get_bounding_rect()
        bboxes.append(bbox if bbox.width > 0 and bbox.height > 0 else pygame.Rect(0, 0, out_w, out_h))
    del sheet
    return Clip(
        key=key, action=spec.action, name=spec.name or spec.action,
        fps=max(1.0, spec.fps), loop=spec.loop, frames=frames, bboxes=bboxes,
        pivot=(pivot_x, pivot_y), size=(out_w, out_h),
        bytes_est=out_w * out_h * 4 * len(frames), path=str(spec.path),
    )


class ClipStore:
    """懒加载 + LRU 缓存：只保留可见角色的当前动作 / 少量 clip，上限 512MB。"""

    def __init__(self, cap_bytes: int = CLIP_CACHE_CAP_BYTES) -> None:
        self.cap_bytes = cap_bytes
        self.cache: OrderedDict[tuple, Clip] = OrderedDict()
        self.bytes_total = 0
        self.placeholders: dict[tuple, Clip] = {}
        self.loads = 0
        self.load_ms = 0.0
        self.evictions = 0

    def get(self, spec: ClipSpec | None, scale: float, warnings: list[str],
            *, context: str = "", protect: set[tuple] | None = None) -> Clip | None:
        if spec is None:
            return None
        key = (spec.cache_key(), round(scale, 4))
        clip = self.cache.get(key)
        if clip is not None:
            self.cache.move_to_end(key)
            return clip
        started = time.perf_counter()
        try:
            clip = build_clip(spec, scale, key)
        except ClipLoadError as exc:
            warnings.append(f"{context}: {exc}")
            return None
        except Exception as exc:  # noqa: BLE001 - 资源格式异常不能崩掉 lab
            warnings.append(f"{context}: 切片失败 {exc}")
            return None
        self.cache[key] = clip
        self.bytes_total += clip.bytes_est
        self.loads += 1
        self.load_ms += (time.perf_counter() - started) * 1000
        print(f"[clip] {spec.action:5s} {spec.name[:17]:17s} frames={len(clip.frames):3d} "
              f"phys={clip.size[0]}x{clip.size[1]} fps={clip.fps:.1f} "
              f"cache={self.bytes_total / 1e6:6.1f}MB loads={self.loads}")
        self._evict(protect or set())
        return clip

    def _evict(self, protect: set[tuple]) -> None:
        while self.bytes_total > self.cap_bytes and len(self.cache) > 1:
            evicted = False
            for key in list(self.cache.keys()):
                if key in protect:
                    continue
                clip = self.cache.pop(key)
                self.bytes_total -= clip.bytes_est
                self.evictions += 1
                evicted = True
                break
            if not evicted:
                break

    def placeholder(self, action: str, name: str, color: tuple[int, int, int],
                    loop: bool, scale: float) -> Clip:
        key = (action, name, color, loop, round(scale, 4))
        clip = self.placeholders.get(key)
        if clip is None:
            clip = build_placeholder_clip(action, name, color, loop=loop, scale=scale)
            self.placeholders[key] = clip
        return clip

    def clear(self) -> None:
        """翻页时清空旧页 clip（可见角色已释放引用），把内存还给新页懒加载。"""
        self.cache.clear()
        self.bytes_total = 0


# ---------------------------------------------------------------------------
# 动画播放器（交叉淡化 / 循环 / 单次）
# ---------------------------------------------------------------------------
class Animator:
    def __init__(self) -> None:
        self.clip: Clip | None = None
        self.frame = 0.0
        self.loop = True
        self.done = False
        self.fade = 0.0
        self.fade_total = 0.0
        self.speed = 1.0
        self.prev_surface: pygame.Surface | None = None
        self.prev_pivot: tuple[int, int] | None = None
        self.prev_clip: Clip | None = None
        self.prev_facing = 1
        self.facing = 1

    def release(self) -> None:
        self.clip = None
        self.prev_surface = None
        self.prev_pivot = None
        self.prev_clip = None
        self.fade = 0.0
        self.frame = 0.0
        self.done = False
        self.speed = 1.0

    def play(self, clip: Clip | None, *, loop: bool, facing: int, fade: float = 0.14,
             speed: float = 1.0) -> None:
        if clip is None:
            return
        if self.clip is clip and self.loop == loop and loop and not self.done:
            self.facing = facing
            self.speed = max(0.1, speed)
            return
        if self.clip is not None and self.clip.frames:
            self.prev_surface = self.current_surface()
            self.prev_pivot = self.clip.pivot
            self.prev_clip = self.clip
            self.prev_facing = self.facing
            self.fade = max(0.0, fade)
            self.fade_total = max(0.001, fade)
        else:
            self.prev_surface = None
            self.prev_pivot = None
            self.prev_clip = None
            self.fade = 0.0
        self.clip = clip
        self.frame = 0.0
        self.loop = loop
        self.done = False
        self.facing = facing
        self.speed = max(0.1, speed)

    def update(self, dt: float) -> None:
        if self.fade > 0:
            self.fade = max(0.0, self.fade - dt)
            if self.fade <= 0:
                self.prev_surface = None
                self.prev_pivot = None
                self.prev_clip = None
        if self.clip is None or not self.clip.frames:
            return
        self.frame += dt * self.clip.fps * self.speed
        count = len(self.clip.frames)
        if self.loop:
            if self.frame >= count:
                self.frame %= count
        elif self.frame >= count:
            self.frame = count - 1
            self.done = True

    def current_surface(self) -> pygame.Surface | None:
        if self.clip is None or not self.clip.frames:
            return None
        return self.clip.frames[self.clip.frame_at(self.frame)]

    def current_bbox(self) -> pygame.Rect | None:
        if self.clip is None or not self.clip.bboxes:
            return None
        return self.clip.bboxes[self.clip.frame_at(self.frame)]

    def current_name(self) -> str:
        return self.clip.name if self.clip else "-"

    def current_frame_index(self) -> tuple[int, int]:
        if self.clip is None or not self.clip.frames:
            return (0, 0)
        return (self.clip.frame_at(self.frame) + 1, len(self.clip.frames))

    def progress(self) -> float:
        if self.clip is None or not self.clip.frames:
            return 0.0
        return clamp(self.frame / len(self.clip.frames), 0.0, 1.0)


# ---------------------------------------------------------------------------
# 特效
# ---------------------------------------------------------------------------
@dataclass
class SkillFx:
    kind: str
    x: float
    y: float
    color: tuple[int, int, int]
    facing: int = 1
    name: str = ""
    t: float = 0.0
    life: float = 0.9


@dataclass
class UltFx:
    kind: str
    x: float
    y: float
    color: tuple[int, int, int]
    name: str = ""
    t: float = 0.0
    life: float = 1.35


@dataclass
class FloatText:
    x: float
    y: float
    message: str
    color: tuple[int, int, int]
    t: float = 0.0
    life: float = 1.1
    size: int = 20
    vy: float = 46.0


# ---------------------------------------------------------------------------
# 角色运行时
# ---------------------------------------------------------------------------
class RoleRuntime:
    def __init__(self, role: RoleDef, index: int, lane: int, rng: random.Random) -> None:
        self.role = role
        self.index = index
        self.lane = lane
        self.rng = rng
        self.anim = Animator()
        self.x = float(LANE_CENTER[lane])
        self.ground_y = float(GROUND_Y)
        self.facing = 1
        self.state = "idle"
        self.state_time = 0.0
        self.idle_timer = rng.uniform(0.6, 1.8)
        self.target_x = self.x
        self.move_speed = MOVE_SPEED * rng.uniform(0.88, 1.10)
        self.skill_timer = rng.uniform(2.0, 4.5)
        self.ult_cd = 0.0
        self.skill_type_override: str | None = None
        self.skill_cycle = 0
        self.action_speed = 1.0
        self.flash = 0.0
        self.hit_rect = pygame.Rect(0, 0, 0, 0)
        self.char_top = float(ZONE_TOP)
        self.char_bottom = float(GROUND_Y)
        self.visible = False

    @property
    def zone(self) -> tuple[float, float]:
        center = LANE_CENTER[self.lane]
        low = max(EDGE_MARGIN, center - LANE_SLACK)
        high = min(W - EDGE_MARGIN, center + LANE_SLACK)
        return (low, high)

    def reset(self) -> None:
        self.state = "idle"
        self.state_time = 0.0
        self.idle_timer = self.rng.uniform(0.5, 1.6)
        low, high = self.zone
        self.x = self.rng.uniform(low + 40, high - 40)
        self.target_x = self.x
        self.facing = 1 if self.rng.random() < 0.5 else -1
        self.ult_cd = 0.0
        self.skill_timer = self.rng.uniform(1.6, 3.5)
        self.flash = 0.0

    def reset_page_position(self) -> None:
        low, high = self.zone
        self.x = self.rng.uniform(low + 60, high - 60)
        self.target_x = self.x
        self.state = "idle"
        self.idle_timer = self.rng.uniform(0.4, 1.2)
        self.facing = 1 if self.rng.random() < 0.5 else -1


# ---------------------------------------------------------------------------
# Character Lab 主体
# ---------------------------------------------------------------------------
class CharacterLab:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.shot_path: Path | None = Path(args.shot) if args.shot else None
        self.shot_time = float(args.time)
        self.smoke_mode = bool(args.smoke)
        self.start_page = int(clamp(int(args.page), 1, 2)) - 1
        self.seed = int(args.seed)
        self.force_skills = bool(args.force_skills)
        self.force_ults = bool(args.force_ults)
        self.debug = not bool(args.no_debug)
        self.native_timing = bool(getattr(args, "native_timing", False))
        self.windowed = bool(args.windowed) or self.shot_path is not None or self.smoke_mode
        self.size = self._parse_size(args.size)

        pygame.display.init()
        pygame.font.init()
        self.window = self._create_window()
        self.view = Painter(W, H)
        self.view.set_target(self.window)
        self.clock = pygame.time.Clock()

        self.roles, self.manifest_status = load_roles()
        self.store = ClipStore()
        self.warnings: list[str] = list(self.manifest_status.get("warnings", []))
        self.rng = random.Random(self.seed)
        self.time = 0.0
        self.fps_value = 60.0
        self.page = self.start_page
        self.skill_mode = "role"
        self.paused = False
        self.running = True
        self.transition_surface: pygame.Surface | None = None
        self.transition_t = 0.0
        self.flash = 0.0
        self.skill_fx: list[SkillFx] = []
        self.ult_fx: list[UltFx] = []
        self.texts: list[FloatText] = []
        self.log_lines: list[tuple[float, str, tuple[int, int, int]]] = []
        self.hover_role: RoleRuntime | None = None
        self.roster_rects: list[tuple[pygame.Rect, int]] = []
        self.page_buttons: dict[str, pygame.Rect] = {}
        self.mouse_logical: tuple[int, int] = (-100, -100)
        self.frame_index = 0

        self.runtimes: dict[str, RoleRuntime] = {}
        for index, role in enumerate(self.roles):
            self.runtimes[role.id] = RoleRuntime(
                role, index, index % 4, random.Random(self.seed + index * 7919))
        self.visible_ids: list[str] = []
        self._activate_page(self.page, initial=True)
        self._log("lab ready: 8 roles, no enemies, no combat stats", CYAN)
        print(f"[view] window={self.window.get_size()} logical={W}x{H} s={self.view.s:.3f} "
              f"| {self._sprite_mode_text()} | "
              f"(source frame {SRC_FRAME_W}x{SRC_FRAME_H}, 2K target 640x360 physical)")
        if self.upscale_capped:
            print("[warn] 窗口物理尺寸超过 2K 目标：精灵按源帧 1:1 封顶绘制，不上采样（降级）")
        self._report_manifest()

    def _report_manifest(self) -> None:
        status = self.manifest_status
        if status.get("from_manifest"):
            roles_desc = " ".join(f"{role.id}「{role.name}」" for role in self.roles)
            print(f"[manifest] OK · {status['count']}/8 roles from {MANIFEST_PATH}")
            print(f"[manifest] loaded: {roles_desc}")
            missing = [w for w in self.warnings if "缺少动作资源" in w]
            fallback_roles = [role.id for role in self.roles if not role.from_manifest]
            if fallback_roles:
                print(f"[manifest] ⚠ 以下角色未从 manifest 解析成功、仍在用 dsh fallback：{fallback_roles}"
                      "（请同步 Lead）")
            if missing:
                print("[manifest] ⚠ 以下角色动作文件缺失，将逐动作使用 dsh fallback（请同步 Lead）：")
                for warning in missing:
                    print(f"   - {warning}")
            else:
                actions = sum(len([a for a in role.clips if role.clips[a] is not None])
                              for role in self.roles)
                print(f"[manifest] actions complete: {actions}/32 (idle/move/skill/ult × 8 roles)")
        else:
            print(f"[manifest] MISSING ({status.get('error')}) → local dsh fallback; "
                  f"lab_manifest.json 落盘后重启自动切换")
        if not self.native_timing:
            print(f"[pacing] one-shot action speed-up: skill ≤{ONESHOT_SKILL_SECONDS}s, "
                  f"ult ≤{ONESHOT_ULT_SECONDS}s（--native-timing 关闭）")
        else:
            print("[pacing] one-shot action uses native manifest timing (≈10s each)")

    # -- 初始化 / 窗口 ---------------------------------------------------
    @staticmethod
    def _parse_size(value: str | None) -> tuple[int, int] | None:
        if not value:
            return None
        raw = str(value).lower().replace("×", "x").replace(" ", "")
        try:
            w_text, h_text = raw.split("x", 1)
            return (max(640, int(w_text)), max(360, int(h_text)))
        except (ValueError, TypeError):
            print(f"[warn] --size 格式应为 WxH，收到 {value!r}，忽略")
            return None

    def _create_window(self) -> pygame.Surface:
        if self.smoke_mode:
            size = self.size or DEFAULT_WINDOW
            return pygame.display.set_mode(size)
        if self.shot_path is not None:
            size = self.size or DEFAULT_WINDOW
            return pygame.display.set_mode(size)
        if self.windowed or self.size:
            size = self.size or DEFAULT_WINDOW
            try:
                desktop = pygame.display.get_desktop_sizes()[0]
                size = (min(size[0], desktop[0]), min(size[1], desktop[1]))
            except (pygame.error, IndexError):
                pass
            return pygame.display.set_mode(size)
        try:
            return pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        except pygame.error:
            self.windowed = True
            return pygame.display.set_mode(DEFAULT_WINDOW)

    @property
    def sprite_scale(self) -> float:
        """源帧 -> 物理像素缩放：2K 时 1:1（640×360），1080P 时 0.75，永不超过 1。"""
        s = self.view.s
        zone_phys_w = ZONE_W * s
        zone_phys_h = ZONE_H * s
        return clamp(min(1.0, zone_phys_w / SRC_FRAME_W, zone_phys_h / SRC_FRAME_H), 0.05, 1.0)

    @property
    def upscale_capped(self) -> bool:
        """窗口物理尺寸超过 2K 目标时，精灵按源帧 1:1 封顶（降级，不上采样）。"""
        return self.view.s > 4 / 3 + 1e-6

    def _sprite_mode_text(self) -> str:
        scale = self.sprite_scale
        if scale >= 1.0 - 1e-6:
            if self.upscale_capped:
                return "sprite 1:1 capped (window > 2K, no upsample)"
            return "sprite 1:1 (2K target, zero resample)"
        return f"sprite {scale:.2f}× smooth downsample"

    def _to_logical(self, pos: tuple[int, int]) -> tuple[int, int]:
        x = (pos[0] - self.view.ox) / max(0.0001, self.view.s)
        y = (pos[1] - self.view.oy) / max(0.0001, self.view.s)
        return int(x), int(y)

    def _logical_to_window(self, pos: tuple[float, float]) -> tuple[int, int]:
        return self.view.p(pos)

    def _update_caption(self) -> None:
        try:
            pygame.display.set_caption(
                f"CHARACTER LAB // 8 roles // {self.window.get_width()}x{self.window.get_height()} "
                f"// s={self.view.s:.2f}")
        except pygame.error:
            pass

    def _on_window_changed(self) -> None:
        """F11 切换后重算映射；精灵物理尺寸改变时清缓存并重载当前页。"""
        old_scale = round(self.sprite_scale, 4)
        self.view.set_target(self.window)
        new_scale = round(self.sprite_scale, 4)
        self._update_caption()
        if old_scale != new_scale:
            for runtime in self.runtimes.values():
                runtime.anim.release()
            self.store.cache.clear()
            self.store.bytes_total = 0
            for runtime in self.runtimes.values():
                runtime.state = "idle"
            self._activate_page(self.page)
            self._log(f"sprite scale changed {old_scale:.3f} -> {new_scale:.3f}, clips reloaded", AMBER)

    def _toggle_fullscreen(self) -> None:
        self.windowed = not self.windowed
        try:
            if self.windowed:
                self.window = pygame.display.set_mode(DEFAULT_WINDOW)
            else:
                self.window = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
            self._on_window_changed()
            self._log(f"window mode: {'windowed' if self.windowed else 'fullscreen'}", MUTED)
        except pygame.error as exc:
            self._log(f"切换窗口失败: {exc}", RED)

    # -- 动作加载（懒加载 + LRU）----------------------------------------
    def _spec_for(self, runtime: RoleRuntime, action: str,
                  skill_type: str | None = None) -> ClipSpec | None:
        role = runtime.role
        if action == "skill":
            if role.from_manifest and role.clips.get("skill") is not None:
                return role.clips["skill"]
            return fallback_clip("skill", skill_type=skill_type or role.skill_type)
        clip = role.clips.get(action)
        if clip is not None and clip.path.exists():
            return clip
        return fallback_clip(action)

    def _active_clip_keys(self) -> set[tuple]:
        keys: set[tuple] = set()
        for rid in self.visible_ids:
            anim = self.runtimes[rid].anim
            if anim.clip is not None:
                keys.add(anim.clip.key)
            if anim.prev_clip is not None:
                keys.add(anim.prev_clip.key)
        return keys

    def _load_action(self, runtime: RoleRuntime, action: str, *,
                     skill_type: str | None = None) -> Clip | None:
        spec = self._spec_for(runtime, action, skill_type)
        clip = self.store.get(spec, self.sprite_scale, self.warnings,
                              context=f"{runtime.role.id}.{action}",
                              protect=self._active_clip_keys())
        if clip is None:
            loop = action in ("idle", "move")
            clip = self.store.placeholder(action, runtime.role.name, runtime.role.color,
                                           loop=loop, scale=self.sprite_scale)
        return clip

    def _oneshot_speed(self, action: str, clip: Clip) -> float:
        if self.native_timing:
            return 1.0
        if action == "skill":
            target = ONESHOT_SKILL_SECONDS
        elif action == "ult":
            target = ONESHOT_ULT_SECONDS
        else:
            return 1.0
        duration = clip.duration
        if duration <= target:
            return 1.0
        return duration / target

    def _play(self, runtime: RoleRuntime, action: str, *, loop: bool, fade: float,
              skill_type: str | None = None) -> Clip | None:
        clip = self._load_action(runtime, action, skill_type=skill_type)
        if clip is None:
            return None
        speed = self._oneshot_speed(action, clip)
        runtime.action_speed = speed
        runtime.anim.play(clip, loop=loop, facing=runtime.facing, fade=fade, speed=speed)
        return clip

    def _activate_page(self, page: int, *, initial: bool = False) -> None:
        page = int(clamp(page, 0, 1))
        self.page = page
        ids = [self.roles[page * 4 + i].id for i in range(4)]
        self.visible_ids = ids
        for index in range(4):
            runtime = self.runtimes[ids[index]]
            runtime.visible = True
            runtime.lane = index
            runtime.reset_page_position()
            runtime.anim.release()
            runtime.skill_timer = runtime.rng.uniform(2.2, 4.2)
            idle_clip = self._load_action(runtime, "idle")
            runtime.anim.play(idle_clip, loop=True, facing=runtime.facing, fade=0.0)
            runtime.state = "idle"
        # 只预载当前页 4 个可见角色的 idle + move（"少量 clip"），skill/ult 触发时懒加载
        for index in range(4):
            self._load_action(self.runtimes[ids[index]], "move")
        for role in self.roles:
            if role.id not in ids:
                self.runtimes[role.id].visible = False
        self._log(f"page {page + 1}/2: {' · '.join(ids)}", CYAN)
        if initial:
            print(f"[page] page 1 ready: {ids}  clips={len(self.store.cache)} "
                  f"cache={self.store.bytes_total / 1e6:.1f}MB")

    def switch_page(self, page: int) -> None:
        page = int(clamp(page, 0, 1))
        if page == self.page:
            return
        self.transition_surface = self.window.copy()
        self.transition_t = 0.18
        self.skill_fx.clear()
        self.ult_fx.clear()
        for runtime in self.runtimes.values():
            if runtime.visible:
                runtime.visible = False
                runtime.anim.release()
        # 旧页 clip 全部不再被可见角色引用 → 清空，内存交给新页懒加载
        self.store.clear()
        self._activate_page(page)

    # -- 状态机 ---------------------------------------------------------
    def _choose_skill_type(self, runtime: RoleRuntime) -> str:
        role = runtime.role
        if self.skill_mode == "role":
            return role.skill_type
        if self.skill_mode == "cycle":
            runtime.skill_cycle = (runtime.skill_cycle + 1) % 3
            return ("attack", "heal", "shield")[runtime.skill_cycle]
        return runtime.rng.choice(("attack", "heal", "shield"))

    def _start_skill(self, runtime: RoleRuntime, *, forced_type: str | None = None) -> bool:
        if runtime.state in ("skill", "ult"):
            return False
        skill_type = forced_type or self._choose_skill_type(runtime)
        runtime.skill_type_override = skill_type
        clip = self._play(runtime, "skill", loop=False, fade=0.12, skill_type=skill_type)
        if clip is None:
            return False
        runtime.state = "skill"
        runtime.state_time = 0.0
        runtime.skill_timer = runtime.rng.uniform(*SKILL_CD)
        runtime.flash = 0.25
        color = SKILL_TYPE_COLORS[skill_type]
        self.skill_fx.append(SkillFx(kind=skill_type, x=runtime.x, y=runtime.ground_y,
                                     color=color, facing=runtime.facing, name=clip.name))
        self.texts.append(FloatText(
            x=runtime.x, y=PLATE_Y - 26,
            message=f"{SKILL_TYPE_CN[skill_type]} · {clip.name[:10]}",
            color=color, size=20, life=1.0))
        self._log(f"{runtime.role.id} SKILL {skill_type} ({clip.name})", color)
        return True

    def _start_ult(self, runtime: RoleRuntime, *, ignore_cd: bool = False) -> bool:
        if not runtime.visible:
            return False
        if runtime.state == "ult":
            return False
        if runtime.ult_cd > 0 and not ignore_cd:
            self._log(f"{runtime.role.id} ULT 冷却中 {runtime.ult_cd:.1f}s", MUTED)
            runtime.flash = 0.18
            return False
        clip = self._play(runtime, "ult", loop=False, fade=0.12)
        if clip is None:
            return False
        runtime.state = "ult"
        runtime.state_time = 0.0
        runtime.ult_cd = ULT_CD
        runtime.flash = 0.5
        self.ult_fx.append(UltFx(kind=runtime.role.ult_type, x=runtime.x, y=runtime.ground_y,
                                 color=runtime.role.color, name=runtime.role.ult_label))
        self.texts.append(FloatText(
            x=runtime.x, y=PLATE_Y - 62,
            message=f"ULT · {runtime.role.ult_label[:14]}",
            color=runtime.role.color, size=26, life=1.4, vy=28.0))
        self.flash = max(self.flash, 0.3)
        self._log(f"{runtime.role.id} ULT ({runtime.role.ult_label})", runtime.role.color)
        return True

    def _finish_action(self, runtime: RoleRuntime) -> None:
        runtime.state = "idle"
        runtime.state_time = 0.0
        runtime.idle_timer = runtime.rng.uniform(0.7, 1.8)
        self._play(runtime, "idle", loop=True, fade=0.18)

    def _update_runtime(self, runtime: RoleRuntime, dt: float) -> None:
        runtime.anim.update(dt)
        runtime.state_time += dt
        runtime.flash = max(0.0, runtime.flash - dt)
        runtime.ult_cd = max(0.0, runtime.ult_cd - dt)
        runtime.skill_timer -= dt
        low, high = runtime.zone
        if runtime.state in ("skill", "ult"):
            if runtime.anim.done:
                self._finish_action(runtime)
            return
        if runtime.state == "idle":
            runtime.idle_timer -= dt
            if runtime.idle_timer <= 0:
                runtime.state = "move"
                runtime.state_time = 0.0
                runtime.target_x = runtime.rng.uniform(low + 30, high - 30)
                if abs(runtime.target_x - runtime.x) < 60:
                    runtime.target_x = runtime.x + runtime.rng.choice((-1, 1)) * runtime.rng.uniform(90, 160)
                    runtime.target_x = clamp(runtime.target_x, low, high)
                self._play(runtime, "move", loop=True, fade=0.12)
        elif runtime.state == "move":
            dx = runtime.target_x - runtime.x
            step = runtime.move_speed * dt
            if abs(dx) <= max(2.0, step):
                runtime.x = runtime.target_x
                runtime.state = "idle"
                runtime.state_time = 0.0
                runtime.idle_timer = runtime.rng.uniform(0.8, 2.2)
                self._play(runtime, "idle", loop=True, fade=0.12)
            else:
                runtime.x += math.copysign(min(step, abs(dx)), dx)
                runtime.facing = 1 if dx > 0 else -1
            if runtime.state_time > 6.0:
                runtime.state = "idle"
                runtime.idle_timer = runtime.rng.uniform(0.5, 1.2)
                self._play(runtime, "idle", loop=True, fade=0.12)
        if runtime.skill_timer <= 0 and runtime.state in ("idle", "move"):
            self._start_skill(runtime)

    def _apply_soft_separation(self) -> None:
        visible = [self.runtimes[rid] for rid in self.visible_ids]
        for _ in range(2):
            for index in range(len(visible) - 1):
                left, right = visible[index], visible[index + 1]
                gap = right.x - left.x
                if gap < MIN_GAP:
                    push = (MIN_GAP - gap) * 0.5
                    left.x -= push
                    right.x += push
            for runtime in visible:
                low, high = runtime.zone
                runtime.x = clamp(runtime.x, low, high)
        for runtime in visible:
            runtime.x = clamp(runtime.x, EDGE_MARGIN, W - EDGE_MARGIN)

    # -- 输入 -----------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            self.running = False
            return
        if event.type == pygame.VIDEOEXPOSE:
            self._update_caption()
            return
        if event.type == pygame.KEYDOWN:
            key = event.key
            if key == pygame.K_ESCAPE:
                self.running = False
            elif key == pygame.K_F11:
                self._toggle_fullscreen()
            elif key in (pygame.K_TAB, pygame.K_e):
                self.switch_page(1 - self.page)
            elif key in (pygame.K_q,):
                self.switch_page(1 - self.page)
            elif key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
                slot = key - pygame.K_1
                if slot < len(self.visible_ids):
                    self._start_ult(self.runtimes[self.visible_ids[slot]])
            elif key == pygame.K_u:
                for rid in self.visible_ids:
                    self._start_ult(self.runtimes[rid])
            elif key == pygame.K_a:
                for rid in self.visible_ids:
                    self._start_skill(self.runtimes[rid])
            elif key == pygame.K_d:
                self.debug = not self.debug
                self._log(f"debug boxes: {'on' if self.debug else 'off'}", MUTED)
            elif key == pygame.K_r:
                self._reset()
            elif key == pygame.K_SPACE:
                self.paused = not self.paused
                self._log(f"paused: {self.paused}", AMBER)
            elif key == pygame.K_t:
                modes = ["role", "cycle", "random"]
                self.skill_mode = modes[(modes.index(self.skill_mode) + 1) % len(modes)]
                self._log(f"auto-skill type mode: {self.skill_mode}", CYAN)
            return
        if event.type == pygame.MOUSEMOTION:
            self.mouse_logical = self._to_logical(event.pos)
            self.hover_role = None
            for rid in self.visible_ids:
                runtime = self.runtimes[rid]
                if runtime.hit_rect.collidepoint(self.mouse_logical):
                    self.hover_role = runtime
                    break
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.mouse_logical = self._to_logical(event.pos)
            for rect, page in self.roster_rects:
                if rect.collidepoint(self.mouse_logical):
                    self.switch_page(page)
                    return
            for rect in self.page_buttons.values():
                if rect.collidepoint(self.mouse_logical):
                    self.switch_page(1 - self.page)
                    return
            for rid in self.visible_ids:
                runtime = self.runtimes[rid]
                if runtime.hit_rect.collidepoint(self.mouse_logical):
                    self._start_ult(runtime)
                    return

    def _reset(self) -> None:
        for runtime in self.runtimes.values():
            runtime.reset()
            runtime.anim.release()
        for rid in self.visible_ids:
            runtime = self.runtimes[rid]
            runtime.visible = True
            runtime.reset_page_position()
            self._play(runtime, "idle", loop=True, fade=0.12)
        self.skill_fx.clear()
        self.ult_fx.clear()
        self.texts.clear()
        self.flash = 0.0
        self._log("reset", MUTED)

    def _log(self, message: str, color: tuple[int, int, int] = TEXT) -> None:
        self.log_lines.append((self.time, message, color))
        if len(self.log_lines) > 7:
            del self.log_lines[: len(self.log_lines) - 7]

    # -- 更新 -----------------------------------------------------------
    def update(self, dt: float) -> None:
        self.time += dt
        self.flash = max(0.0, self.flash - dt)
        self.transition_t = max(0.0, self.transition_t - dt)
        if self.paused:
            return
        for rid in self.visible_ids:
            self._update_runtime(self.runtimes[rid], dt)
        self._apply_soft_separation()
        for fx in self.skill_fx:
            fx.t += dt
        self.skill_fx = [fx for fx in self.skill_fx if fx.t < fx.life]
        for fx in self.ult_fx:
            fx.t += dt
        self.ult_fx = [fx for fx in self.ult_fx if fx.t < fx.life]
        for item in self.texts:
            item.t += dt
        self.texts = [item for item in self.texts if item.t < item.life]
        self.store._evict(self._active_clip_keys())

    # -- 绘制 -----------------------------------------------------------
    def draw(self) -> None:
        self.window.fill((0, 0, 0))
        v = self.view
        v.fill(BG, (0, 0, W, H))
        self._draw_stage(v)
        if self.debug:
            self._draw_debug_floor(v)
        self._draw_effects(v, behind=True)
        for rid in sorted(self.visible_ids, key=lambda r: self.runtimes[r].x):
            self._draw_runtime(v, self.runtimes[rid])
        self._draw_effects(v, behind=False)
        if self.debug:
            self._draw_debug_sprite_boxes(v)
        self._draw_role_plates(v)
        self._draw_floating_texts(v)
        self._draw_topbar(v)
        self._draw_hud(v)
        self._draw_overlays(v)
        if self.hover_role is not None and not self.paused:
            self._draw_hover_hint(v, self.hover_role)
        self._set_cursor()

    def _set_cursor(self) -> None:
        want_hand = self.hover_role is not None
        if want_hand == getattr(self, "_cursor_hand", False):
            return
        self._cursor_hand = want_hand
        try:
            pygame.mouse.set_cursor(
                pygame.SYSTEM_CURSOR_HAND if want_hand else pygame.SYSTEM_CURSOR_ARROW)
        except (pygame.error, AttributeError):
            pass

    def _draw_stage(self, v: Painter) -> None:
        bands = 20
        for i in range(bands):
            t = i / (bands - 1)
            color = blend((8, 12, 18), (16, 26, 38), t)
            y = TOP_H + int((BOTTOM_Y - TOP_H) * i / bands)
            h = int((BOTTOM_Y - TOP_H) / bands) + 1
            v.fill(color, (0, y, W, h))
        v.fill(PANEL, (0, 0, W, TOP_H))
        v.line(LINE, (0, TOP_H - 1), (W, TOP_H - 1))
        v.fill(PANEL, (0, BOTTOM_Y, W, H - BOTTOM_Y))
        v.line(LINE, (0, BOTTOM_Y), (W, BOTTOM_Y))
        # 地板
        v.fill((12, 19, 28), (0, GROUND_Y, W, BOTTOM_Y - GROUND_Y))
        for x in range(0, W + 1, 80):
            v.line((21, 32, 45), (x, GROUND_Y), (x, BOTTOM_Y), 1)
        for row in range(1, 5):
            y = GROUND_Y + row * row * 10
            if y < BOTTOM_Y:
                v.line((17, 26, 37), (0, y), (W, y), 1)
        v.line((60, 88, 112), (0, GROUND_Y), (W, GROUND_Y), 2)
        v.line((26, 40, 54), (0, GROUND_Y + 3), (W, GROUND_Y + 3), 1)
        for lane in range(1, ZONE_LANES):
            x = lane * ZONE_W
            for y in range(TOP_H + 20, BOTTOM_Y, 26):
                v.line((24, 36, 49), (x, y), (x, y + 12), 1)
        # 页面水印 / 标题
        v.text(f"PAGE {self.page + 1} / 2", (W // 2, TOP_H + 92), (34, 52, 70), 64,
               bold=True, center=True)
        v.text("ANIMATION · MOVEMENT · STATE MACHINE", (W // 2, TOP_H + 146),
               (46, 66, 86), 18, mono=True, center=True)
        names = "  ·  ".join(self.runtimes[rid].role.name for rid in self.visible_ids)
        v.text(names, (W // 2, TOP_H + 176), (94, 120, 142), 18, center=True)
        # 区域尺寸标注（右上角，避免压住脚底调试信息）
        v.text(f"ZONE {ZONE_W}×{ZONE_H} LOGICAL  →  {int(round(ZONE_W * self.view.s))}×"
               f"{int(round(ZONE_H * self.view.s))} PHYSICAL  ·  source {SRC_FRAME_W}×{SRC_FRAME_H} "
               f"@ ×{self.sprite_scale:.2f}", (W - 30, TOP_H + 14), (52, 74, 92), 13,
               mono=True, right=(W - 30, TOP_H + 14))

    def _draw_topbar(self, v: Painter) -> None:
        v.fill(PANEL, (0, 0, W, TOP_H))
        v.fill(PANEL2, (0, 0, W, 92))
        v.line(LINE, (0, TOP_H - 1), (W, TOP_H - 1))
        v.fill(CYAN, (0, 0, 8, 92))
        v.text("CHARACTER LAB", (34, 18), WHITE, 38, bold=True)
        v.text("全角色动画验证 · 8 个唯一角色 · 无敌人 · 无战斗数值 · 按窗口物理像素直绘",
               (36, 62), MUTED, 17)
        v.text(f"FPS {self.fps_value:5.1f}   TIME {self.time:6.1f}s   SKILL-MODE {self.skill_mode.upper()}",
               (W - 34, 16), MUTED, 15, mono=True, right=(W - 34, 16))
        v.text(f"PAGE {self.page + 1} / 2", (W - 34, 44), CYAN, 20, bold=True, right=(W - 34, 44))
        v.text("Tab / [ ] 翻页", (W - 34, 72), DIM, 12, right=(W - 34, 72))
        self.page_buttons = {}
        for name, rect, label in (
            ("prev", pygame.Rect(W - 330, 46, 38, 28), "◀"),
            ("next", pygame.Rect(W - 286, 46, 38, 28), "▶"),
        ):
            v.rect(PANEL2, rect, radius=6)
            v.rect(LINE2, rect, width=1, radius=6)
            v.text(label, rect.center, TEXT, 16, center=True)
            self.page_buttons[name] = rect
        self.roster_rects = []
        card_w, card_h, gap = 214, 88, 10
        total = card_w * 8 + gap * 7
        x0 = (W - total) // 2
        y0 = 98
        for index, role in enumerate(self.roles):
            rect = pygame.Rect(x0 + index * (card_w + gap), y0, card_w, card_h)
            page = index // 4
            current = page == self.page
            runtime = self.runtimes[role.id]
            hovered = rect.collidepoint(self.mouse_logical)
            fill = PANEL2 if current else (12, 18, 26)
            if hovered:
                fill = blend(fill, role.color, 0.10)
            v.rect(fill, rect, radius=8)
            v.rect(role.color if current else LINE, rect, width=2 if current else 1, radius=8)
            v.fill(role.color, (rect.x + 1, rect.y + 10, 5, rect.h - 20))
            v.text(f"{index + 1:02d}", (rect.right - 10, rect.y + 8),
                   DIM if not current else MUTED, 12, mono=True, right=(rect.right - 10, rect.y + 8))
            v.text(role.name, (rect.x + 16, rect.y + 9), WHITE if current else (150, 170, 186), 18, bold=True)
            v.text(role.id, (rect.x + 16, rect.y + 34), role.color if current else DIM, 13, mono=True)
            v.text(SKILL_TYPE_LABELS.get(role.skill_type, role.skill_type),
                   (rect.x + 16, rect.y + 56), SKILL_TYPE_COLORS.get(role.skill_type, MUTED), 13)
            if runtime.ult_cd > 0.05:
                v.text(f"ULT {runtime.ult_cd:4.1f}s", (rect.right - 12, rect.y + 56), DIM,
                       13, mono=True, right=(rect.right - 12, rect.y + 56))
            else:
                v.text("ULT READY", (rect.right - 12, rect.y + 56), GREEN, 13, mono=True,
                       right=(rect.right - 12, rect.y + 56))
            if current:
                v.circle(role.color, (rect.x + 16, rect.bottom - 13), 4)
            self.roster_rects.append((rect, page))

    # -- 绘制：角色 -----------------------------------------------------
    def _frame_blit_pos(self, runtime: RoleRuntime, surface: pygame.Surface,
                        pivot: tuple[int, int], flip: bool) -> tuple[int, int]:
        width = surface.get_width()
        px = width - pivot[0] if flip else pivot[0]
        return (
            self.view.ox + int(round(runtime.x * self.view.s)) - px,
            self.view.oy + int(round(runtime.ground_y * self.view.s)) - pivot[1],
        )

    def _blit_frame(self, runtime: RoleRuntime, surface: pygame.Surface, pivot: tuple[int, int],
                    *, flip: bool, alpha: int = 255) -> tuple[int, int]:
        sprite = pygame.transform.flip(surface, True, False) if flip else surface
        pos = self._frame_blit_pos(runtime, surface, pivot, flip)
        if alpha < 255:
            sprite = sprite.copy()
            sprite.set_alpha(alpha)
        self.view.surface.blit(sprite, pos)
        return pos

    def _draw_runtime(self, v: Painter, runtime: RoleRuntime) -> None:
        anim = runtime.anim
        surface = anim.current_surface()
        if surface is None:
            return
        clip = anim.clip
        assert clip is not None
        bbox = anim.current_bbox() or pygame.Rect(0, 0, surface.get_width(), surface.get_height())
        facing = 1 if runtime.facing >= 0 else -1
        # 脚底影子
        shadow_w = int(clamp(bbox.width * 0.85, 30, 300))
        shadow = pygame.Surface((shadow_w, max(8, int(14 * self.view.s))), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 120), shadow.get_rect())
        v.surface.blit(shadow, (int(runtime.x * self.view.s + self.view.ox - shadow_w / 2),
                                int(runtime.ground_y * self.view.s + self.view.oy - shadow.get_height() / 2)))
        # 当前帧 + 交叉淡化
        pos = self._blit_frame(runtime, surface, clip.pivot, flip=facing < 0, alpha=255)
        if anim.prev_surface is not None and anim.fade > 0.0 and anim.fade_total > 0:
            ratio = clamp(anim.fade / anim.fade_total, 0.0, 1.0)
            self._blit_frame(runtime, anim.prev_surface,
                             anim.prev_pivot if anim.prev_pivot is not None else clip.pivot,
                             flip=anim.prev_facing < 0, alpha=int(255 * ratio))
        # bbox / hit（物理 -> 逻辑）
        frame_w = surface.get_width()
        bbox_x = pos[0] + (frame_w - bbox.right if facing < 0 else bbox.left)
        hit_phys = pygame.Rect(bbox_x, pos[1] + bbox.top, bbox.width, bbox.height)
        runtime.hit_rect = v.logical_rect(hit_phys).inflate(10, 10)
        runtime.char_top = v.logical_rect(hit_phys).top
        runtime.char_bottom = v.logical_rect(hit_phys).bottom
        # 技能 / 大招高亮描边（用预混合色，避免 alpha 层）
        if runtime.state in ("skill", "ult"):
            color = SKILL_TYPE_COLORS.get(runtime.skill_type_override or runtime.role.skill_type,
                                          runtime.role.color)
            v.rect(tint(color, runtime.char_top, 0.55), (hit_phys.x, hit_phys.y, hit_phys.w, hit_phys.h),
                   width=2, radius=20)

    def _draw_effects(self, v: Painter, *, behind: bool) -> None:
        for fx in self.skill_fx:
            self._draw_skill_fx(v, fx, behind=behind)
        for fx in self.ult_fx:
            self._draw_ult_fx(v, fx, behind=behind)

    def _draw_floating_texts(self, v: Painter) -> None:
        for item in self.texts:
            p = clamp(item.t / max(0.001, item.life), 0.0, 1.0)
            alpha = int(255 * (1.0 - p * p))
            y = item.y - item.vy * p
            v.text(item.message, (item.x, y), item.color, item.size, center=True, alpha=alpha)

    def _draw_skill_fx(self, v: Painter, fx: SkillFx, *, behind: bool) -> None:
        p = clamp(fx.t / max(0.001, fx.life), 0.0, 1.0)
        color = fx.color
        x, y = fx.x, fx.y
        if fx.kind == "attack":
            facing = 1 if fx.facing >= 0 else -1
            start = -0.72 if facing >= 0 else math.pi - 0.72
            if behind:
                # 攻击范围指示（地面圆弧；限制在角色附近、地面线以上，不扫到相邻 role）
                if p < 0.45:
                    radius = 55 + 145 * p
                    v.arc(tint(color, y, 0.45),
                          (x - radius, y - 150 - radius, radius * 2, radius * 2),
                          start, start + 1.44, 3)
                return
            radius = 55 + 145 * p
            v.arc(color, (x - radius, y - 150 - radius, radius * 2, radius * 2),
                  start, start + 1.44, 5)
            radius2 = 42 + 96 * p
            v.arc(blend(color, WHITE, 0.6),
                  (x - radius2, y - 150 - radius2, radius2 * 2, radius2 * 2),
                  start + 0.18, start + 1.08, 2)
            for index in range(5):
                angle = start + 0.25 + index * 0.24
                sx = x + math.cos(angle) * radius2 * 0.9
                sy = y - 150 + math.sin(angle) * radius2 * 0.9
                v.circle(blend(color, WHITE, 0.5), (sx, sy), max(2, 4 * (1 - p)))
        elif fx.kind == "heal":
            if not behind:
                for index in range(5):
                    plus_p = clamp(p * 1.4 - index * 0.08, 0.0, 1.0)
                    if plus_p <= 0:
                        continue
                    angle = index * (math.tau / 5) + fx.t * 0.6
                    radius = 26 + 96 * plus_p
                    px = x + math.cos(angle) * radius
                    py = y - 100 + math.sin(angle) * radius * 0.55 - 34 * plus_p
                    size = max(2, int(7 * (1 - plus_p) + 3))
                    v.line(GREEN, (px - size, py), (px + size, py), 2)
                    v.line(GREEN, (px, py - size), (px, py + size), 2)
                return
            radius = 36 + 120 * p
            v.circle(tint(color, y, 0.35), (x, y - 20), radius, 2)
        elif fx.kind == "shield":
            if not behind:
                return
            center = (x, y - 110)
            alpha_t = clamp(0.9 - 0.35 * p, 0.2, 0.9)
            radius = 90 + 12 * math.sin(math.pi * p)
            points = [(center[0] + radius * math.cos(a), center[1] + radius * math.sin(a))
                      for a in [math.tau * i / 6 - math.pi / 2 for i in range(6)]]
            v.polygon(tint(color, center[1], 0.22 * alpha_t), points)
            v.polygon(color, points, width=3)
            inner = radius * 0.78
            points2 = [(center[0] + inner * math.cos(a), center[1] + inner * math.sin(a))
                       for a in [math.tau * i / 6 - math.pi / 2 for i in range(6)]]
            v.polygon(blend(color, WHITE, 0.45), points2, width=1)

    def _draw_ult_fx(self, v: Painter, fx: UltFx, *, behind: bool) -> None:
        if not behind:
            return
        p = clamp(fx.t / max(0.001, fx.life), 0.0, 1.0)
        fade = math.sin(math.pi * p)
        color = fx.color
        x, y = fx.x, fx.y
        if fx.kind == "summon":
            # 注意：manifest 的 ult 动画本身已包含「现世」召唤特效，这里只叠加地面光环/光柱，
            # 不再画鲸影，避免和源动画重复。
            radius = 80 + 300 * p
            v.circle(tint(color, y, 0.38), (x, y), radius, 2)
            v.circle(tint(color, y, 0.24), (x, y), radius - 34, 2)
            for index in range(3):
                offset = (index - 1) * 90
                v.line(tint(color, y, 0.26), (x + offset, y), (x + offset, y - 300), 2)
            for index in range(8):
                angle = math.tau * index / 8 + fx.t * 1.2
                px = x + math.cos(angle) * (120 + 80 * p)
                py = y - 60 + math.sin(angle) * 80 - 160 * p
                v.circle(blend(color, WHITE, 0.5), (px, py), 3)
        elif fx.kind == "aoe":
            for index in range(3):
                radius = 80 + 520 * p + index * 46
                v.circle(tint(color, y, max(0.12, 0.4 - index * 0.1)), (x, y - 40), radius, 3)
            for index in range(10):
                angle = math.tau * index / 10 + fx.t
                ex = x + math.cos(angle) * (120 + 420 * p)
                ey = y - 40 + math.sin(angle) * (60 + 180 * p)
                v.line(tint(color, y, 0.4), (x, y - 20), (ex, ey), 2)
        else:  # buff
            column_w = 70 + 24 * math.sin(fx.t * 8)
            v.fill(tint(color, y, 0.18), (x - column_w / 2, TOP_H, column_w, y - TOP_H))
            for index in range(4):
                size = 60 + 120 * p + index * 18
                v.ellipse(color, (x - size, y - size / 2, size * 2, size), width=2)
            for index in range(12):
                angle = math.tau * index / 12 + fx.t * 1.4
                spark_x = x + math.cos(angle) * (110 + 60 * p)
                spark_y = y - 120 + math.sin(angle) * 110 - 90 * p
                v.circle(WHITE, (spark_x, spark_y), 3)

    # -- 绘制：调试 / 标签 ----------------------------------------------
    def _zone_rect(self, runtime: RoleRuntime) -> pygame.Rect:
        return pygame.Rect(runtime.lane * ZONE_W, ZONE_TOP, ZONE_W, ZONE_H)

    def _draw_debug_floor(self, v: Painter) -> None:
        for rid in self.visible_ids:
            runtime = self.runtimes[rid]
            low, high = runtime.zone
            interval = pygame.Rect(int(low), ZONE_TOP, int(high - low), ZONE_H + 24)
            color = blend(runtime.role.color, BG, 0.62)
            draw_dashed_rect(v, interval, color, dash=14, gap=10)
            v.text(f"activity {rid}", (interval.x + 2, interval.y - 16), color, 12, mono=True)
            zone = self._zone_rect(runtime)
            v.rect(blend(runtime.role.color, BG, 0.35), zone, width=1)
            v.text(f"zone {ZONE_W}×{ZONE_H}", (zone.x + 4, zone.bottom - 16),
                   blend(runtime.role.color, BG, 0.5), 10, mono=True)
            # 脚底锚点
            ax, ay = runtime.x, runtime.ground_y
            v.line((110, 150, 180), (ax - 16, ay), (ax + 16, ay), 1)
            v.line((110, 150, 180), (ax, ay - 16), (ax, ay + 16), 1)
            v.circle(runtime.role.color, (ax, ay), 5, 1)
            v.text("anchor", (ax + 10, ay + 6), (96, 124, 146), 11, mono=True)
            v.line(color, (low, GROUND_Y + 2), (low, GROUND_Y + 16), 2)
            v.line(color, (high, GROUND_Y + 2), (high, GROUND_Y + 16), 2)
            v.text(f"{int(low)}", (low, GROUND_Y + 20), (80, 104, 124), 10, mono=True, center=True)
            v.text(f"{int(high)}", (high, GROUND_Y + 20), (80, 104, 124), 10, mono=True, center=True)
        for index in range(len(self.visible_ids) - 1):
            left = self.runtimes[self.visible_ids[index]]
            right = self.runtimes[self.visible_ids[index + 1]]
            gap = abs(right.x - left.x)
            color = GREEN if gap >= MIN_GAP - 1 else AMBER
            y = GROUND_Y + 34
            v.line(color, (left.x, y), (right.x, y), 1)
            v.text(f"gap {gap:5.1f} / min {MIN_GAP}", ((left.x + right.x) / 2, y + 4),
                   color, 11, mono=True, center=True)

    def _draw_debug_sprite_boxes(self, v: Painter) -> None:
        for rid in self.visible_ids:
            runtime = self.runtimes[rid]
            if runtime.hit_rect.width <= 0:
                continue
            rect = runtime.hit_rect.inflate(-18, -18)
            v.rect((86, 130, 156), rect, width=1)
            v.text("bbox", (rect.x + 2, rect.y + 2), (86, 130, 156), 10, mono=True)

    def _draw_role_plates(self, v: Painter) -> None:
        for rid in self.visible_ids:
            runtime = self.runtimes[rid]
            role = runtime.role
            # 固定在各 lane 的列位置，避免角色靠近时相邻面板互相压住
            plate_x = runtime.lane * ZONE_W + (ZONE_W - PLATE_W) // 2
            rect = pygame.Rect(plate_x, PLATE_Y, PLATE_W, PLATE_H)
            v.rect((10, 16, 24), rect, radius=8)
            v.rect(role.color, rect, width=2, radius=8)
            v.fill(role.color, (rect.x + 1, rect.y + 10, 4, rect.h - 20))
            v.text(role.name, (rect.x + 16, rect.y + 8), WHITE, 18, bold=True)
            v.text(role.id, (rect.x + 16, rect.y + 32),
                   role.color if runtime.state != "idle" else MUTED, 12, mono=True)
            state_color = {
                "idle": MUTED, "move": CYAN,
                "skill": SKILL_TYPE_COLORS.get(runtime.skill_type_override or role.skill_type, AMBER),
                "ult": role.color,
            }[runtime.state]
            v.text(STATE_LABELS[runtime.state], (rect.x + 70, rect.y + 30), state_color, 13,
                   bold=runtime.state in ("skill", "ult"))
            frame_now, frame_total = runtime.anim.current_frame_index()
            action_text = f"{runtime.anim.current_name()[:13]}  {frame_now:3d}/{frame_total:<3d}"
            if runtime.anim.speed > 1.05:
                action_text += f" ×{runtime.anim.speed:.1f}"
            v.text(action_text, (rect.x + 16, rect.y + 52), TEXT, 13)
            skill_type = runtime.skill_type_override or role.skill_type
            v.text(SKILL_TYPE_LABELS.get(skill_type, skill_type),
                   (rect.x + 16, rect.y + 72), SKILL_TYPE_COLORS.get(skill_type, MUTED), 12)
            if runtime.ult_cd > 0.05:
                v.text(f"ULT CD {runtime.ult_cd:4.1f}s", (rect.right - 12, rect.y + 72), DIM,
                       12, mono=True, right=(rect.right - 12, rect.y + 72))
            else:
                v.text("ULT READY", (rect.right - 12, rect.y + 72), GREEN, 12, mono=True,
                       right=(rect.right - 12, rect.y + 72))
            v.text(f"ult: {role.ult_label[:12]}", (rect.right - 12, rect.y + 52), DIM, 11,
                   right=(rect.right - 12, rect.y + 52))
            progress = runtime.anim.progress()
            bar = pygame.Rect(rect.x + 16, rect.bottom - 10, rect.w - 32, 4)
            v.fill((26, 38, 50), bar)
            if progress > 0:
                v.fill(role.color, (bar.x, bar.y, int(bar.w * progress), bar.h))
            if runtime.state in ("skill", "ult") or runtime.flash > 0:
                v.rect(role.color, rect, width=3, radius=8)

    # -- 绘制：HUD / 覆盖层 ---------------------------------------------
    def _draw_hud(self, v: Painter) -> None:
        v.fill(PANEL, (0, BOTTOM_Y, W, H - BOTTOM_Y))
        v.line(LINE, (0, BOTTOM_Y), (W, BOTTOM_Y))
        left_x = 30
        row1 = BOTTOM_Y + 18
        v.text(f"FPS {self.fps_value:5.1f}", (left_x, row1),
               GREEN if self.fps_value > 50 else AMBER, 20, mono=True)
        v.text(f"clock {self.time:6.1f}s", (left_x + 140, row1), MUTED, 15, mono=True)
        v.text(f"debug {'ON' if self.debug else 'OFF'} (D)", (left_x + 290, row1), MUTED, 14)
        v.text(f"paused {'YES' if self.paused else 'no'} (Space)", (left_x + 440, row1),
               AMBER if self.paused else MUTED, 14)
        v.text("energy ∞ · ULT 无消耗 · CD 12s", (left_x + 640, row1), DIM, 13)
        manifest = self.manifest_status
        if manifest.get("from_manifest") and manifest.get("count") == 8:
            status_color = GREEN
            role_ids = " ".join(role.id for role in self.roles)
            status_text = f"manifest OK · 8 roles [{role_ids}] · assets/pets/lab_manifest.json"
        elif manifest.get("from_manifest"):
            status_color = AMBER
            status_text = f"manifest 部分可用 · {manifest.get('count', 0)} roles · 缺的用 fallback（warning）"
        else:
            status_color = AMBER
            status_text = "manifest MISSING → 本地 dsh fallback（8 角色共用动作，正式 manifest 落盘后自动切换）"
        v.text(status_text, (left_x, row1 + 26), status_color, 13, mono=manifest.get("from_manifest", False))
        v.text(f"auto-skill mode {self.skill_mode.upper()} (T)  ·  page {self.page + 1}/2  ·  "
               f"visible {' '.join(self.visible_ids)}", (left_x, row1 + 52), CYAN, 13, mono=True)
        pacing = ("one-shot: source timing (≈10s)" if self.native_timing
                  else f"one-shot: skill ≤{ONESHOT_SKILL_SECONDS}s / ult ≤{ONESHOT_ULT_SECONDS}s")
        v.text(f"clip cache {self.store.bytes_total / 1e6:5.1f}MB / {self.store.cap_bytes / 1e6:.0f}MB "
               f"· loads {self.store.loads} · evict {self.store.evictions} · "
               f"{self._sprite_mode_text()} · {pacing}", (left_x, row1 + 76), DIM, 12, mono=True)
        if self.upscale_capped:
            v.text("WARN 窗口 > 2K：精灵 1:1 封顶，不上采样（降级）",
                   (W - 30, row1), (230, 170, 80), 12, right=(W - 30, row1))
        if self.warnings:
            v.text(f"warnings {len(self.warnings)}: {self.warnings[-1][:70]}",
                   (left_x + 470, row1 + 52), (220, 170, 90), 12)
        # 中栏：事件日志
        log_x = 1150
        v.text("EVENT LOG", (log_x, row1), MUTED, 12, mono=True)
        for index, (stamp, message, color) in enumerate(self.log_lines[-4:]):
            v.text(f"{stamp:5.1f}s", (log_x, row1 + 22 + index * 18), DIM, 11, mono=True)
            v.text(message[:34], (log_x + 52, row1 + 22 + index * 18), color, 12)
        # 右栏：操作提示
        help_x = W - 30
        lines = [
            "1-4 / 点击角色 = 大招",
            "U 全屏大招 · A 强制小技能",
            "Tab / [ ] 翻页 · T 技能类型",
            "D 调试框 · R 重置 · Space 暂停",
            "F11 全屏/窗口 · Esc 退出",
        ]
        for index, line in enumerate(lines):
            v.text(line, (help_x, row1 + index * 20), MUTED, 13,
                   right=(help_x, row1 + index * 20))

    def _draw_overlays(self, v: Painter) -> None:
        if self.transition_surface is not None and self.transition_t > 0:
            alpha = int(clamp(self.transition_t / 0.18, 0, 1) * 220)
            snapshot = self.transition_surface
            snapshot.set_alpha(alpha)
            v.surface.blit(snapshot, (0, 0))
            snapshot.set_alpha(255)
        if self.flash > 0.02:
            # 用边框光晕代替全屏 alpha 闪白（直接物理像素绘制，免全屏 alpha 层）
            strength = clamp(self.flash / 0.35, 0.0, 1.0)
            for index, width in enumerate((26, 16, 8)):
                color = blend((40, 60, 80), (190, 230, 255), 0.22 + 0.25 * (2 - index) * strength)
                v.rect(color, (0, 0, W, H), width=width)
        if self.paused:
            veil = pygame.Surface(self.view.surface.get_size(), pygame.SRCALPHA)
            veil.fill((4, 8, 14, 140))
            v.surface.blit(veil, (0, 0))
            v.text("PAUSED", (W // 2, H // 2 - 20), AMBER, 56, bold=True, center=True)
            v.text("Space 继续 · R 重置 · Esc 退出", (W // 2, H // 2 + 40), MUTED, 20, center=True)

    def _draw_hover_hint(self, v: Painter, runtime: RoleRuntime) -> None:
        if runtime.ult_cd > 0.05:
            hint, color = f"ULT 冷却 {runtime.ult_cd:.1f}s", MUTED
        else:
            hint, color = "点击 = 大招", runtime.role.color
        pos = (runtime.x, runtime.char_top - 26)
        rect = v.text(hint, pos, color, 14, center=True)
        rect.inflate_ip(18, 8)
        v.rect((10, 16, 24), rect, radius=6)
        v.rect(color, rect, width=1, radius=6)
        v.text(hint, pos, color, 14, center=True)

    # -- 运行循环 -------------------------------------------------------
    def _present(self) -> None:
        self._update_caption()
        pygame.display.flip()

    def run(self) -> int:
        try:
            if self.smoke_mode:
                return self._run_smoke()
            if self.shot_path is not None:
                return self._run_shot()
            return self._run_interactive()
        finally:
            # 允许同一进程反复构造 lab（截图/测试），避免缓存的字体在 pygame.quit 后失效
            _FONT_CACHE.clear()
            pygame.quit()

    def _run_interactive(self) -> int:
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            dt = min(dt, 0.05)
            self.fps_value = 1.0 / max(dt, 1e-3)
            for event in pygame.event.get():
                self.handle_event(event)
            if not self.running:
                break
            self.update(dt)
            self.frame_index += 1
            self.draw()
            self._present()
        return 0

    def _run_shot(self) -> int:
        assert self.shot_path is not None
        dt = 1.0 / FPS
        target = max(0.05, self.shot_time)
        forced_skills = False
        forced_ults = False
        while self.time < target:
            if self.time >= 0.12:
                if self.force_skills and not forced_skills:
                    for rid in self.visible_ids:
                        self._start_skill(self.runtimes[rid], forced_type=self.runtimes[rid].role.skill_type)
                    forced_skills = True
                if self.force_ults and not forced_ults:
                    slot = getattr(self.args, "ult_slot", None)
                    if slot is not None:
                        targets = [int(clamp(int(slot), 1, 4)) - 1]
                    else:
                        targets = list(range(len(self.visible_ids)))
                    for index in targets:
                        if 0 <= index < len(self.visible_ids):
                            self._start_ult(self.runtimes[self.visible_ids[index]], ignore_cd=True)
                    forced_ults = True
            self.update(dt)
            self.frame_index += 1
            self.draw()
        self.fps_value = FPS
        self.draw()
        self._save_screenshot(self.shot_path)
        ww, wh = self.window.get_size()
        print(f"SHOT OK {self.shot_path}  physical={ww}x{wh}  logical={W}x{H}  "
              f"roles={len(self.roles)}  page={self.page + 1}  "
              f"manifest={'yes' if self.manifest_status.get('from_manifest') else 'fallback'}  "
              f"{self._sprite_mode_text()}  "
              f"time={self.time:.2f}s  clip_cache={self.store.bytes_total / 1e6:.1f}MB")
        return 0

    def _save_screenshot(self, path: Path) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            pygame.image.save(self.window, str(path))
        except (OSError, pygame.error) as exc:
            print(f"[error] 保存截图失败 {path}: {exc}")

    # -- smoke ----------------------------------------------------------
    def _run_smoke(self) -> int:
        """无窗口自检：manifest / 分辨率映射 / 8 唯一角色 / 翻页 / 状态机 / 输入 / 内存 / 截图。"""
        print("[smoke] Character Lab 无窗口自检（默认 2560×1440 物理 = 2K 1:1 目标）")
        errors: list[str] = []

        def check(condition: bool, message: str) -> None:
            if condition:
                print(f"  ok  {message}")
            else:
                errors.append(message)
                print(f"  FAIL {message}")

        ww, wh = self.window.get_size()
        check(ww == 2560 and wh == 1440, f"默认窗口物理尺寸 2560×1440 (got {ww}×{wh})")
        check(abs(self.view.s - 4 / 3) < 1e-6, f"物理/逻辑比例 s=4/3 (got {self.view.s:.4f})")
        check(abs(self.sprite_scale - 1.0) < 1e-6,
              f"2K 下精灵 1:1（scale={self.sprite_scale:.3f}, 640×360 物理，不上采样）")
        ids = [role.id for role in self.roles]
        check(len(ids) == 8, f"8 个角色 (got {len(ids)})")
        check(len(set(ids)) == 8, "角色 id 唯一（dsh/dsh1 已合并）")
        check(set(ids) == set(ROLE_ORDER), f"角色 id 集合符合预期 {sorted(ids)}")

        # --- manifest 状态 ---
        manifest_exists = MANIFEST_PATH.exists()
        if manifest_exists:
            check(self.manifest_status.get("from_manifest"), "manifest 已加载（assets/pets/lab_manifest.json）")
            check(all(role.from_manifest for role in self.roles),
                  "8 角色全部来自 manifest（无角色级 fallback）")
            check(self.manifest_status.get("count") == 8, f"manifest 角色数 = 8")
            print("  manifest roles: " + ", ".join(
                f"{r.id}「{r.name}」{r.skill_type}/{r.ult_type}" for r in self.roles))
            missing = [w for w in self.warnings if "缺少动作资源" in w]
            if missing:
                print("  manifest 缺失动作（逐动作 dsh fallback，需同步 Lead）：")
                for warning in missing:
                    print(f"   - {warning}")
            else:
                print("  manifest actions complete: 32/32 (idle/move/skill/ult × 8 roles)")
        else:
            check(not self.manifest_status.get("from_manifest"), "manifest 不存在时 fallback 生效")

        # --- 分辨率 / 懒加载 ---
        check(len(self.store.cache) <= 8, f"启动只加载当前页少量 clip (cache={len(self.store.cache)})")
        clip = self.runtimes[ids[0]].anim.clip
        check(clip is not None and max(clip.size) <= 640, "帧物理尺寸不超过源帧 640×360（不上采样）")
        check(self.visible_ids == [role.id for role in self.roles[0:4]],
              f"启动页 4 角色 {self.visible_ids}")

        state_seen: dict[str, set[str]] = {rid: set() for rid in ids}
        crossfade_seen: set[str] = set()
        oneshot_speeds: set[float] = set()
        skill_durations: list[float] = []
        ult_durations: list[float] = []
        state_start_frame: dict[str, int] = {}
        state_start_kind: dict[str, str] = {}
        captures = [
            (60, SHOTS_DIR / "character_lab_smoke_skills.png"),
            (260, SHOTS_DIR / "character_lab_smoke_ult.png"),
            (470, SHOTS_DIR / "character_lab_smoke_page2_skills.png"),
            (560, SHOTS_DIR / "character_lab_smoke_page2_ult.png"),
            (1300, SHOTS_DIR / "character_lab_smoke_stage.png"),
        ]
        saved: list[Path] = []
        dt = 1.0 / FPS
        page2_ids: list[str] = []
        key_ult_checked = False
        mouse_ult_checked = False
        cache_peak = self.store.bytes_total
        visible_prev = set(self.visible_ids)
        for frame in range(1450):
            if set(self.visible_ids) != visible_prev:
                # 翻页会重置隐藏角色的状态：丢弃跨页的动作时长样本，避免误报
                for rid in self.runtimes:
                    if rid not in self.visible_ids:
                        state_start_kind.pop(rid, None)
                        state_start_frame.pop(rid, None)
                visible_prev = set(self.visible_ids)
            if frame == 10:
                for rid in self.visible_ids:
                    self._start_skill(self.runtimes[rid])
                check(any(self.runtimes[r].state == "skill" for r in self.visible_ids),
                      "全部可见角色触发自动小技能")
                check(self.runtimes[self.visible_ids[0]].anim.fade_total > 0,
                      "动作切换带交叉淡化设置")
            elif frame == 200:
                for rid in self.visible_ids:
                    self._start_ult(self.runtimes[rid], ignore_cd=True)
                check(all(self.runtimes[r].state == "ult" for r in self.visible_ids),
                      "第一页全部可见角色触发大招")
            elif frame == 400:
                # 用 Tab 键翻页，验证输入路径
                self.runtimes[self.visible_ids[0]].ult_cd = 0.0
                self.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_TAB))
                page2_ids = list(self.visible_ids)
                check(page2_ids == [role.id for role in self.roles[4:8]], "Tab 翻页切到第二页")
                for rid in page2_ids:
                    self.runtimes[rid].ult_cd = 0.0
            elif frame == 440:
                for rid in self.visible_ids:
                    self._start_skill(self.runtimes[rid])
            elif frame == 520:
                for rid in self.visible_ids:
                    self._start_ult(self.runtimes[rid], ignore_cd=True)
                check(all(self.runtimes[r].state == "ult" for r in self.visible_ids),
                      "第二页全部可见角色触发大招")
            elif frame == 760:
                self.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_TAB))
                check(list(self.visible_ids) == [role.id for role in self.roles[0:4]], "Tab 翻回第一页")
                self.runtimes[self.visible_ids[1]].ult_cd = 0.0
            elif frame == 820:
                self.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_2))
                key_ult_checked = self.runtimes[self.visible_ids[1]].state == "ult"
            elif frame == 980:
                target = self.runtimes[self.visible_ids[2]]
                target.ult_cd = 0.0
                center = target.hit_rect.center if target.hit_rect.width > 0 else (
                    target.x, target.ground_y - 120)
                window_pos = self._logical_to_window(center)
                self.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=window_pos))
                mouse_ult_checked = target.state == "ult"
            self.update(dt)
            self.frame_index += 1
            cache_peak = max(cache_peak, self.store.bytes_total)
            for rid in self.visible_ids:
                runtime = self.runtimes[rid]
                state = runtime.state
                state_seen[rid].add(state)
                anim = runtime.anim
                if anim.prev_surface is not None and anim.fade > 0:
                    crossfade_seen.add(rid)
                if state in ("skill", "ult"):
                    oneshot_speeds.add(round(anim.speed, 2))
                if state != state_start_kind.get(rid):
                    previous = state_start_kind.get(rid)
                    start_frame = state_start_frame.get(rid, frame)
                    elapsed = (frame - start_frame) / FPS
                    if previous == "skill":
                        skill_durations.append(elapsed)
                    elif previous == "ult":
                        ult_durations.append(elapsed)
                    state_start_kind[rid] = state
                    state_start_frame[rid] = frame
            self.draw()
            for capture_frame, path in captures:
                if frame == capture_frame:
                    self._save_screenshot(path)
                    saved.append(path)
        # 收尾：先冻结自动小技能，确保动作能自然播完回 idle（不硬切）
        for rid in self.visible_ids:
            self.runtimes[rid].skill_timer = 1e9
        for _ in range(300):
            self.update(dt)
        for rid in self.visible_ids:
            runtime = self.runtimes[rid]
            check(runtime.state in ("idle", "move"), f"{rid} 动作播完回 idle/move（当前 {runtime.state}）")
            check(not runtime.anim.done, f"{rid} 没有停在动作最后一帧")
        # 一遍性动作时长 / 加速断言
        if not self.native_timing:
            check(bool(oneshot_speeds) and max(oneshot_speeds) > 1.0,
                  f"一遍性动作默认加速（observed speed={sorted(oneshot_speeds)}）")
            check(all(d <= ONESHOT_SKILL_SECONDS + 0.6 for d in skill_durations),
                  f"skill 状态时长 ≤{ONESHOT_SKILL_SECONDS + 0.6:.1f}s "
                  f"(max={max(skill_durations) if skill_durations else 0:.2f}s)")
            check(all(d <= ONESHOT_ULT_SECONDS + 0.6 for d in ult_durations),
                  f"ult 状态时长 ≤{ONESHOT_ULT_SECONDS + 0.6:.1f}s "
                  f"(max={max(ult_durations) if ult_durations else 0:.2f}s)")
        else:
            check(all(abs(s - 1.0) < 1e-6 for s in oneshot_speeds),
                  f"--native-timing 下按 manifest 原生速度播放 {sorted(oneshot_speeds)}")
        # 状态覆盖
        for rid in ids:
            check("idle" in state_seen[rid], f"{rid} 观察到 idle")
            check("skill" in state_seen[rid], f"{rid} 观察到 skill")
            check("ult" in state_seen[rid], f"{rid} 观察到 ult")
        check(len(crossfade_seen) >= 4, f"观察到交叉淡化角色数 {len(crossfade_seen)}")
        check(key_ult_checked, "键盘 1-4 触发大招")
        check(mouse_ult_checked, "鼠标点击角色触发大招")
        check(len(page2_ids) == 4, "第二页有 4 个角色")
        # 显式移动验证：两页共 8 个角色都要在活动区间内进入 move
        moved: set[str] = set()
        for page in (0, 1):
            self.switch_page(page)
            for rid in self.visible_ids:
                runtime = self.runtimes[rid]
                runtime.skill_timer = 1e9
                runtime.state = "idle"
                runtime.idle_timer = 0.03
                self._play(runtime, "idle", loop=True, fade=0.0)
            for _ in range(150):
                self.update(dt)
                for rid in self.visible_ids:
                    if self.runtimes[rid].state == "move":
                        moved.add(rid)
        for rid in ids:
            check(rid in moved, f"{rid} 在活动区间内进入 move（软分离可观察）")
        # 内存 / 1080P 公式
        check(self.store.bytes_total <= self.store.cap_bytes,
              f"当前 clip 缓存 {self.store.bytes_total / 1e6:.1f}MB ≤ 512MB")
        check(cache_peak <= 1024 * 1024 * 1024,
              f"缓存峰值 {cache_peak / 1e6:.1f}MB < 1GB（禁止 8×4 全预载 ≈3.4GB）")
        check(abs(min(1.0, ZONE_W * 1.0 / SRC_FRAME_W, ZONE_H * 1.0 / SRC_FRAME_H) - 0.75) < 1e-9,
              "1080P 窗口下精灵 scale=0.75（下采样，不上采样）")
        # 收尾展示页
        self.switch_page(0)
        for rid in self.visible_ids:
            self.runtimes[rid].ult_cd = 0.0
            self.runtimes[rid].skill_timer = 1e9
            self.runtimes[rid].state = "idle"
            self._play(self.runtimes[rid], "idle", loop=True, fade=0.0)
        for _ in range(40):
            self.update(dt)
        self.draw()
        final_shot = SHOTS_DIR / "character_lab_smoke_final.png"
        self._save_screenshot(final_shot)
        saved.append(final_shot)
        print(f"[smoke] roles={len(self.roles)} unique={len(set(ids))} "
              f"manifest={'loaded' if self.manifest_status.get('from_manifest') else 'fallback'} "
              f"window={self.window.get_size()} s={self.view.s:.3f} sprite_scale={self.sprite_scale:.3f} "
              f"cache_now={self.store.bytes_total / 1e6:.1f}MB cache_peak={cache_peak / 1e6:.1f}MB "
              f"loads={self.store.loads} evictions={self.store.evictions} shots={len(saved)} "
              f"oneshot_speeds={sorted(oneshot_speeds)}")
        if errors:
            print(f"[smoke] FAILED: {len(errors)} 项")
            for error in errors:
                print(f"  - {error}")
            return 1
        print("CHARACTER LAB SMOKE OK")
        return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Character Lab: 8 roles animation / movement lab")
    parser.add_argument("--windowed", action="store_true", help="窗口模式（默认全屏）")
    parser.add_argument("--size", default=None, help="窗口物理尺寸 WxH，例如 1920x1080（隐含窗口模式）")
    parser.add_argument("--shot", default=None, help="无窗口截图路径（PNG，窗口物理分辨率），保存后退出")
    parser.add_argument("--time", type=float, default=SHOT_DEFAULT_TIME,
                        help="--shot 模拟到第几秒（默认 3.0）")
    parser.add_argument("--page", type=int, default=1, help="初始页 1/2")
    parser.add_argument("--seed", type=int, default=SEED, help="随机种子")
    parser.add_argument("--force-skills", action="store_true", help="截图/调试：开场强制全部可见小技能")
    parser.add_argument("--force-ults", action="store_true", help="截图/调试：开场强制全部可见大招")
    parser.add_argument("--ult-slot", type=int, default=None,
                        help="配合 --force-ults 只让某一槽位（1-4）放大招，截图更干净")
    parser.add_argument("--no-debug", action="store_true", help="关闭脚底锚点/活动区间调试框")
    parser.add_argument("--native-timing", action="store_true",
                        help="一遍性动作按 manifest 原生时长播放（默认 Lab 会加速到 skill≤2.4s / ult≤3.2s）")
    parser.add_argument("--smoke", action="store_true", help="无窗口 smoke 自检（自动使用 dummy SDL）")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.smoke and "SDL_VIDEODRIVER" not in os.environ:
        os.environ["SDL_VIDEODRIVER"] = "dummy"
    if "SDL_AUDIODRIVER" not in os.environ:
        os.environ["SDL_AUDIODRIVER"] = "dummy"
    lab = CharacterLab(args)
    return lab.run()


if __name__ == "__main__":
    sys.exit(main())
