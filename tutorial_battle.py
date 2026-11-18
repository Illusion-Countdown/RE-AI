# -*- coding: utf-8 -*-
"""Tutorial Battle：第一关 3 人 × 3 Wave 教学战斗原型。

定位
----
- 固定队伍：Qwen（先锋 / shield）、DeepSeek（输出 / attack，复用 manifest 的 dsh 资源）、
  Claude（支援 / heal）。无大招、无模块、无升星、无商店、无货币。
- 三波：
  · W1：2× MINION，教自动移动 / 自动普攻 / 自动小技能；
  · W2：MINION + SENTINEL + BOMB，教三种普通敌人；
  · W3：SENTINEL + WARD，二者之间有 SHARE（青，伤害共享）与 BUFF（金，WARD→SENTINEL 增益）；
    只允许剪断一次引用。底部唯一主动「断连」在 W1/W2 锁定，W3 首次出现弹窗后解锁。
- 所有首次出现的新机制/敌人/操作都走「时停模态弹窗」，点击继续后才恢复战斗。
- 1920×1080 逻辑坐标 + 窗口物理像素直绘（复用 character_lab.Painter），不整幅 scale；
  复用 character_lab.ClipStore / load_roles / Animator / RoleRuntime 与 lab_manifest.json。
- 角色/敌人自动战斗；敌人有简单 AI/HP；全灭弹「重试当前波」；三波清空后「教程完成」。

运行（项目根 D:\\Pygame\\RE-AI-AutoChess）
-----------------------------------------
    D:\\Pygame\\.venv\\Scripts\\python.exe tutorial_battle.py                     # 默认全屏
    D:\\Pygame\\.venv\\Scripts\\python.exe tutorial_battle.py --windowed
    D:\\Pygame\\.venv\\Scripts\\python.exe tutorial_battle.py --windowed --size 1920x1080
    D:\\Pygame\\.venv\\Scripts\\python.exe tutorial_battle.py --shot shots/tutorial_wave1.png --time 6
    $env:SDL_VIDEODRIVER='dummy'; D:\\Pygame\\.venv\\Scripts\\python.exe tutorial_battle.py --smoke

本文件独立运行；不修改 character_lab.py / main.py / battle_demo.py / assets。
"""

from __future__ import annotations

import argparse
import math
import os
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pygame

import character_lab as CL


# ---------------------------------------------------------------------------
# 常量 / 布局（全部 1920×1080 逻辑坐标）
# ---------------------------------------------------------------------------
W, H = 1920, 1080
DEFAULT_WINDOW = (2560, 1440)
FPS = 60
SEED = 20261118

TOPBAR_H = 96
LEFT_PANEL = pygame.Rect(24, 104, 300, 812)
ARENA = pygame.Rect(348, 104, 1160, 812)
RIGHT_PANEL = pygame.Rect(1524, 104, 372, 812)
BOTTOM_Y = 930
BATTLE_RECT = pygame.Rect(404, 256, 1052, 596)   # 脚底 (x,y) 可活动范围
ALLY_FRAME_LOGICAL_W = 360.0                     # 战场里角色帧的逻辑显示宽（2K 下 0.75× 源帧）
ALLY_FRAME_LOGICAL_H = 202.5
SHOT_DEFAULT_TIME = 6.0

# 主题色（与 Character Lab 保持同一套终端风）
INK = (7, 11, 17)
BG = (10, 15, 22)
PANEL = (15, 23, 33)
PANEL2 = (19, 29, 41)
PANEL3 = (12, 18, 26)
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
GOLD = (255, 206, 84)

SHARE_CYAN = (72, 222, 235)
BUFF_GOLD = (255, 206, 84)

ALLY_ORDER = ["qwen", "deepseek", "claude"]
ALLY_MANIFEST_ID = {"qwen": "qwen", "deepseek": "dsh", "claude": "claude"}
ALLY_DISPLAY = {
    "qwen": {"name": "Qwen", "slot": "先锋", "type": "SHIELD",
             "desc": "自动给附近友军护盾（180）", "intro": "站前排承伤，小技能为附近友军提供护盾（范围 180）。"},
    "deepseek": {"name": "DeepSeek", "slot": "输出", "type": "ATTACK",
                 "desc": "远程持续输出", "intro": "保持距离持续普攻，小技能打范围爆发。"},
    "claude": {"name": "Claude", "slot": "支援", "type": "HEAL",
               "desc": "自动治疗生命最低角色", "intro": "远程支援，小技能优先治疗生命最低的队友。"},
}
ALLY_STATS = {
    "qwen": dict(hp=280, damage=14, attack_range=180, attack_interval=1.0,
                 move_speed=118, skill_cd=6.5, color=(136, 152, 216)),
    "deepseek": dict(hp=190, damage=27, attack_range=260, attack_interval=0.95,
                     move_speed=126, skill_cd=5.5, color=(86, 118, 210)),
    "claude": dict(hp=180, damage=11, attack_range=250, attack_interval=1.25,
                   move_speed=124, skill_cd=7.0, color=(232, 136, 72)),
}

# 选中/悬停时的范围圈（第一关固定站位，不做拖拽部署）：
# (移动范围半径, 攻击/支援范围半径) —— 蓝内圈锚定部署点固定不动；外圈跟随角色当前位置。
# Claude 为支援角色，外圈用绿色表示治疗/支援范围。
ALLY_RANGE_UI = {
    "qwen": (140.0, 180.0),
    "deepseek": (170.0, 260.0),
    "claude": (150.0, 250.0),
}
ALLY_RANGE_OUTER_COLOR = {
    "qwen": (255, 206, 84),
    "deepseek": (255, 206, 84),
    "claude": (114, 230, 160),
}
ALLY_RANGE_INNER_COLOR = (86, 176, 255)

# 战场比例：角色统一等比缩小到原来的约 0.55×，脚底锚点不变；左栏头像另用高分辨率源帧。
FIELD_SPRITE_SCALE = 0.55
ENEMY_DRAW_SCALE = 0.72
ALLY_MIN_GAP = 78.0
# 三人各自活动带（互不重叠的横向条带），软分离约束在带内。
ALLY_BANDS = {
    "qwen": pygame.Rect(470, 690, 460, 158),
    "deepseek": pygame.Rect(404, 530, 430, 138),
    "claude": pygame.Rect(560, 390, 430, 138),
}
ALLY_HOMES = {
    "qwen": (690.0, 768.0),
    "deepseek": (560.0, 598.0),
    "claude": (760.0, 458.0),
}

# W3 结算奖励：被动协议卡（只展示，不进入 5x5；第二关再接入）
REWARD_CARDS = [
    {
        "key": "attack_protocol",
        "name": "攻击协议",
        "effect": "全体攻击力 +10",
        "shape": [(0, 0), (0, 1), (1, 0)],
        "color": AMBER,
        "type": "被动 / 攻击",
        "desc": "第二关开始装配到 5×5 内存板",
    },
    {
        "key": "defense_protocol",
        "name": "防御协议",
        "effect": "全体防御力 +10",
        "shape": [(0, 0), (0, 1), (1, 0), (1, 1)],
        "color": (88, 150, 255),
        "type": "被动 / 防御",
        "desc": "第二关开始装配到 5×5 内存板",
    },
]

ENEMY_STATS = {
    "MINION": dict(name="游标", hp=72, damage=6, attack_range=74,
                   attack_interval=1.25, speed=64, radius=26, color=(240, 96, 92),
                   desc="最基础近战，会主动接近角色"),
    "SENTINEL": dict(name="哨兵", hp=230, damage=13, attack_range=190,
                     attack_interval=1.9, speed=40, radius=36, color=ORANGE,
                     desc="远程，移动到射程后停下射击"),
    "BOMB": dict(name="析构炸弹", hp=46, damage=34, attack_range=40,
                 attack_interval=99.0, speed=104, radius=25, color=(255, 110, 88),
                 desc="快速接近，死亡时爆炸"),
    "WARD": dict(name="护盾守卫", hp=170, damage=0, attack_range=240,
                 attack_interval=99.0, speed=26, radius=30, color=(96, 206, 226),
                 desc="给链接目标提供增益/护盾；剪断金线会移除增益"),
}
ENEMY_KINDS = ["MINION", "SENTINEL", "BOMB", "WARD"]

WAVES = [
    {"label": "WAVE 1", "objective": "击破 2 个游标", "enemies": [
        ("MINION", 1228, 640), ("MINION", 1364, 778),
    ]},
    {"label": "WAVE 2", "objective": "击破 游标 / 哨兵 / 析构炸弹", "enemies": [
        ("MINION", 1168, 568), ("SENTINEL", 1320, 748), ("BOMB", 1410, 500),
    ]},
    {"label": "WAVE 3", "objective": "击破 哨兵 + 护盾守卫，剪断一条引用", "enemies": [
        ("SENTINEL", 1262, 716), ("WARD", 1436, 592),
    ]},
]

MODAL_KINDS = ("opening", "w1", "w2", "w3", "cut", "defeat", "complete",
               "enemy_MINION", "enemy_SENTINEL", "enemy_BOMB", "enemy_WARD")


def _lighten(color: tuple[int, int, int], amount: int = 18) -> tuple[int, int, int]:
    return tuple(min(255, value + amount) for value in color)


def _has_cjk(value: Any) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in str(value))


class Painter(CL.Painter):
    """在 character_lab.Painter 之上做一个小修正：等宽字体没有中文字形，
    含中文的文本自动回退到默认中文字体，避免出现「囗囗」豆腐块。"""

    def text(self, value: Any, pos: tuple[float, float],
             color: tuple[int, int, int] = TEXT, size: int = 16, *,
             bold: bool = False, mono: bool = False, center: bool = False,
             right: bool | tuple[float, float] = False, alpha: int = 255) -> pygame.Rect:
        if mono and _has_cjk(value):
            mono = False
        return super().text(value, pos, color, size, bold=bold, mono=mono, center=center,
                            right=right, alpha=alpha)


# ---------------------------------------------------------------------------
# 轻量数据结构
# ---------------------------------------------------------------------------
@dataclass
class Modal:
    kind: str
    title: str
    lines: list[str]
    illustration: str = ""
    button: str = "点击继续"


@dataclass
class Edge:
    key: str
    kind: str           # "share" / "buff"
    a: str              # 敌人 key（share: sentinel/ward；buff: ward → sentinel）
    b: str
    color: tuple[int, int, int]
    active: bool = True
    cut: bool = False


@dataclass
class FloatText:
    x: float
    y: float
    message: str
    color: tuple[int, int, int]
    t: float = 0.0
    life: float = 0.9
    size: int = 18
    vy: float = 54.0


@dataclass
class Fx:
    kind: str
    x: float
    y: float
    color: tuple[int, int, int]
    t: float = 0.0
    life: float = 0.6
    radius: float = 60.0
    facing: int = 1
    text: str = ""


@dataclass
class Projectile:
    x: float
    y: float
    target: Any
    damage: float
    color: tuple[int, int, int]
    kind: str = "bubble"
    speed: float = 680.0
    radius: float = 8.0
    life: float = 2.4
    owner: str = ""
    hostile: bool = False


# ---------------------------------------------------------------------------
# 角色 / 敌人
# ---------------------------------------------------------------------------
class Ally:
    def __init__(self, key: str, role: CL.RoleDef, index: int, home: tuple[float, float],
                 rng: random.Random) -> None:
        self.key = key
        self.role = role
        self.index = index
        self.home_x, self.home_y = home
        self.rng = rng
        self.runtime = CL.RoleRuntime(role, index, index, rng)
        self.anim = self.runtime.anim
        self.x, self.y = home
        self.facing = 1
        self.max_hp = ALLY_STATS[key]["hp"]
        self.hp = float(self.max_hp)
        self.shield = 0.0
        self.shield_timer = 0.0
        self.damage = ALLY_STATS[key]["damage"]
        self.attack_range = ALLY_STATS[key]["attack_range"]
        self.attack_interval = ALLY_STATS[key]["attack_interval"]
        self.move_speed = ALLY_STATS[key]["move_speed"]
        self.skill_cd_max = ALLY_STATS[key]["skill_cd"]
        self.attack_cd = rng.uniform(0.2, 0.8)
        self.skill_cd = rng.uniform(2.0, 3.8)
        self.state = "idle"
        self.state_time = 0.0
        self.hit_flash = 0.0
        self.dead_t = 0.0
        self.skill_flash = 0.0
        self.action_speed = 1.0
        self.thumbnail: pygame.Surface | None = None

    @property
    def alive(self) -> bool:
        return self.hp > 0

    @property
    def move_radius(self) -> float:
        return ALLY_RANGE_UI[self.key][0]

    @property
    def attack_range_ui(self) -> float:
        return ALLY_RANGE_UI[self.key][1]

    @property
    def display_name(self) -> str:
        return ALLY_DISPLAY[self.key]["name"]

    @property
    def color(self) -> tuple[int, int, int]:
        return self.role.color if self.role else ALLY_STATS[self.key]["color"]

    def reset_for_wave(self) -> None:
        self.hp = float(self.max_hp)
        self.shield = 0.0
        self.shield_timer = 0.0
        self.attack_cd = 0.4
        self.skill_cd = self.rng.uniform(2.0, 3.6)
        self.state = "idle"
        self.state_time = 0.0
        self.hit_flash = 0.0
        self.dead_t = 0.0
        self.x, self.y = self.home_x, self.home_y
        self.facing = 1
        self.anim.release()


class Enemy:
    def __init__(self, kind: str, x: float, y: float, wave: int) -> None:
        stats = ENEMY_STATS[kind]
        self.kind = kind
        self.key = f"{kind.lower()}_{wave}_{int(x)}_{int(y)}"
        self.wave = wave
        self.x = float(x)
        self.y = float(y)
        self.spawn_x = float(x)
        self.spawn_y = float(y)
        self.max_hp = float(stats["hp"]) * (1.0 + 0.10 * wave)
        self.hp = self.max_hp
        self.damage = stats["damage"]
        self.attack_range = stats["attack_range"]
        self.attack_interval = stats["attack_interval"]
        self.attack_cd = 0.9
        self.speed = stats["speed"]
        self.radius = stats["radius"]
        self.color = stats["color"]
        self.name = stats["name"]
        self.desc = stats["desc"]
        self.facing = -1
        self.state = "move"
        self.hit_flash = 0.0
        self.dead_t = 0.0
        self.bob = random.uniform(0.0, math.tau)
        self.fuse = 0.0
        self.exploded = False
        # 接近 / 攻击追踪（smoke 断言用）
        self.attacked = False
        self.moved_distance = 0.0
        self.min_distance_to_ally = 1e9
        self.spawn_distance = 1e9
        # W3 网络状态
        self.share_active = False
        self.buff_active = False
        self.exposed = False
        self.death_handled = False

    @property
    def alive(self) -> bool:
        return self.hp > 0


# ---------------------------------------------------------------------------
# 主程序
# ---------------------------------------------------------------------------
class TutorialBattle:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.shot_path: Path | None = Path(args.shot) if args.shot else None
        self.shot_time = float(args.time)
        self.smoke_mode = bool(args.smoke)
        self.start_wave = int(getattr(args, "start_wave", 1) or 1)
        self.auto_cut = bool(getattr(args, "auto_cut", False))
        self.seed = int(args.seed)
        self.windowed = bool(args.windowed) or self.shot_path is not None or self.smoke_mode
        self.size = self._parse_size(args.size)

        pygame.display.init()
        pygame.font.init()
        self.window = self._create_window()
        self.painter = Painter(W, H)
        self.painter.set_target(self.window)
        self.clock = pygame.time.Clock()
        self.veil: pygame.Surface | None = None

        self.roles, self.manifest_status = CL.load_roles()
        self.role_by_id = {role.id: role for role in self.roles}
        self.store = CL.ClipStore()
        self.warnings: list[str] = list(self.manifest_status.get("warnings", []))
        self.rng = random.Random(self.seed)

        self.time = 0.0
        self.fps_value = FPS
        self.running = True
        self.paused = False

        self.allies: list[Ally] = []
        self.role_native_height: dict[str, int] = {}
        self.select_thumb_cache: dict[str, pygame.Surface] = {}
        self._build_allies()
        self._preload_idle_move()

        self.enemies: list[Enemy] = []
        self.projectiles: list[Projectile] = []
        self.floats: list[FloatText] = []
        self.fx: list[Fx] = []
        self.edges: list[Edge] = []

        self.phase = "intro"             # intro / wave / clear / defeat / complete
        self.wave_index = 0
        self.wave_time = 0.0
        self.clear_timer = 0.0
        self.banner_text = ""
        self.banner_time = 0.0
        self.cut_unlocked = False
        self.cut_used = False
        self.cut_banner = ""
        self.cut_banner_time = 0.0
        self.cut_drag: list[tuple[float, float]] = []
        self.dragging_cut = False
        self.mouse_logical: tuple[float, float] = (-100.0, -100.0)
        self.hover_continue = False
        self.selected_ally: str | None = None
        self.hover_ally: str | None = None
        self.ally_box_rects: dict[str, pygame.Rect] = {}
        self.enemy_attacks = 0
        self.enemy_attacks_by_wave: dict[int, int] = {0: 0, 1: 0, 2: 0}
        self.enemy_approached_waves: set[int] = set()
        self.enemy_moved_waves: set[int] = set()
        self.stall_timer = 0.0
        self.stalemate_events = 0
        self._enemy_moved_frame = False
        self.enemy_progress_log: list[str] = []
        self.enemy_intro_seen: set[str] = set()
        self.modal_sequence: list[str] = []
        self.modal_freeze_ok = False
        self.modal_resume_ok = False
        self._range_fill_cache: dict[tuple, pygame.Surface] = {}

        self.modal: Modal | None = None
        self.modal_queue: list[Modal] = []
        self.modal_age = 0.0
        self.modals_shown = 0
        self.modal_button_rect = pygame.Rect(0, 0, 0, 0)

        self.basic_attacks = 0
        self.skill_casts = 0
        self.damage_dealt = 0.0
        self.damage_taken = 0.0
        self.kills = 0
        self.waves_cleared = 0
        self.retries = 0
        self.cut_attempts = 0
        self.completed = False
        self.complete_closed = False
        self.banner_timer = 0.0
        # 选角介绍界面（固定 3 人，不做真正选择）
        self.select_hover: str | None = None
        self.select_selected: str | None = None
        self.select_time = 0.0
        self.select_card_rects: dict[str, pygame.Rect] = {}
        self.select_start_rect = pygame.Rect(W // 2 - 200, 952, 400, 62)
        # W3 结算奖励卡（只展示）
        self.reward_cards = [dict(card) for card in REWARD_CARDS]
        self.reward_button_rect = pygame.Rect(W // 2 - 170, 936, 340, 58)
        self.reward_hover = False
        self.reward_screen_seen = False
        # 右侧战斗面板状态（第一关全锁定）
        self.memory_unlocked = False
        self.passive_loaded = False

        if self.shot_path is not None:
            self._prepare_shot_mode()
        else:
            self._prepare_select()

        print(f"[view] window={self.window.get_size()} logical={W}x{H} s={self.painter.s:.3f} "
              f"| {self._sprite_mode_text()}")
        self._report_manifest()

    # -- 初始化 ---------------------------------------------------------
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
        if self.shot_path is not None or self.smoke_mode:
            return pygame.display.set_mode(self.size or DEFAULT_WINDOW)
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
        """源帧 640×360 -> 物理像素；战场角色按 0.75× 源帧再统一缩到约 0.55×，永不上采样。"""
        s = self.painter.s
        base = CL.clamp(min(1.0, (ALLY_FRAME_LOGICAL_W * s) / 640.0,
                            (ALLY_FRAME_LOGICAL_H * s) / 360.0), 0.05, 1.0)
        return CL.clamp(base * FIELD_SPRITE_SCALE, 0.03, 1.0)

    def _sprite_mode_text(self) -> str:
        scale = self.sprite_scale
        if self.painter.s > 4 / 3 + 1e-6:
            return f"sprite {scale:.2f}× (capped, no upsample)"
        return f"sprite {scale:.2f}× source-frame"

    def _setup_label(self, value: str) -> None:
        try:
            pygame.display.set_caption(value)
        except pygame.error:
            pass

    def _report_manifest(self) -> None:
        status = self.manifest_status
        used = [r for r in (self.role_by_id.get(ALLY_MANIFEST_ID[k]) for k in ALLY_ORDER) if r is not None]
        if status.get("from_manifest"):
            print(f"[manifest] OK · {status['count']}/8 roles · used: "
                  + ", ".join(f"{k}->{ALLY_MANIFEST_ID[k]}({r.name})" for k, r in zip(ALLY_ORDER, used)))
            if len(used) < 3:
                print("[manifest] ⚠ 固定队伍中有角色未从 manifest 解析成功（回退 fallback，请同步 Lead）")
        else:
            print(f"[manifest] MISSING ({status.get('error')}) → dsh fallback（会同步 Lead）")
        if self.warnings:
            print(f"[manifest] warnings {len(self.warnings)}:")
            for warning in self.warnings[:8]:
                print("   -", warning)

    def _build_allies(self) -> None:
        for index, key in enumerate(ALLY_ORDER):
            role = self.role_by_id.get(ALLY_MANIFEST_ID[key])
            if role is None:
                raise RuntimeError(f"manifest 缺少角色 {ALLY_MANIFEST_ID[key]}，无法组成固定队伍")
            ally = Ally(key, role, index, ALLY_HOMES[key], random.Random(self.seed + 101 * index))
            self.allies.append(ally)

    def _active_clip_keys(self) -> set[tuple]:
        keys: set[tuple] = set()
        for ally in self.allies:
            if ally.anim.clip is not None:
                keys.add(ally.anim.clip.key)
            if ally.anim.prev_clip is not None:
                keys.add(ally.anim.prev_clip.key)
        return keys

    def _sprite_scale_for(self, ally: Ally) -> float:
        """按「统一目标身高」归一化每个角色的绘制比例：源图里高矮不同的角色，
        在战场上渲染出的像素高度保持一致（脚底锚点由 clip pivot 负责）。"""
        base = self.sprite_scale
        own_height = self.role_native_height.get(ally.key)
        heights = [height for height in self.role_native_height.values() if height > 0]
        if own_height and len(heights) >= 2:
            target_height = sum(heights) / len(heights)
            scale = base * target_height / own_height
            return CL.clamp(scale, base * 0.55, base * 1.65)
        return base

    def _clip_for(self, ally: Ally, action: str) -> CL.Clip | None:
        spec = ally.role.clips.get(action)
        clip = self.store.get(spec, self._sprite_scale_for(ally), self.warnings,
                              context=f"{ally.key}.{action}", protect=self._active_clip_keys())
        return clip

    def _play(self, ally: Ally, action: str, *, loop: bool, fade: float,
              speed: float = 1.0) -> CL.Clip | None:
        clip = self._clip_for(ally, action)
        if clip is None:
            return None
        ally.action_speed = speed
        ally.anim.play(clip, loop=loop, facing=ally.facing, fade=fade, speed=speed)
        return clip

    def _preload_idle_move(self) -> None:
        # 缩略图按物理尺寸缓存；窗口尺寸变化时丢弃旧的缩略图（保留源图 portrait）
        for key in list(self.select_thumb_cache):
            if not (isinstance(key, str) and key.startswith("portrait:")):
                del self.select_thumb_cache[key]
        # 先量出每个角色源图的实际身高（左栏头像也复用这张高分辨率源帧）
        for ally in self.allies:
            self._role_portrait(ally)
        for ally in self.allies:
            for action in ("idle", "move"):
                self._clip_for(ally, action)
        for ally in self.allies:
            clip = self._clip_for(ally, "idle")
            if clip is not None and clip.frames:
                ally.anim.play(clip, loop=True, facing=ally.facing, fade=0.0)
        print(f"[load] 3 roles idle+move lazy-loaded: clips={len(self.store.cache)} "
              f"cache={self.store.bytes_total / 1e6:.1f}MB")

    # -- 波次 / 弹窗 -----------------------------------------------------
    def _enemy_intro_modal(self, kind: str) -> Modal:
        stats = ENEMY_STATS[kind]
        name = stats["name"]
        if kind == "MINION":
            lines = [
                "游标：最基础的近战敌人，血量低。",
                "它会自动选择最近的角色并主动靠近，进入攻击距离后才停下攻击。",
                "本轮目标：击破 2 个游标。",
            ]
        elif kind == "SENTINEL":
            lines = [
                "哨兵：远程敌人，血量较高、移动较慢。",
                "它会主动移动到射程内，然后停下持续射击——不要再等它靠近。",
                "本轮目标：击破 游标 / 哨兵 / 析构炸弹。",
            ]
        elif kind == "BOMB":
            lines = [
                "析构炸弹：会高速接近角色。",
                "它死亡时会爆炸，对附近角色造成范围伤害；尽量让远程角色提前击破它。",
                "本轮目标：击破 游标 / 哨兵 / 析构炸弹。",
            ]
        else:
            lines = [
                "护盾守卫：不主动攻击，会缓慢靠近并给链接目标提供增益/护盾。",
                "金色 BUFF 线为哨兵提供攻击加成与减伤；剪断金线会移除这些增益。",
                "它也是 W3 引用网络的一端：SHARE 会分担哨兵受到的伤害。",
            ]
        return Modal(f"enemy_{kind}", f"新敌人 // {name}", lines, f"enemy_{kind}")

    def _intro_modals(self) -> list[Modal]:
        return [
            Modal("opening", "第一关 // 三固定角色", [
                "Qwen（先锋 / SHIELD）：站前排，吸引火力，小技能为附近友军提供护盾（范围 180）。",
                "DeepSeek（输出 / ATTACK）：远程普攻，小技能打范围爆发。",
                "Claude（支援 / HEAL）：远程支援，小技能回复全队生命。",
                "本关没有大招、没有模块、没有升星、没有商店；角色会自己战斗。",
            ], "roles"),
            Modal("w1", "WAVE 1 // 自动战斗", [
                "角色会自动移动、自动普攻、自动释放小技能。",
                "你不需要点任何按钮，先观察它们的攻击距离与协作。",
                "左侧角色框可选中：蓝色内圈是移动范围（锚定部署点），黄/绿外圈是攻击/支援范围。",
            ], "auto"),
            self._enemy_intro_modal("MINION"),
        ]

    def _modals_for_wave(self, wave: int) -> list[Modal]:
        if wave == 1:
            # W2 首次出现两种新敌人：按 哨兵 → 析构炸弹 顺序各弹一次，不合并
            return [self._enemy_intro_modal("SENTINEL"), self._enemy_intro_modal("BOMB")]
        if wave == 2:
            # W3：新敌人 护盾守卫 → SHARE/BUFF 引用网络 → 断连操作
            return [
                self._enemy_intro_modal("WARD"),
                Modal("w3", "WAVE 3 // 引用网络：SHARE 与 BUFF", [
                    "哨兵 ↔ 护盾守卫之间有两条引用：",
                    "SHARE（青）：伤害共享，哨兵受到的伤害有 40% 转移给护盾守卫。",
                    "BUFF（金）：护盾守卫 → 哨兵提供攻击力 +50%、受伤 -25%（护盾）。",
                    "剪断一条边 = 隔离。失去 SHARE 后哨兵会「暴露」，受到伤害 +40%。",
                ], "network"),
                Modal("cut", "首次解锁 // 断连", [
                    "底部唯一的主动技能「断连」已解锁（W1/W2 时锁定）。",
                    "按住鼠标左键，从一条引用的一侧划过另一侧，即可剪断它。",
                    "只允许剪一次：SHARE 或 BUFF，选一条。",
                ], "cut"),
            ]
        return []

    def _prepare_select(self) -> None:
        """战前固定 3 人选角介绍界面（不可替换）。"""
        self.phase = "select"
        self.modal_queue = []
        self.modal = None
        self.select_hover = None
        self.select_selected = None
        self.select_time = 0.0

    def _start_tutorial(self) -> None:
        if self.phase != "select":
            return
        self._log("enter tutorial from select screen")
        self._prepare_intro()

    def _prepare_intro(self) -> None:
        self.phase = "intro"
        self.wave_index = 0
        self.modal_queue = self._intro_modals()
        self._show_next_modal()

    def _prepare_shot_mode(self) -> None:
        self.modal_queue = []
        if self.start_wave > 1:
            self.phase = "wave"
            self.wave_index = self.start_wave - 1
            self.cut_unlocked = self.start_wave == 3
            self._spawn_wave(self.wave_index)
            self.banner_text = WAVES[self.wave_index]["label"]
            self.banner_time = 1.6
        else:
            self._prepare_select()

    def _show_next_modal(self) -> None:
        while self.modal is None and self.modal_queue:
            modal = self.modal_queue.pop(0)
            if modal.kind.startswith("enemy_"):
                kind = modal.kind[len("enemy_"):]
                if kind in self.enemy_intro_seen:
                    # 每种新敌人只弹一次（重试当前波不重复说明）
                    continue
                self.enemy_intro_seen.add(kind)
            self.modal = modal
            self.modal_age = 0.0
            self.modals_shown += 1
            self.modal_sequence.append(modal.kind)
            self._log(f"modal: {modal.kind}")
            return

    def _continue_modal(self) -> bool:
        if self.modal is None:
            return False
        kind = self.modal.kind
        self.modal = None
        self.modal_age = 0.0
        if kind == "cut":
            self.cut_unlocked = True
            self._log("断连已解锁（W3 只允许一次）")
        elif kind == "defeat":
            self._retry_wave()
        elif kind == "complete":
            self.complete_closed = True
        self._show_next_modal()
        return True

    def _start_wave(self, wave: int) -> None:
        self.wave_index = int(CL.clamp(wave, 0, 2))
        self.phase = "wave"
        self.wave_time = 0.0
        self.clear_timer = 0.0
        self.enemies.clear()
        self.projectiles.clear()
        self.floats.clear()
        self.fx.clear()
        for ally in self.allies:
            ally.reset_for_wave()
        self._spawn_wave(self.wave_index)
        self.banner_text = WAVES[self.wave_index]["label"] + "  //  " + WAVES[self.wave_index]["objective"]
        self.banner_time = 2.2
        self._log(f"start {WAVES[self.wave_index]['label']}")

    def _spawn_wave(self, wave: int) -> None:
        self.edges.clear()
        for kind, x, y in WAVES[wave]["enemies"]:
            enemy = Enemy(kind, x, y, wave)
            self.enemies.append(enemy)
        if wave == 2:
            sentinel = next((e for e in self.enemies if e.kind == "SENTINEL"), None)
            ward = next((e for e in self.enemies if e.kind == "WARD"), None)
            if sentinel is not None and ward is not None:
                sentinel.share_active = True
                sentinel.buff_active = True
                ward.share_active = True
                ward.buff_active = True
                self.edges = [
                    Edge("share", "share", sentinel.key, ward.key, SHARE_CYAN),
                    Edge("buff", "buff", ward.key, sentinel.key, BUFF_GOLD),
                ]
        self._update_network_state()

    def _update_network_state(self) -> None:
        sentinel = next((e for e in self.enemies if e.kind == "SENTINEL" and e.alive), None)
        ward = next((e for e in self.enemies if e.kind == "WARD" and e.alive), None)
        share = next((edge for edge in self.edges if edge.kind == "share"), None)
        buff = next((edge for edge in self.edges if edge.kind == "buff"), None)
        if sentinel is not None:
            sentinel.share_active = bool(share and share.active and ward is not None)
            sentinel.buff_active = bool(buff and buff.active and ward is not None)
        if ward is not None:
            ward.share_active = bool(share and share.active and sentinel is not None)
            ward.buff_active = bool(buff and buff.active and sentinel is not None)

    def _retry_wave(self) -> None:
        self.retries += 1
        self._log(f"retry {WAVES[self.wave_index]['label']}")
        self._start_wave(self.wave_index)

    def _check_wave_state(self) -> None:
        if self.phase != "wave":
            return
        if all(not ally.alive for ally in self.allies):
            self.phase = "defeat"
            self.modal_queue = [Modal("defeat", "全灭 // 重试当前波", [
                "队伍被击倒，但教学关卡不会失败。",
                "点击下方按钮重置角色并重试当前波（不会重复机制说明）。",
            ], "defeat", button="重试当前波")]
            self._show_next_modal()
            return
        if all(not enemy.alive for enemy in self.enemies):
            self.phase = "clear"
            self.clear_timer = 1.6
            self.waves_cleared += 1
            self._log(f"{WAVES[self.wave_index]['label']} cleared")
            self.banner_text = f"{WAVES[self.wave_index]['label']} CLEAR"
            self.banner_time = 1.6

    def _advance_to_next_wave(self) -> None:
        if self.wave_index >= 2:
            self.phase = "result"
            self.completed = True
            self.reward_screen_seen = True
            self.projectiles.clear()
            self.fx.clear()
            self.floats.clear()
            self._log("tutorial complete → reward screen")
            return
        next_wave = self.wave_index + 1
        self.phase = "intro"
        self.modal_queue = self._modals_for_wave(next_wave)
        self._pending_next_wave = next_wave
        for ally in self.allies:
            ally.hp = float(ally.max_hp)
            ally.shield = 0.0
            ally.state = "idle"
            ally.anim.release()
        self._show_next_modal()

    # -- 事件 -----------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            self.running = False
            return
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.running = False
            elif event.key == pygame.K_F11:
                self._toggle_fullscreen()
            elif event.key == pygame.K_r and self.phase in ("wave", "defeat"):
                self._retry_wave()
            return
        if self.phase == "select":
            if event.type == pygame.MOUSEMOTION:
                self.mouse_logical = self._to_logical(event.pos)
                self.select_hover = None
                for key, rect in self.select_card_rects.items():
                    if rect.collidepoint(self.mouse_logical):
                        self.select_hover = key
                        break
                return
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.mouse_logical = self._to_logical(event.pos)
                if self.select_start_rect.collidepoint(self.mouse_logical):
                    self._start_tutorial()
                    return
                for key, rect in self.select_card_rects.items():
                    if rect.collidepoint(self.mouse_logical):
                        self.select_selected = key
                        self.select_hover = key
                        return
                return
            return
        if self.phase == "result":
            if event.type == pygame.MOUSEMOTION:
                self.mouse_logical = self._to_logical(event.pos)
                self.reward_hover = self.reward_button_rect.collidepoint(self.mouse_logical)
                return
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.mouse_logical = self._to_logical(event.pos)
                if self.reward_button_rect.collidepoint(self.mouse_logical):
                    self._finish_tutorial()
                return
            return
        if self.phase == "complete":
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.complete_closed = True
            return
        if event.type == pygame.MOUSEMOTION:
            self.mouse_logical = self._to_logical(event.pos)
            self.hover_continue = bool(self.modal and self.modal_button_rect.collidepoint(self.mouse_logical))
            self.hover_ally = None
            if self.modal is None:
                hovered = self._ally_at(self.mouse_logical)
                if hovered is None:
                    hovered = self._box_at(self.mouse_logical)
                self.hover_ally = hovered.key if hovered is not None else None
            if self.dragging_cut:
                self.cut_drag.append(self.mouse_logical)
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.mouse_logical = self._to_logical(event.pos)
            if self.modal is not None:
                # 点击面板任意位置继续，降低教学卡住概率
                self._continue_modal()
                return
            clicked = self._box_at(self.mouse_logical) or self._ally_at(self.mouse_logical)
            if clicked is not None:
                # 选中/取消选中：只显示一个角色的范围圈
                self.selected_ally = None if self.selected_ally == clicked.key else clicked.key
                if self.selected_ally is not None:
                    self.hover_ally = None
                self._log(f"select ally: {self.selected_ally}")
                return
            if self.cut_unlocked and not self.cut_used and self.phase == "wave":
                if ARENA.collidepoint(self.mouse_logical):
                    self.dragging_cut = True
                    self.cut_drag = [self.mouse_logical]
            return
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.mouse_logical = self._to_logical(event.pos)
            if self.dragging_cut:
                self.cut_drag.append(self.mouse_logical)
                self.dragging_cut = False
                self._try_cut_drag()
            return

    # -- 选中范围圈 -----------------------------------------------------
    def _ally_box_rect(self, index: int) -> pygame.Rect:
        panel = LEFT_PANEL
        box_h = 232
        return pygame.Rect(panel.x + 12, panel.y + 58 + index * (box_h + 12), panel.w - 24, box_h)

    def _box_at(self, pos: tuple[float, float]) -> Ally | None:
        for index, ally in enumerate(self.allies):
            if self._ally_box_rect(index).collidepoint(pos):
                return ally
        return None

    def _ally_at(self, pos: tuple[float, float]) -> Ally | None:
        """战场内悬停检测：按角色当前位置的小体型范围（角色已缩到约 0.55×）。"""
        best: Ally | None = None
        best_distance = 1e9
        for ally in self.allies:
            if not ally.alive:
                continue
            dx = pos[0] - ally.x
            if abs(dx) > 72:
                continue
            if not (ally.y - 150 <= pos[1] <= ally.y + 22):
                continue
            distance = abs(dx) + abs(pos[1] - (ally.y - 70))
            if distance < best_distance:
                best_distance = distance
                best = ally
        return best

    def _range_target(self) -> Ally | None:
        key = None
        if self.hover_ally is not None:
            key = self.hover_ally
        elif self.selected_ally is not None:
            key = self.selected_ally
        if key is None:
            return None
        return next((ally for ally in self.allies if ally.key == key), None)

    def _range_fill(self, radius_px: int, color: tuple[int, int, int]) -> pygame.Surface:
        key = (radius_px, color)
        surface = self._range_fill_cache.get(key)
        if surface is None:
            size = radius_px * 2 + 4
            surface = pygame.Surface((size, size), pygame.SRCALPHA)
            pygame.draw.circle(surface, (*color, 24), (size // 2, size // 2), radius_px)
            self._range_fill_cache[key] = surface
        return surface

    def _range_dashed_circle(self, painter: CL.Painter, center: tuple[float, float],
                             radius: float, color: tuple[int, int, int], width: float = 2,
                             dash_deg: float = 9.0, gap_deg: float = 6.0) -> None:
        if radius <= 2:
            return
        rect = (center[0] - radius, center[1] - radius, radius * 2, radius * 2)
        degree = 0.0
        while degree < 360.0:
            painter.arc(color, rect, math.radians(degree),
                        math.radians(min(360.0, degree + dash_deg)), width)
            degree += dash_deg + gap_deg

    def _draw_range_circles(self, painter: CL.Painter) -> None:
        """选中左侧角色框 / 悬停战场角色时，显示该角色的移动范围（蓝，固定锚点）
        与攻击/支援范围（黄，Claude 绿，跟随当前位置）；同一时间只显示一个角色。"""
        target = self._range_target()
        if target is None or not target.alive:
            return
        selected = self.selected_ally == target.key
        pulse = 1.0 + (0.025 * math.sin(self.time * 5.0) if selected else 0.0)
        # 1) 内圈蓝色：移动范围，锚定在部署点（固定不动）
        move_radius = target.move_radius * pulse
        move_center = (target.home_x, target.home_y)
        move_color = ALLY_RANGE_INNER_COLOR
        fill_px = int(move_radius * painter.s)
        if fill_px > 2:
            fill = self._range_fill(fill_px, move_color)
            painter.surface.blit(fill, (painter.ox + int(round(move_center[0] * painter.s)) - fill_px - 2,
                                        painter.oy + int(round(move_center[1] * painter.s)) - fill_px - 2))
        self._range_dashed_circle(painter, move_center, move_radius, move_color, width=2)
        painter.circle(move_color, move_center, 4)
        move_label_pos = (move_center[0] - move_radius - 8, move_center[1])
        painter.text(f"移动范围 {int(target.move_radius)}", move_label_pos, move_color, 12,
                     right=move_label_pos)
        # 2) 外圈黄色/绿色：攻击/支援范围，跟随角色当前位置
        outer_radius = target.attack_range_ui * pulse
        inner_color = ALLY_RANGE_OUTER_COLOR[target.key]
        outer_center = (target.x, target.y - 110.0)
        fill_px = int(outer_radius * painter.s)
        if fill_px > 2:
            fill = self._range_fill(fill_px, inner_color)
            painter.surface.blit(fill, (painter.ox + int(round(outer_center[0] * painter.s)) - fill_px - 2,
                                        painter.oy + int(round(outer_center[1] * painter.s)) - fill_px - 2))
        self._range_dashed_circle(painter, outer_center, outer_radius, inner_color, width=2)
        label = "支援范围" if target.key == "claude" else (
            "护盾/攻击范围" if target.key == "qwen" else "攻击范围")
        painter.text(f"{label} {int(target.attack_range_ui)}",
                     (outer_center[0] + outer_radius + 8, outer_center[1] - 8),
                     inner_color, 12)
        painter.text(f"{target.display_name} · 范围预览", (target.x, target.y + 34),
                     (200, 216, 228), 12, center=True)

    def _toggle_fullscreen(self) -> None:
        self.windowed = not self.windowed
        try:
            if self.windowed:
                self.window = pygame.display.set_mode(DEFAULT_WINDOW)
            else:
                self.window = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
            old_scale = self.sprite_scale
            self.painter.set_target(self.window)
            new_scale = self.sprite_scale
            if abs(old_scale - new_scale) > 1e-6:
                for ally in self.allies:
                    ally.anim.release()
                self.store.clear()
                self._preload_idle_move()
            self._log(f"window mode: {'windowed' if self.windowed else 'fullscreen'}")
        except pygame.error as exc:
            self._log(f"切换窗口失败: {exc}")

    def _to_logical(self, pos: tuple[int, int]) -> tuple[float, float]:
        x = (pos[0] - self.painter.ox) / max(0.0001, self.painter.s)
        y = (pos[1] - self.painter.oy) / max(0.0001, self.painter.s)
        return (float(x), float(y))

    def _logical_to_window(self, pos: tuple[float, float]) -> tuple[int, int]:
        return self.painter.p(pos)

    # -- 断连 / 引用 ------------------------------------------------
    def _edge_endpoints(self, edge: Edge) -> tuple[tuple[float, float], tuple[float, float]]:
        by_key = {enemy.key: enemy for enemy in self.enemies}
        a = by_key.get(edge.a)
        b = by_key.get(edge.b)
        if a is None or b is None:
            return ((0.0, 0.0), (0.0, 0.0))
        return ((a.x, a.y - 88.0), (b.x, b.y - 88.0))

    def _edge_curve(self, edge: Edge) -> list[tuple[float, float]]:
        (ax, ay), (bx, by) = self._edge_endpoints(edge)
        mx, my = (ax + bx) / 2, (ay + by) / 2
        dx, dy = bx - ax, by - ay
        length = max(1.0, math.hypot(dx, dy))
        nx, ny = -dy / length, dx / length
        bend = 42.0 if edge.kind == "share" else -42.0
        points = []
        for i in range(13):
            t = i / 12
            x = (1 - t) * (1 - t) * ax + 2 * (1 - t) * t * (mx + nx * bend) + t * t * bx
            y = (1 - t) * (1 - t) * ay + 2 * (1 - t) * t * (my + ny * bend) + t * t * by
            points.append((x, y))
        return points

    @staticmethod
    def _point_segment_distance(px: float, py: float, ax: float, ay: float,
                                bx: float, by: float) -> float:
        dx, dy = bx - ax, by - ay
        seg_len2 = dx * dx + dy * dy
        if seg_len2 <= 1e-6:
            return math.hypot(px - ax, py - ay)
        t = CL.clamp(((px - ax) * dx + (py - ay) * dy) / seg_len2, 0.0, 1.0)
        return math.hypot(px - (ax + t * dx), py - (ay + t * dy))

    def _drag_length(self) -> float:
        if len(self.cut_drag) < 2:
            return 0.0
        total = 0.0
        for i in range(1, len(self.cut_drag)):
            x1, y1 = self.cut_drag[i - 1]
            x2, y2 = self.cut_drag[i]
            total += math.hypot(x2 - x1, y2 - y1)
        return total

    def _try_cut_drag(self) -> bool:
        self.cut_attempts += 1
        if not self.cut_unlocked or self.cut_used:
            return False
        if self._drag_length() < 36.0:
            return False
        lines = self.cut_drag
        best: tuple[float, Edge] | None = None
        for edge in self.edges:
            if not edge.active:
                continue
            curve = self._edge_curve(edge)
            for i in range(len(curve) - 1):
                ax, ay = curve[i]
                bx, by = curve[i + 1]
                for point in lines:
                    distance = self._point_segment_distance(point[0], point[1], ax, ay, bx, by)
                    if best is None or distance < best[0]:
                        best = (distance, edge)
        if best is None or best[0] > 38.0:
            self._log("断连未命中引用（拖拽需划过青色/金色连线）")
            return False
        return self._execute_cut(best[1])

    def _execute_cut(self, edge: Edge) -> bool:
        if edge is None or not edge.active or self.cut_used:
            return False
        edge.active = False
        edge.cut = True
        self.cut_used = True
        sentinel = next((e for e in self.enemies if e.kind == "SENTINEL"), None)
        ward = next((e for e in self.enemies if e.kind == "WARD"), None)
        if edge.kind == "share":
            if sentinel is not None:
                sentinel.exposed = True
            self.cut_banner = "SHARE 断开 → 隔离：哨兵暴露，受到伤害 +40%"
            pos = self._enemy_center("SENTINEL")
            if pos is not None:
                self.floats.append(FloatText(pos[0], pos[1] - 40, "SHARE 断开", SHARE_CYAN,
                                             life=1.3, size=22))
        else:
            self.cut_banner = "BUFF 断开 → 哨兵失去攻击加成与护盾减伤"
            pos = self._enemy_center("SENTINEL")
            if pos is not None:
                self.floats.append(FloatText(pos[0], pos[1] - 40, "BUFF 中断", BUFF_GOLD,
                                             life=1.3, size=22))
        self.cut_banner_time = 3.0
        self._add_cut_effect(edge)
        self._update_network_state()
        self._log(f"cut edge: {edge.kind} (只允许一次)")
        return True

    def _enemy_center(self, kind: str) -> tuple[float, float] | None:
        for enemy in self.enemies:
            if enemy.kind == kind and enemy.alive:
                return (enemy.x, enemy.y - 90)
        return None

    def _add_cut_effect(self, edge: Edge) -> None:
        (ax, ay), (bx, by) = self._edge_endpoints(edge)
        mx, my = (ax + bx) / 2, (ay + by) / 2
        self.fx.append(Fx("cut", mx, my, edge.color, life=0.9, radius=70.0))
        self.floats.append(FloatText(mx, my - 20, "×", edge.color, life=1.2, size=34, vy=26.0))

    # -- 战斗更新 -------------------------------------------------------
    def update(self, dt: float) -> None:
        self.banner_time = max(0.0, self.banner_time - dt)
        self.cut_banner_time = max(0.0, self.cut_banner_time - dt)
        if self.modal is not None:
            self.modal_age += dt
            return
        if self.paused:
            return
        if self.phase == "select":
            self.time += dt
            self.select_time += dt
            return
        if self.phase in ("result", "complete"):
            self.time += dt
            return
        self.time += dt
        self._show_next_modal()
        if self.modal is not None:
            return
        if self.phase == "intro":
            pending = getattr(self, "_pending_next_wave", 0)
            if not self.modal_queue and self.modal is None:
                self._pending_next_wave = 0
                self._start_wave(pending)
            return
        if self.phase == "clear":
            self.clear_timer -= dt
            self._update_fx(dt)
            if self.clear_timer <= 0:
                self._advance_to_next_wave()
            return
        if self.phase == "defeat":
            self._update_fx(dt)
            return
        if self.phase == "complete":
            self._update_fx(dt)
            return
        if self.phase != "wave":
            return

        self.wave_time += dt
        for ally in self.allies:
            self._update_ally(ally, dt)
        self._enemy_moved_frame = False
        for enemy in self.enemies:
            self._update_enemy(enemy, dt)
        self._separate()
        self._update_projectiles(dt)
        self._update_fx(dt)
        for ally in self.allies:
            if ally.shield_timer > 0:
                ally.shield_timer = max(0.0, ally.shield_timer - dt)
                if ally.shield_timer <= 0:
                    ally.shield = 0.0
        self._check_stalemate(dt)
        self._check_wave_state()

    def _check_stalemate(self, dt: float) -> None:
        """防卡关：场上还有敌人、没有任何敌人移动、也没有任何敌人近身 → 判定卡住。"""
        alive_enemies = [enemy for enemy in self.enemies if enemy.alive]
        if not alive_enemies:
            self.stall_timer = 0.0
            return
        contact = False
        for enemy in alive_enemies:
            for ally in self.allies:
                if ally.alive and math.hypot(ally.x - enemy.x, ally.y - enemy.y) < 340:
                    contact = True
                    break
            if contact:
                break
        if contact or self._enemy_moved_frame:
            self.stall_timer = 0.0
        else:
            self.stall_timer += dt
            if self.stall_timer > 2.5:
                self.stall_timer = 0.0
                self.stalemate_events += 1
                self.enemy_progress_log.append(
                    f"stalemate suspect at wave={self.wave_index + 1} "
                    f"t={self.time:.1f}s enemies={[e.kind for e in alive_enemies]}")
                self._log("警告：敌人与角色都停住，判定卡关")

    def _update_fx(self, dt: float) -> None:
        for item in self.floats:
            item.t += dt
        self.floats = [item for item in self.floats if item.t < item.life]
        for fx in self.fx:
            fx.t += dt
        self.fx = [fx for fx in self.fx if fx.t < fx.life]

    # -- 角色 AI --------------------------------------------------------
    def _nearest_enemy(self, ally: Ally) -> Enemy | None:
        alive = [enemy for enemy in self.enemies if enemy.alive]
        if not alive:
            return None
        return min(alive, key=lambda enemy: math.hypot(enemy.x - ally.x, enemy.y - ally.y))

    def _update_ally(self, ally: Ally, dt: float) -> None:
        ally.hit_flash = max(0.0, ally.hit_flash - dt)
        ally.skill_flash = max(0.0, ally.skill_flash - dt)
        ally.anim.update(dt)
        if not ally.alive:
            ally.dead_t += dt
            return
        if ally.state == "skill":
            if ally.anim.done:
                ally.state = "idle"
                self._set_anim(ally, "idle")
            return
        target = self._nearest_enemy(ally)
        moving = False
        if target is None:
            if math.hypot(ally.x - ally.home_x, ally.y - ally.home_y) > 26:
                moving = self._move_toward(ally, ally.home_x, ally.home_y, dt)
            if not moving and ally.state != "idle":
                ally.state = "idle"
                self._set_anim(ally, "idle")
            return
        dx = target.x - ally.x
        dy = target.y - ally.y
        distance = math.hypot(dx, dy)
        desired = ally.attack_range * (0.62 if ally.key != "qwen" else 0.82)
        if distance > desired:
            moving = self._move_toward(ally, target.x, target.y, dt)
        elif ally.key != "qwen" and distance < desired * 0.55:
            moving = self._move_toward(ally, ally.x - dx, ally.y - dy, dt)
        if abs(dx) > 4:
            ally.facing = 1 if dx > 0 else -1
        if moving:
            if ally.state != "move":
                ally.state = "move"
                self._set_anim(ally, "move")
        else:
            if ally.state != "idle":
                ally.state = "idle"
                self._set_anim(ally, "idle")
        ally.attack_cd -= dt
        if distance <= ally.attack_range + 12 and ally.attack_cd <= 0:
            ally.attack_cd = ally.attack_interval
            self._ally_attack(ally, target)
        ally.skill_cd -= dt
        if ally.skill_cd <= 0 and target is not None:
            self._ally_skill(ally, target)

    def _set_anim(self, ally: Ally, action: str) -> None:
        clip = self._clip_for(ally, action)
        if clip is None:
            return
        ally.anim.play(clip, loop=True, facing=ally.facing, fade=0.12)

    def _move_toward(self, ally: Ally, x: float, y: float, dt: float) -> bool:
        dx, dy = x - ally.x, y - ally.y
        distance = math.hypot(dx, dy)
        if distance < 4:
            return False
        step = min(distance, ally.move_speed * dt)
        ally.x += dx / distance * step
        ally.y += dy / distance * step
        self._clamp_ally_position(ally)
        return True

    def _clamp_ally_position(self, ally: Ally) -> None:
        """位置限制在战场内与自己的活动带内（三人分带，不互相叠；软分离在带内生效）。"""
        ally.x = CL.clamp(ally.x, BATTLE_RECT.left, BATTLE_RECT.right)
        ally.y = CL.clamp(ally.y, BATTLE_RECT.top, BATTLE_RECT.bottom)
        band = ALLY_BANDS[ally.key]
        ally.x = CL.clamp(ally.x, band.left, band.right)
        ally.y = CL.clamp(ally.y, band.top, band.bottom)

    def _ally_attack(self, ally: Ally, target: Enemy) -> None:
        self.basic_attacks += 1
        color = ALLY_STATS[ally.key]["color"]
        if ally.key == "qwen":
            self._deal_enemy_damage(target, ally.damage, color)
            self.fx.append(Fx("slash", target.x, target.y - 40, color, life=0.35, radius=52,
                              facing=ally.facing))
        else:
            kind = "bubble" if ally.key == "deepseek" else "orb"
            self.projectiles.append(Projectile(
                ally.x, ally.y - 120, target, ally.damage, color, kind=kind,
                speed=720.0, radius=9.0 if kind == "bubble" else 7.0, owner=ally.key,
            ))

    def _ally_skill(self, ally: Ally, target: Enemy) -> None:
        clip = self._clip_for(ally, "skill")
        if clip is None:
            return
        duration = max(1.0, clip.duration)
        speed = max(1.0, duration / 1.6)
        ally.action_speed = speed
        ally.anim.play(clip, loop=False, facing=ally.facing, fade=0.12, speed=speed)
        ally.state = "skill"
        ally.skill_cd = ally.skill_cd_max + 2.0
        ally.skill_flash = 0.6
        self.skill_casts += 1
        if ally.key == "qwen":
            # 先锋的护盾/嘲讽覆盖范围 180：只给处在范围内的友军上盾
            support_range = ally.attack_range
            targets = [other for other in self.allies
                       if other.alive and math.hypot(other.x - ally.x, other.y - ally.y) <= support_range]
            if ally.alive and ally not in targets:
                targets.append(ally)
            for other in targets:
                other.shield = max(other.shield, 46.0)
                other.shield_timer = 5.0
            self.fx.append(Fx("shield_all", ally.x, ally.y - 100, SHARE_CYAN, life=1.1,
                              radius=support_range))
            self.floats.append(FloatText(ally.x, ally.y - 260,
                                         f"护盾 +46 ×{len(targets)}（范围 {int(support_range)}）",
                                         SHARE_CYAN, life=1.2, size=19))
            self._log(f"Qwen 小技能：护盾 {len(targets)} 人（范围 {int(support_range)}）")
        elif ally.key == "deepseek":
            cx, cy = target.x, target.y
            for enemy in self.enemies:
                if enemy.alive and math.hypot(enemy.x - cx, enemy.y - cy) <= 250:
                    self._deal_enemy_damage(enemy, 34.0, PURPLE)
            self.fx.append(Fx("burst", cx, cy - 40, PURPLE, life=0.8, radius=250))
            self.floats.append(FloatText(cx, cy - 150, "范围爆发 34", PURPLE, life=1.2, size=20))
            self._log("DeepSeek 小技能：范围爆发")
        else:
            for other in self.allies:
                if other.alive:
                    heal = other.max_hp * 0.34
                    other.hp = min(other.max_hp, other.hp + heal)
                    self.floats.append(FloatText(other.x, other.y - 230, f"+{int(heal)} HP", GREEN, life=1.0, size=18))
            self.fx.append(Fx("heal_all", ally.x, ally.y - 60, GREEN, life=1.1, radius=200))
            self._log("Claude 小技能：全队回复")

    def _deal_enemy_damage(self, enemy: Enemy, amount: float, color: tuple[int, int, int]) -> None:
        if enemy is None or not enemy.alive:
            return
        amount = float(amount)
        sentinel = enemy if enemy.kind == "SENTINEL" else None
        ward = next((e for e in self.enemies if e.kind == "WARD" and e.alive), None)
        share_edge = next((edge for edge in self.edges if edge.kind == "share"), None)
        # BUFF（金线）：护盾守卫为哨兵提供受伤 -25%
        if sentinel is not None and sentinel.buff_active and self._buff_edge_active():
            amount *= 0.75
        if sentinel is not None and self.wave_index == 2 and share_edge is not None \
                and share_edge.active and ward is not None:
            transferred = amount * 0.40
            direct = amount * 0.60
            if sentinel.exposed:
                direct *= 1.40
            self._apply_enemy_hp(sentinel, direct, color)
            self._apply_enemy_hp(ward, transferred, SHARE_CYAN)
            self.floats.append(FloatText(ward.x, ward.y - 130, "SHARE", SHARE_CYAN, life=0.8, size=15))
            self.damage_dealt += direct + transferred
        else:
            if sentinel is not None and sentinel.exposed:
                amount *= 1.40
            self._apply_enemy_hp(enemy, amount, color)
            self.damage_dealt += amount

    def _apply_enemy_hp(self, enemy: Enemy, amount: float, color: tuple[int, int, int]) -> None:
        if not enemy.alive:
            return
        enemy.hp -= amount
        enemy.hit_flash = 0.16
        self.floats.append(FloatText(enemy.x + random.uniform(-16, 16), enemy.y - 120,
                                     f"-{int(max(1, amount))}", color, life=0.7,
                                     size=18 if amount < 40 else 22))
        if enemy.hp <= 0 and not enemy.death_handled:
            enemy.death_handled = True
            self._on_enemy_death(enemy)

    def _on_enemy_death(self, enemy: Enemy) -> None:
        self.kills += 1
        self.fx.append(Fx("death", enemy.x, enemy.y - 60, enemy.color, life=0.8, radius=enemy.radius * 2))
        self.floats.append(FloatText(enemy.x, enemy.y - 150, f"{enemy.name} 被击破", enemy.color, life=1.2, size=18))
        if enemy.kind == "BOMB":
            # 析构炸弹：死亡时爆炸
            self._bomb_death_explosion(enemy)
        if enemy.kind in ("SENTINEL", "WARD") and self.wave_index == 2:
            for edge in self.edges:
                if edge.active:
                    edge.active = False
                    edge.cut = False
            self._update_network_state()
            self._log(f"{enemy.name} 被击破，引用网络中断")

    # -- 敌人 AI --------------------------------------------------------
    def _distance_to_nearest_ally(self, enemy: Enemy) -> float:
        alive = [ally for ally in self.allies if ally.alive]
        if not alive:
            return 1e9
        return min(math.hypot(ally.x - enemy.x, ally.y - enemy.y) for ally in alive)

    def _update_enemy(self, enemy: Enemy, dt: float) -> None:
        enemy.hit_flash = max(0.0, enemy.hit_flash - dt)
        enemy.bob += dt * 3.0
        if not enemy.alive:
            enemy.dead_t += dt
            return
        alive_allies = [ally for ally in self.allies if ally.alive]
        if not alive_allies:
            return
        # 每帧选最近存活角色；距离 > 攻击距离就持续靠近，<= 攻击距离才停下攻击
        target = min(alive_allies, key=lambda ally: math.hypot(ally.x - enemy.x, ally.y - enemy.y))
        dx = target.x - enemy.x
        dy = target.y - enemy.y
        distance = math.hypot(dx, dy)
        enemy.min_distance_to_ally = min(enemy.min_distance_to_ally, distance)
        enemy.spawn_distance = min(enemy.spawn_distance, distance)
        if abs(dx) > 4:
            enemy.facing = 1 if dx > 0 else -1
        if enemy.attack_range > 0 and distance <= enemy.attack_range + 22:
            self.enemy_approached_waves.add(enemy.wave)
        if enemy.kind == "WARD":
            # 护盾守卫不攻击，但会缓慢靠近角色；移动时引用链视觉跟随
            if distance > 240:
                self._enemy_move_toward(enemy, target.x, target.y, dt)
            return
        if enemy.kind == "BOMB":
            # 快速接近，死亡时爆炸（爆炸在 _on_enemy_death 统一处理）
            if distance > enemy.attack_range:
                self._enemy_move_toward(enemy, target.x, target.y, dt)
            return
        if distance > enemy.attack_range:
            self._enemy_move_toward(enemy, target.x, target.y, dt)
            return
        enemy.attack_cd -= dt
        if enemy.attack_cd <= 0:
            interval = enemy.attack_interval
            damage = enemy.damage
            if enemy.kind == "SENTINEL" and enemy.buff_active and self._buff_edge_active():
                damage *= 1.5
                interval *= 0.75
            enemy.attack_cd = interval
            enemy.attacked = True
            self.enemy_attacks += 1
            self.enemy_attacks_by_wave[enemy.wave] = self.enemy_attacks_by_wave.get(enemy.wave, 0) + 1
            if enemy.kind == "SENTINEL":
                self._enemy_ranged_attack(enemy, target, damage)
            else:
                self._enemy_melee_attack(enemy, target, damage)

    def _buff_edge_active(self) -> bool:
        return any(edge.kind == "buff" and edge.active for edge in self.edges)

    def _enemy_move_toward(self, enemy: Enemy, x: float, y: float, dt: float) -> None:
        dx, dy = x - enemy.x, y - enemy.y
        distance = math.hypot(dx, dy)
        if distance < 2:
            return
        step = min(distance, enemy.speed * dt)
        enemy.x += dx / distance * step
        enemy.y += dy / distance * step
        enemy.x = CL.clamp(enemy.x, BATTLE_RECT.left, BATTLE_RECT.right)
        enemy.y = CL.clamp(enemy.y, BATTLE_RECT.top, BATTLE_RECT.bottom)
        enemy.moved_distance += step
        self.enemy_moved_waves.add(enemy.wave)
        self._enemy_moved_frame = True

    def _enemy_melee_attack(self, enemy: Enemy, target: Ally, damage: float) -> None:
        self._damage_ally(target, damage)
        self.fx.append(Fx("enemy_hit", target.x, target.y - 100, enemy.color, life=0.3, radius=46))

    def _enemy_ranged_attack(self, enemy: Enemy, target: Ally, damage: float) -> None:
        self.projectiles.append(Projectile(
            enemy.x, enemy.y - 110, target, damage, enemy.color, kind="bolt",
            speed=520.0, radius=8.0, life=2.2, owner="enemy", hostile=True,
        ))
        self.fx.append(Fx("enemy_muzzle", enemy.x, enemy.y - 110, enemy.color, life=0.22, radius=24))

    def _bomb_death_explosion(self, enemy: Enemy) -> None:
        if enemy.exploded:
            return
        enemy.exploded = True
        self.fx.append(Fx("explosion", enemy.x, enemy.y - 40, RED, life=0.9, radius=150))
        self.floats.append(FloatText(enemy.x, enemy.y - 150, "析构爆炸!", RED, life=1.0, size=20))
        for ally in self.allies:
            if ally.alive and math.hypot(ally.x - enemy.x, ally.y - enemy.y) <= 150:
                self._damage_ally(ally, enemy.damage)
        self._log("析构炸弹死亡爆炸")

    def _damage_ally(self, ally: Ally, amount: float) -> None:
        if not ally.alive:
            return
        damage = float(amount)
        if ally.shield > 0:
            absorbed = min(ally.shield, damage)
            ally.shield -= absorbed
            damage -= absorbed
        if ally.shield <= 0:
            ally.shield = 0.0
        ally.hp -= damage
        ally.hit_flash = 0.18
        self.damage_taken += max(0.0, damage)
        self.floats.append(FloatText(ally.x + random.uniform(-12, 12), ally.y - 210,
                                     f"-{int(damage)}", RED if damage > 0 else MUTED, life=0.7, size=18))
        if ally.hp <= 0:
            ally.hp = 0.0
            ally.state = "dead"
            self.floats.append(FloatText(ally.x, ally.y - 240, f"{ally.display_name} 失去连接", RED, life=1.4, size=20))
            self._log(f"{ally.display_name} 被击倒")

    def _separate(self) -> None:
        living_allies = [ally for ally in self.allies if ally.alive]
        for _ in range(2):
            for i in range(len(living_allies) - 1):
                for j in range(i + 1, len(living_allies)):
                    a, b = living_allies[i], living_allies[j]
                    dx, dy = b.x - a.x, b.y - a.y
                    distance = math.hypot(dx, dy)
                    if 0.01 < distance < ALLY_MIN_GAP:
                        push = (104 - distance) * 0.5
                        nx, ny = dx / distance, dy / distance
                        a.x -= nx * push
                        a.y -= ny * push
                        b.x += nx * push
                        b.y += ny * push
            for ally in living_allies:
                self._clamp_ally_position(ally)
        living_enemies = [enemy for enemy in self.enemies if enemy.alive]
        for _ in range(2):
            for i in range(len(living_enemies) - 1):
                for j in range(i + 1, len(living_enemies)):
                    a, b = living_enemies[i], living_enemies[j]
                    if a.kind == "WARD" or b.kind == "WARD":
                        continue
                    dx, dy = b.x - a.x, b.y - a.y
                    distance = math.hypot(dx, dy)
                    if 0.01 < distance < 76:
                        push = (76 - distance) * 0.5
                        nx, ny = dx / distance, dy / distance
                        a.x -= nx * push
                        a.y -= ny * push
                        b.x += nx * push
                        b.y += ny * push
            for enemy in living_enemies:
                if enemy.kind == "WARD":
                    continue
                enemy.x = CL.clamp(enemy.x, BATTLE_RECT.left, BATTLE_RECT.right)
                enemy.y = CL.clamp(enemy.y, BATTLE_RECT.top, BATTLE_RECT.bottom)

    def _update_projectiles(self, dt: float) -> None:
        alive_projectiles: list[Projectile] = []
        for projectile in self.projectiles:
            target = projectile.target
            if target is None or not getattr(target, "alive", False):
                continue
            projectile.life -= dt
            if projectile.hostile:
                dx = target.x - projectile.x
                dy = (target.y - 120) - projectile.y
            else:
                dx = target.x - projectile.x
                dy = (target.y - 100) - projectile.y
            distance = math.hypot(dx, dy)
            step = projectile.speed * dt
            if distance <= step + 16 or projectile.life <= 0:
                if projectile.hostile:
                    self._damage_ally(target, projectile.damage)
                    self.fx.append(Fx("pop", target.x, target.y - 110, projectile.color, life=0.3,
                                      radius=26))
                else:
                    self._deal_enemy_damage(target, projectile.damage, projectile.color)
                    self.fx.append(Fx("pop", target.x, target.y - 90, projectile.color, life=0.3,
                                      radius=28))
                continue
            projectile.x += dx / distance * step
            projectile.y += dy / distance * step
            if projectile.life > 0:
                alive_projectiles.append(projectile)
        self.projectiles = alive_projectiles

    # -- 截图 / 运行模式 ------------------------------------------------
    def _save_screenshot(self, path: Path) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            pygame.image.save(self.window, str(path))
            print(f"[shot] {path}")
        except (OSError, pygame.error) as exc:
            print(f"[error] 保存截图失败 {path}: {exc}")

    def _present(self) -> None:
        self._setup_label(f"TUTORIAL BATTLE // {self.window.get_width()}x{self.window.get_height()} "
                          f"// {self._sprite_mode_text()}")
        pygame.display.flip()

    def run(self) -> int:
        try:
            if self.smoke_mode:
                return self._run_smoke()
            if self.shot_path is not None:
                return self._run_shot()
            return self._run_interactive()
        finally:
            CL._FONT_CACHE.clear()
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
            self.draw()
            self._present()
        return 0

    def _run_shot(self) -> int:
        assert self.shot_path is not None
        dt = 1.0 / FPS
        target = max(0.1, self.shot_time)
        auto_cut_done = False
        frames = 0
        while frames < target * FPS:
            if self.phase == "select":
                self._start_tutorial()
                continue
            if self.modal is not None:
                if frames >= 2:
                    self._continue_modal()
                self.draw()
                frames += 1
                continue
            self.update(dt)
            frames += 1
            if self.auto_cut and not auto_cut_done and self.wave_index == 2 \
                    and self.cut_unlocked and not self.cut_used and self.wave_time > 2.0:
                share = next((edge for edge in self.edges if edge.kind == "share"), None)
                if share is not None:
                    self._execute_cut(share)
                    auto_cut_done = True
            self.draw()
        self.fps_value = FPS
        self.draw()
        self._save_screenshot(self.shot_path)
        print(f"SHOT OK {self.shot_path}  physical={self.window.get_size()[0]}x{self.window.get_size()[1]} "
              f"logical={W}x{H} s={self.painter.s:.3f} sprite={self.sprite_scale:.2f} "
              f"phase={self.phase} wave={self.wave_index + 1} cut_used={self.cut_used} "
              f"cache={self.store.bytes_total / 1e6:.1f}MB")
        return 0

    # -- smoke ----------------------------------------------------------
    def _run_smoke(self) -> int:
        print("[smoke] Tutorial Battle 无窗口自检")
        errors: list[str] = []

        def check(condition: bool, message: str) -> None:
            if condition:
                print(f"  ok  {message}")
            else:
                errors.append(message)
                print(f"  FAIL {message}")

        ww, wh = self.window.get_size()
        check((ww, wh) == (2560, 1440), f"默认窗口物理 2560×1440 (got {ww}×{wh})")
        check(abs(self.painter.s - 4 / 3) < 1e-6, f"直绘 s=4/3 (got {self.painter.s:.4f})")
        check(abs(self.sprite_scale - 0.75 * FIELD_SPRITE_SCALE) < 1e-6,
              f"战场角色缩小到 0.75×0.55={0.75 * FIELD_SPRITE_SCALE:.3f}× 源帧 (got {self.sprite_scale:.3f})")
        ids_used = [ALLY_MANIFEST_ID[k] for k in ALLY_ORDER]
        check(all(self.role_by_id.get(rid) is not None for rid in ids_used),
              f"固定队伍 3 角色来自 manifest {ids_used}")
        check(all(self.role_by_id[rid].from_manifest for rid in ids_used),
              "3 角色均非 fallback（全部来自 lab_manifest.json）")
        initial_clips = len(self.store.cache)
        check(initial_clips <= 6, f"启动只 lazy load 3 角色 idle+move（{initial_clips} clips）")
        check(not any(ally.anim.clip is None for ally in self.allies), "3 角色都有 idle 动画")
        # 敌人统一中文名（内部 key 不直接展示）
        expected_names = {"MINION": "游标", "SENTINEL": "哨兵", "BOMB": "析构炸弹", "WARD": "护盾守卫"}
        check(all(ENEMY_STATS[key]["name"] == name for key, name in expected_names.items()),
              f"敌人中文名 {list(expected_names.values())}")
        # 范围圈常量（Lead 追加：Qwen 140/180、DeepSeek 170/260、Claude 150/250）
        check(ALLY_RANGE_UI == {"qwen": (140.0, 180.0), "deepseek": (170.0, 260.0),
                                "claude": (150.0, 250.0)}, f"范围圈常量 {ALLY_RANGE_UI}")
        check(all(inner < outer for inner, outer in ALLY_RANGE_UI.values()),
              "三名角色都是蓝内圈 < 黄/绿外圈（内蓝外黄）")
        check(ALLY_STATS["qwen"]["attack_range"] == 180, "Qwen 护盾/攻击覆盖范围为 180")
        check(ALLY_RANGE_OUTER_COLOR["claude"] == (114, 230, 160), "Claude 外圈为绿色")
        # 战场角色统一视觉身高：源图身高不同 -> 每角色分别缩放，渲染高度一致
        rendered_heights = {}
        for ally in self.allies:
            rendered_heights[ally.key] = self.role_native_height.get(ally.key, 0) * self._sprite_scale_for(ally)
        check(max(rendered_heights.values()) - min(rendered_heights.values()) <= 1.5,
              f"战场角色统一目标身高（{ {k: round(v, 1) for k, v in rendered_heights.items()} }）")
        check(len({round(self._sprite_scale_for(a), 4) for a in self.allies}) > 1,
              "不同源身高的角色使用不同绘制缩放（非统一源系数）")

        shots: list[Path] = []
        modal_shots = {
            "opening": Path("shots/tutorial_modal_opening.png"),
            "enemy_MINION": Path("shots/tutorial_modal_minion.png"),
            "enemy_SENTINEL": Path("shots/tutorial_modal_sentinel.png"),
            "enemy_BOMB": Path("shots/tutorial_modal_bomb.png"),
            "enemy_WARD": Path("shots/tutorial_modal_ward.png"),
            "w3": Path("shots/tutorial_modal_w3_network.png"),
            "cut": Path("shots/tutorial_modal_cut.png"),
        }
        wave_shots = {
            0: Path("shots/tutorial_wave1.png"),
            1: Path("shots/tutorial_wave2.png"),
            2: Path("shots/tutorial_wave3_network.png"),
        }
        range_shots = {
            "qwen": Path("shots/tutorial_range_qwen.png"),
            "deepseek": Path("shots/tutorial_range_deepseek.png"),
            "claude": Path("shots/tutorial_range_claude.png"),
        }
        captured: dict[str, bool] = {}
        cut_second_checked = False
        cut_first_frame = -1
        first_modal_clicked = False
        range_tested = False
        range_select_ok = False
        range_hover_ok = False
        select_tested = False
        select_hover_ok = False
        select_click_ok = False
        select_stage_seen = False
        reward_clicked = False
        reward_screen_seen = False
        min_ally_gap = 1e9
        w1_right_locked = False
        dt = 1.0 / FPS
        total_frames = 12000
        frame = 0
        modal_snapshot: tuple | None = None
        resume_pending = False
        resume_time = 0.0
        while frame < total_frames:
            frame += 1
            # --- 战前选角介绍界面 ---
            if self.phase == "select":
                self.update(dt)
                select_stage_seen = True
                if not select_tested and self.select_time > 0.15:
                    self.draw()
                    select_path = Path("shots/tutorial_select.png")
                    self._save_screenshot(select_path)
                    shots.append(select_path)
                    cards = dict(self.select_card_rects)
                    check(len(cards) == 3, f"选角界面显示 3 张固定角色卡（{list(cards)}）")
                    deepseek_rect = cards.get("deepseek")
                    if deepseek_rect is not None:
                        self.handle_event(pygame.event.Event(
                            pygame.MOUSEMOTION, pos=self._logical_to_window(deepseek_rect.center),
                            rel=(0, 0), buttons=(0, 0, 0)))
                        select_hover_ok = self.select_hover == "deepseek"
                        self.draw()
                        hover_path = Path("shots/tutorial_select_hover.png")
                        self._save_screenshot(hover_path)
                        shots.append(hover_path)
                    claude_rect = cards.get("claude")
                    if claude_rect is not None:
                        self.handle_event(pygame.event.Event(
                            pygame.MOUSEBUTTONDOWN, button=1,
                            pos=self._logical_to_window(claude_rect.center)))
                        select_click_ok = self.select_selected == "claude"
                    # 进入第一关（固定 3 人，不做真正选择）
                    self.handle_event(pygame.event.Event(
                        pygame.MOUSEBUTTONDOWN, button=1,
                        pos=self._logical_to_window(self.select_start_rect.center)))
                    check(self.phase == "intro", "点击『进入第一关』进入教学流程")
                    select_tested = True
                self.draw()
                continue
            if self.phase == "result":
                self.update(dt)
                reward_screen_seen = True
                if not captured.get("result"):
                    captured["result"] = True
                    self.draw()
                    result_path = Path("shots/tutorial_result_rewards.png")
                    self._save_screenshot(result_path)
                    shots.append(result_path)
                if not reward_clicked:
                    self.handle_event(pygame.event.Event(
                        pygame.MOUSEBUTTONDOWN, button=1,
                        pos=self._logical_to_window(self.reward_button_rect.center)))
                    reward_clicked = True
                self.draw()
                continue
            if self.phase == "complete":
                if not captured.get("complete_screen"):
                    captured["complete_screen"] = True
                    self.draw()
                    complete_path = Path("shots/tutorial_complete.png")
                    self._save_screenshot(complete_path)
                    shots.append(complete_path)
                break
            if self.modal is not None:
                self.update(dt)   # 生产路径：时停期间 update 必须冻结战斗
                kind = self.modal.kind
                if modal_snapshot is None:
                    modal_snapshot = (
                        self.time, self.wave_time,
                        tuple((a.x, a.y) for a in self.allies),
                        tuple((e.x, e.y) for e in self.enemies),
                    )
                elif not self.modal_freeze_ok and self.modal_age > 0.06:
                    same = (
                        abs(self.time - modal_snapshot[0]) < 1e-9
                        and abs(self.wave_time - modal_snapshot[1]) < 1e-9
                        and tuple((a.x, a.y) for a in self.allies) == modal_snapshot[2]
                        and tuple((e.x, e.y) for e in self.enemies) == modal_snapshot[3]
                    )
                    if same:
                        self.modal_freeze_ok = True
                path = modal_shots.get(kind)
                if path is not None and str(path) not in captured and self.modal_age > 0.14:
                    captured[str(path)] = True
                    self.draw()
                    self._save_screenshot(path)
                    shots.append(path)
                if self.modal_age > 0.26:
                    if not first_modal_clicked:
                        # 走一次真实鼠标点击按钮路径
                        bx, by = self.modal_button_rect.center
                        pos = self._logical_to_window((bx, by))
                        self.handle_event(pygame.event.Event(
                            pygame.MOUSEBUTTONDOWN, button=1, pos=pos))
                        first_modal_clicked = True
                    else:
                        self._continue_modal()
                    resume_pending = True
                    resume_time = self.time
                    modal_snapshot = None
                self.draw()
                continue
            if resume_pending:
                self.update(dt)
                if self.time > resume_time + 1e-9:
                    self.modal_resume_ok = True
                resume_pending = False
            else:
                self.update(dt)
            living_allies = [ally for ally in self.allies if ally.alive]
            for i in range(len(living_allies)):
                for j in range(i + 1, len(living_allies)):
                    a, b = living_allies[i], living_allies[j]
                    min_ally_gap = min(min_ally_gap, math.hypot(a.x - b.x, a.y - b.y))
            # 选中范围圈：仅显示一个角色（点击左侧小框 / 悬停战场角色）
            if not range_tested and self.phase == "wave" and self.wave_index == 0 and self.wave_time > 0.9:
                box = self._ally_box_rect(0)
                self.handle_event(pygame.event.Event(
                    pygame.MOUSEBUTTONDOWN, button=1,
                    pos=self._logical_to_window(box.center)))
                range_select_ok = self.selected_ally == "qwen"
                self.draw()
                self._save_screenshot(range_shots["qwen"])
                shots.append(range_shots["qwen"])
                deepseek = next(ally for ally in self.allies if ally.key == "deepseek")
                hover_pos = self._logical_to_window((deepseek.x, deepseek.y - 60))
                self.handle_event(pygame.event.Event(
                    pygame.MOUSEMOTION, pos=hover_pos, rel=(0, 0), buttons=(0, 0, 0)))
                range_hover_ok = self.hover_ally == "deepseek"
                self.draw()
                self._save_screenshot(range_shots["deepseek"])
                shots.append(range_shots["deepseek"])
                claude_box = self._ally_box_rect(2)
                self.handle_event(pygame.event.Event(
                    pygame.MOUSEBUTTONDOWN, button=1,
                    pos=self._logical_to_window(claude_box.center)))
                check(self.selected_ally == "claude", "点击 Claude 小框选中范围预览")
                self.draw()
                self._save_screenshot(range_shots["claude"])
                shots.append(range_shots["claude"])
                # 取消选中，避免影响后续
                self.handle_event(pygame.event.Event(
                    pygame.MOUSEBUTTONDOWN, button=1,
                    pos=self._logical_to_window(claude_box.center)))
                range_tested = True
            if self.phase == "wave" and not cut_second_checked and self.cut_used:
                if frame - cut_first_frame > 70:
                    # 尝试第二次剪线：必须被拒绝（只允许一次）
                    buff_edge = next((edge for edge in self.edges if edge.kind == "buff"), None)
                    if buff_edge is not None and buff_edge.active:
                        self._simulate_drag_across_edge(buff_edge)
                        check(self.cut_used and buff_edge.active, "第二次剪线被拒绝（只允许一次）")
                        cut_second_checked = True
            if self.phase == "wave" and not self.cut_used and self.wave_index == 2 \
                    and self.cut_unlocked and self.wave_time > 1.6:
                if not captured.get("wave3_network"):
                    self.draw()
                    self._save_screenshot(wave_shots[2])
                    shots.append(wave_shots[2])
                    captured["wave3_network"] = True
                share = next((edge for edge in self.edges if edge.kind == "share"), None)
                if share is not None and share.active:
                    self._simulate_drag_across_edge(share)
                    check(self.cut_used, "鼠标拖拽滑剪成功剪断一条引用")
                    check(not share.active, "被剪断的 SHARE 引用失活")
                    cut_first_frame = frame
            if self.phase == "wave" and self.wave_index == 0 and self.wave_time > 2.2:
                if not captured.get(0):
                    self.draw()
                    self._save_screenshot(wave_shots[0])
                    shots.append(wave_shots[0])
                    captured[0] = True
                    w1_right_locked = (not self.memory_unlocked and not self.passive_loaded
                                       and not self.cut_unlocked)
            if self.phase == "wave" and self.wave_index == 1 and self.wave_time > 2.2:
                if not captured.get(1):
                    self.draw()
                    self._save_screenshot(wave_shots[1])
                    shots.append(wave_shots[1])
                    captured[1] = True
            if self.cut_used and cut_first_frame > 0 and frame - cut_first_frame > 36:
                cut_path = Path("shots/tutorial_wave3_cut.png")
                if not captured.get("wave3_cut"):
                    self.draw()
                    self._save_screenshot(cut_path)
                    shots.append(cut_path)
                    captured["wave3_cut"] = True
            self.draw()
        timed_out = self.phase != "complete"
        check(not timed_out, f"smoke 在 {total_frames} 帧内完成 3 波（当前 phase={self.phase} wave={self.wave_index + 1}）")
        check(self.waves_cleared == 3, f"3 波全部清空（waves_cleared={self.waves_cleared}）")
        check(self.kills >= 7, f"击破敌人数量 {self.kills} ≥ 7（2+3+2）")
        check(self.basic_attacks > 0, f"角色自动普攻次数 {self.basic_attacks} > 0")
        check(self.skill_casts > 0, f"角色自动小技能次数 {self.skill_casts} > 0")
        check(self.cut_used, "断连使用 1 次")
        check(cut_second_checked, "第二次剪线拒绝路径已验证")
        check(self.completed, "教程完成状态")
        check(self.complete_closed, "完成后点击关闭教程面板")
        check(range_select_ok, "点击左侧 Qwen 小框选中范围预览")
        check(range_hover_ok, "悬停 DeepSeek 角色显示范围预览")
        check(self.selected_ally is None, "再次点击取消范围预览（同一时间只显示一个角色）")
        check(self.modal_freeze_ok, "弹窗期间战斗完全冻结（time/wave_time/角色/敌人位置不变）")
        check(self.modal_resume_ok, "点击继续后战斗恢复更新")
        expected_sequence = ["opening", "w1", "enemy_MINION", "enemy_SENTINEL", "enemy_BOMB",
                             "enemy_WARD", "w3", "cut"]
        check(self.modal_sequence == expected_sequence,
              f"弹窗顺序/次数正确：{self.modal_sequence}")
        check(len(self.modal_sequence) == 8, f"共 8 个机制弹窗（{len(self.modal_sequence)}）")
        check(all(self.modal_sequence.count(f"enemy_{k}") == 1 for k in ENEMY_KINDS),
              "每种新敌人只弹一次")
        check(select_stage_seen, "战前固定 3 人选角介绍界面出现")
        check(select_hover_ok, "悬停选角卡显示范围/定位说明")
        check(select_click_ok, "点击选角卡查看说明（固定 3 人，不做真正选择）")
        check(w1_right_locked, "W1 右侧面板：内存板锁定 / 被动未装载 / 断连 LOCKED")
        check(not self.passive_loaded, "第一关被动栏显示未装载（无被动装配）")
        check(self.selected_ally is None, "范围圈同一时间只显示一个角色")
        check(min_ally_gap >= 40.0, f"三人明显分开（smoke 过程中最小间距 {min_ally_gap:.1f}）")
        band_ok = True
        for ally in self.allies:
            band = ALLY_BANDS[ally.key]
            if not (band.left - 1 <= ally.x <= band.right + 1 and band.top - 1 <= ally.y <= band.bottom + 1):
                band_ok = False
        check(band_ok, "三名角色都在各自独立活动带内")
        check(self.memory_unlocked, "结算后内存系统解锁状态置位")
        check(reward_screen_seen and self.reward_screen_seen, "W3 完成后显示结算奖励界面")
        reward_expected = {
            "攻击协议": ("全体攻击力 +10", [(0, 0), (0, 1), (1, 0)], AMBER),
            "防御协议": ("全体防御力 +10", [(0, 0), (0, 1), (1, 0), (1, 1)], (88, 150, 255)),
        }
        for card in self.reward_cards:
            expected = reward_expected.get(card["name"])
            check(expected is not None
                  and card["effect"] == expected[0]
                  and [tuple(cell) for cell in card["shape"]] == expected[1]
                  and tuple(card["color"]) == expected[2],
                  f"结算被动卡 {card['name']} / {card['effect']} / shape={card['shape']}")
        check({card["name"] for card in self.reward_cards} == {"攻击协议", "防御协议"},
              "结算固定给两张被动卡（攻击协议 / 防御协议）")
        check(self.enemy_attacks_by_wave.get(1, 0) > 0 and self.enemy_attacks_by_wave.get(2, 0) > 0,
              f"W2/W3 敌人均主动进入射程并攻击 "
              f"(attacks by wave={self.enemy_attacks_by_wave})")
        check({1, 2} <= self.enemy_approached_waves,
              f"W2/W3 至少一个敌人从远处进入攻击距离 {sorted(self.enemy_approached_waves)}")
        check({0, 1, 2} <= self.enemy_moved_waves,
              f"三波敌人都有主动移动 {sorted(self.enemy_moved_waves)}")
        check(self.stalemate_events == 0,
              f"没有敌人/角色全体卡住（stalemate_events={self.stalemate_events}）")
        check(len(self.store.cache) <= 14, f"clip 缓存数量 {len(self.store.cache)} 合理")
        check(self.store.bytes_total < 512 * 1024 * 1024,
              f"clip 缓存 {self.store.bytes_total / 1e6:.1f}MB < 512MB")
        final_path = Path("shots/tutorial_smoke_final.png")
        self.draw()
        self._save_screenshot(final_path)
        shots.append(final_path)
        print(f"[smoke] manifest={'loaded' if self.manifest_status.get('from_manifest') else 'fallback'} "
              f"waves={self.waves_cleared} kills={self.kills} basic={self.basic_attacks} "
              f"skills={self.skill_casts} cut={self.cut_used} modals={self.modals_shown} "
              f"enemy_attacks={self.enemy_attacks} approached={sorted(self.enemy_approached_waves)} "
              f"stalemate={self.stalemate_events} cache={self.store.bytes_total / 1e6:.1f}MB "
              f"shots={len(shots)}")
        for path in shots:
            print(f"[smoke] shot {path}")
        if errors:
            print(f"[smoke] FAILED: {len(errors)} 项")
            for error in errors:
                print(f"  - {error}")
            return 1
        print("TUTORIAL BATTLE SMOKE OK")
        return 0

    def _simulate_drag_across_edge(self, edge: Edge) -> None:
        curve = self._edge_curve(edge)
        mid = curve[len(curve) // 2]
        dx = curve[-1][0] - curve[0][0]
        dy = curve[-1][1] - curve[0][1]
        length = max(1.0, math.hypot(dx, dy))
        nx, ny = -dy / length, dx / length
        start = (mid[0] + nx * 52, mid[1] + ny * 52)
        end = (mid[0] - nx * 52, mid[1] - ny * 52)
        start_win = self._logical_to_window(start)
        self.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=start_win))
        steps = 8
        for i in range(1, steps + 1):
            t = i / steps
            point = (start[0] + (end[0] - start[0]) * t, start[1] + (end[1] - start[1]) * t)
            win = self._logical_to_window(point)
            self.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=win, rel=(0, 0), buttons=(1, 0, 0)))
        end_win = self._logical_to_window(end)
        self.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=end_win))

    # -- 绘制 -----------------------------------------------------------
    def _log(self, message: str) -> None:
        # 轻量事件日志：目前仅打印到控制台，避免 UI 过载
        if getattr(self.args, "verbose", False):
            print(f"[log] {message}")

    def draw(self) -> None:
        self.window.fill((0, 0, 0))
        painter = self.painter
        painter.fill(BG, (0, 0, W, H))
        if self.phase == "select":
            self._draw_select_screen(painter)
            return
        self._draw_arena(painter)
        self._draw_range_circles(painter)
        self._draw_network(painter)
        self._draw_battle_units(painter)
        self._draw_projectiles(painter)
        self._draw_fx(painter)
        self._draw_topbar(painter)
        self._draw_left_panel(painter)
        self._draw_right_panel(painter)
        self._draw_bottom_bar(painter)
        self._draw_cut_drag(painter)
        if self.banner_time > 0:
            self._draw_banner(painter)
        if self.cut_banner_time > 0:
            self._draw_cut_banner(painter)
        if self.phase == "result":
            self._draw_result_screen(painter)
        elif self.phase == "complete":
            self._draw_complete_screen(painter)
        if self.modal is not None:
            self._draw_modal(painter)

    # -- 选角界面 / 结算界面 -------------------------------------------
    @staticmethod
    def _wrap_cn(text: str, max_chars: int) -> list[str]:
        lines: list[str] = []
        current = ""
        for char in str(text):
            if len(current) >= max_chars:
                lines.append(current)
                current = ""
            current += char
        if current:
            lines.append(current)
        return lines

    def _role_portrait(self, ally: Ally) -> pygame.Surface | None:
        """从 manifest 源帧单独取一张高分辨率角色图，用于左栏小框/选角卡（不跟战场 0.55× 缩小）。"""
        cached = self.select_thumb_cache.get(f"portrait:{ally.key}")
        if cached is not None:
            return cached
        spec = ally.role.clips.get("idle")
        if spec is None or not spec.path.exists():
            return None
        try:
            sheet = pygame.image.load(str(spec.path)).convert_alpha()
        except pygame.error:
            return None
        columns = max(1, int(spec.columns))
        rows = max(1, int(spec.rows))
        frame_w = max(1, int(spec.frame_w))
        frame_h = max(1, int(spec.frame_h))
        frame_count = min(max(1, int(spec.frame_count)), columns * rows)
        index = int(CL.clamp(int(spec.start), 0, frame_count - 1))
        rect = pygame.Rect((index % columns) * frame_w, (index // columns) * frame_h,
                           frame_w, frame_h)
        try:
            frame = sheet.subsurface(rect)
        except ValueError:
            del sheet
            return None
        bbox = frame.get_bounding_rect()
        if bbox.width <= 2 or bbox.height <= 2:
            bbox = frame.get_rect()
        crop = bbox.inflate(22, 22).clip(frame.get_rect())
        portrait = frame.subsurface(crop).copy()
        del sheet
        self.role_native_height[ally.key] = max(1, bbox.height)
        self.select_thumb_cache[f"portrait:{ally.key}"] = portrait
        return portrait

    def _role_thumbnail(self, ally: Ally, logical_w: float, logical_h: float) -> pygame.Surface | None:
        key = (ally.key, int(logical_w), int(logical_h))
        cached = self.select_thumb_cache.get(key)
        if cached is not None:
            return cached
        portrait = self._role_portrait(ally)
        if portrait is None:
            return None
        target_w = max(1, int(logical_w * self.painter.s))
        target_h = max(1, int(logical_h * self.painter.s))
        frame_w, frame_h = portrait.get_size()
        scale = min(1.0, target_w / frame_w, target_h / frame_h)
        try:
            if scale < 1.0:
                image = pygame.transform.smoothscale(
                    portrait, (max(1, int(frame_w * scale)), max(1, int(frame_h * scale))))
            else:
                image = portrait.copy()
        except pygame.error:
            return None
        self.select_thumb_cache[key] = image
        return image

    def _draw_ally_thumb(self, painter: CL.Painter, ally: Ally,
                         box: pygame.Rect) -> None:
        image = self._role_thumbnail(ally, box.w, box.h)
        if image is None:
            return
        width = int(round(image.get_width() / max(0.0001, painter.s)))
        height = int(round(image.get_height() / max(0.0001, painter.s)))
        painter.blit(image, (box.centerx - width / 2, box.centery - height / 2))

    def _selection_thumbnail(self, ally: Ally) -> pygame.Surface | None:
        return self._role_thumbnail(ally, 154, 186)

    def _draw_range_diagram(self, painter: CL.Painter, ally: Ally, center: tuple[float, float],
                            max_radius: float = 92.0) -> None:
        inner, outer = ALLY_RANGE_UI[ally.key]
        scale = max_radius / max(1.0, inner, outer)
        inner_r = inner * scale
        outer_r = outer * scale
        outer_color = ALLY_RANGE_OUTER_COLOR[ally.key]
        # 低透明填充 + 虚线描边（只做示意，不参与战斗）
        for radius, color in ((inner_r, ALLY_RANGE_INNER_COLOR), (outer_r, outer_color)):
            px = int(radius * painter.s)
            if px > 1:
                fill = self._range_fill(px, color)
                painter.surface.blit(fill, (painter.ox + int(round(center[0] * painter.s)) - px - 2,
                                            painter.oy + int(round(center[1] * painter.s)) - px - 2))
            self._range_dashed_circle(painter, center, radius, color, width=2, dash_deg=10, gap_deg=7)
        painter.circle(ALLY_RANGE_INNER_COLOR, center, 3)
        outer_name = "支援" if ally.key == "claude" else ("护盾/攻击" if ally.key == "qwen" else "攻击")
        painter.text("移动", (center[0], center[1] - inner_r - 12), ALLY_RANGE_INNER_COLOR, 10, center=True)
        painter.text(outer_name,
                     (center[0], center[1] - outer_r - 12), outer_color, 10, center=True)

    def _draw_select_screen(self, painter: CL.Painter) -> None:
        painter.fill(BG, (0, 0, W, H))
        for band in range(16):
            color = CL.blend((8, 12, 18), (17, 27, 39), band / 15)
            painter.fill(color, (0, band * H // 16, W, H // 16 + 1))
        painter.text("内存远征 · 第一关", (W // 2, 40), WHITE, 38, bold=True, center=True)
        painter.text("TUTORIAL // 选角", (W // 2, 92), MUTED, 14, mono=True, center=True)
        card_w, card_h, gap = 440, 540, 36
        total = card_w * 3 + gap * 2
        x0 = (W - total) // 2
        y0 = 138
        self.select_card_rects = {}
        for index, ally in enumerate(self.allies):
            rect = pygame.Rect(x0 + index * (card_w + gap), y0, card_w, card_h)
            self.select_card_rects[ally.key] = rect
            key = ally.key
            color = ALLY_STATS[key]["color"]
            hovered = self.select_hover == key
            selected = self.select_selected == key
            painter.rect((14, 20, 28) if not (hovered or selected) else (18, 27, 37), rect, radius=12)
            border = ALLY_RANGE_INNER_COLOR if selected else (_lighten(color, 40) if hovered else color)
            painter.rect(border, rect, width=3 if (hovered or selected) else 2, radius=12)
            painter.fill(color, (rect.x + 2, rect.y + 16, 5, rect.h - 32))
            # 缩略图
            thumb_box = pygame.Rect(rect.x + 18, rect.y + 18, 154, 186)
            painter.rect((10, 15, 22), thumb_box, radius=8)
            painter.rect(LINE, thumb_box, width=1, radius=8)
            self._draw_ally_thumb(painter, ally, thumb_box)
            painter.text(ally.display_name, (rect.x + 188, rect.y + 18), WHITE, 28, bold=True)
            painter.text(f"{ALLY_DISPLAY[key]['slot']} · {ALLY_DISPLAY[key]['type']}",
                         (rect.x + 188, rect.y + 56), color, 14, mono=True)
            painter.text("固定上场", (rect.right - 16, rect.y + 18), MUTED, 11,
                         right=(rect.right - 16, rect.y + 18))
            desc_lines = self._wrap_cn(ALLY_DISPLAY[key]["intro"], 15)
            line_y = rect.y + 84
            for line in desc_lines[:3]:
                painter.text(line, (rect.x + 188, line_y), TEXT, 14)
                line_y += 22
            # 数值范围
            inner, outer = ALLY_RANGE_UI[key]
            outer_name = "支援" if key == "claude" else ("护盾/攻击" if key == "qwen" else "攻击")
            painter.text(f"移动内圈 {int(inner)}   ·   {outer_name}外圈 {int(outer)}",
                         (rect.x + 18, rect.y + 224), ALLY_RANGE_INNER_COLOR, 13, mono=True)
            painter.text(f"自动：{ALLY_DISPLAY[key]['desc']}", (rect.x + 18, rect.y + 246),
                         ALLY_RANGE_OUTER_COLOR[key], 13)
            self._draw_range_diagram(painter, ally, (rect.centerx, rect.y + 386), max_radius=104)
            painter.text("点击卡片查看说明（不会真的选择/替换）", (rect.centerx, rect.bottom - 20),
                         DIM if not (hovered or selected) else border, 11, center=True)
        # 选中/悬停说明
        focus_key = self.select_selected or self.select_hover
        detail = pygame.Rect(W // 2 - 640, 706, 1280, 186)
        painter.rect((12, 18, 26), detail, radius=10)
        painter.rect(LINE, detail, width=1, radius=10)
        if focus_key is not None:
            ally = next(a for a in self.allies if a.key == focus_key)
            color = ALLY_STATS[focus_key]["color"]
            inner, outer = ALLY_RANGE_UI[focus_key]
            outer_name = "支援" if focus_key == "claude" else ("护盾/攻击" if focus_key == "qwen" else "攻击")
            painter.text(f"{ally.display_name} · {ALLY_DISPLAY[focus_key]['slot']} / "
                         f"{ALLY_DISPLAY[focus_key]['type']}", (detail.x + 24, detail.y + 18),
                         color, 22, bold=True)
            painter.text(ALLY_DISPLAY[focus_key]["intro"], (detail.x + 24, detail.y + 56), TEXT, 16)
            painter.text(f"范围：移动内圈 {int(inner)} · {outer_name}外圈 {int(outer)}   ·   "
                         f"技能类型：{ALLY_DISPLAY[focus_key]['type']}   ·   定位：{ALLY_DISPLAY[focus_key]['slot']}",
                         (detail.x + 24, detail.y + 90), ALLY_RANGE_INNER_COLOR, 14, mono=True)
            painter.text("固定 3 人进入第一关；本关只演示自动战斗与引用网络，不涉及选择/养成。",
                         (detail.x + 24, detail.y + 124), MUTED, 14)
            painter.text(f"内圈（蓝，锚定部署点）：{int(inner)}   外圈（{'绿' if focus_key == 'claude' else '黄'}，跟随角色）：{int(outer)}",
                         (detail.x + 24, detail.y + 152), ALLY_RANGE_OUTER_COLOR[focus_key], 13)
        else:
            painter.text("悬停 / 点击上方角色卡查看定位、技能类型与范围圈说明", (detail.centerx, detail.centery),
                         MUTED, 17, center=True)
            painter.text("Qwen 先锋/护盾 140/180   ·   DeepSeek 输出/攻击 170/260   ·   Claude 支援/治疗 150/250",
                         (detail.centerx, detail.centery + 34), DIM, 13, center=True)
        # 开始按钮
        button = self.select_start_rect
        hovered_button = button.collidepoint(self.mouse_logical) and self.phase == "select"
        painter.rect((20, 34, 44) if hovered_button else (16, 26, 36), button, radius=10)
        painter.rect(ALLY_RANGE_INNER_COLOR, button, width=2, radius=10)
        painter.text("进入第一关  →", button.center, WHITE, 22, bold=True, center=True)

    def _draw_reward_card_grid(self, painter: CL.Painter, card: dict, rect: pygame.Rect) -> None:
        shape = set(map(tuple, card["shape"]))
        color = card["color"]
        cell = 34
        cols = 5
        grid_w = cell * cols
        grid_h = cell * cols
        gx = rect.centerx - grid_w // 2
        gy = rect.y + 116
        painter.text("5×5 内存板（仅预览）", (rect.centerx, gy - 22), DIM, 11, center=True)
        for row in range(cols):
            for col in range(cols):
                cell_rect = pygame.Rect(gx + col * cell, gy + row * cell, cell - 2, cell - 2)
                filled = (col - 1, row - 1) in shape
                painter.rect(color if filled else (22, 28, 36), cell_rect, radius=3)
                painter.rect(color if filled else (38, 48, 60), cell_rect, width=1, radius=3)
                if filled:
                    painter.text("+10", cell_rect.center, (12, 16, 20), 11, center=True, bold=True)
        painter.text(f"形状：{card['shape']}", (rect.centerx, gy + grid_h + 12), MUTED, 11,
                     mono=True, center=True)

    def _draw_reward_card(self, painter: CL.Painter, card: dict, rect: pygame.Rect) -> None:
        color = card["color"]
        painter.rect((14, 20, 28), rect, radius=12)
        painter.rect(color, rect, width=2, radius=12)
        painter.fill(color, (rect.x + 2, rect.y + 16, 5, rect.h - 32))
        painter.text(card["name"], (rect.x + 24, rect.y + 16), WHITE, 26, bold=True)
        painter.text(card["type"], (rect.x + 24, rect.y + 52), color, 13, mono=True)
        painter.text(card["effect"], (rect.x + 24, rect.y + 76), color, 17)
        self._draw_reward_card_grid(painter, card, rect)
        painter.text(card["desc"], (rect.centerx, rect.bottom - 42), DIM, 12, center=True)

    def _draw_result_screen(self, painter: CL.Painter) -> None:
        veil = self.veil
        if veil is None or veil.get_size() != self.window.get_size():
            veil = pygame.Surface(self.window.get_size(), pygame.SRCALPHA)
            self.veil = veil
        veil.fill((3, 6, 11, 210))
        painter.surface.blit(veil, (0, 0))
        panel = pygame.Rect(W // 2 - 700, 104, 1400, 900)
        painter.rect(PANEL, panel, radius=16)
        painter.rect(GREEN, panel, width=3, radius=16)
        painter.fill(GREEN, (panel.x + 20, panel.y + 20, 6, panel.h - 40))
        painter.text("TUTORIAL COMPLETE // 结算", (panel.x + 42, panel.y + 22), GREEN, 13, mono=True)
        painter.text("教程完成 // 第一关", (panel.x + 42, panel.y + 48), WHITE, 34, bold=True)
        painter.text("三波敌人全部击破 · 引用网络教学完成", (panel.x + 42, panel.y + 92), MUTED, 16)
        painter.text("内存系统解锁 · 第二关开始装配", (panel.centerx, panel.y + 132), AMBER, 22,
                     bold=True, center=True)
        card_w, card_h, gap = 600, 560, 48
        total = card_w * 2 + gap
        x0 = panel.centerx - total // 2
        card_y = panel.y + 176
        for index, card in enumerate(self.reward_cards):
            rect = pygame.Rect(x0 + index * (card_w + gap), card_y, card_w, card_h)
            self._draw_reward_card(painter, card, rect)
        painter.text("两个被动协议卡已加入收藏：只展示，不进入 5×5；第二关再接入装配。",
                     (panel.centerx, panel.bottom - 128), TEXT, 15, center=True)
        painter.text(f"击破 {self.kills} · 断连 {'已使用' if self.cut_used else '未使用'} · "
                     f"全灭重试 {self.retries} 次", (panel.centerx, panel.bottom - 100), DIM, 13,
                     center=True)
        button = self.reward_button_rect
        hovered = button.collidepoint(self.mouse_logical) and self.phase == "result"
        painter.rect((22, 38, 30) if hovered else (16, 28, 22), button, radius=10)
        painter.rect(GREEN, button, width=2, radius=10)
        painter.text("结束本关", button.center, WHITE, 22, bold=True, center=True)

    def _finish_tutorial(self) -> None:
        if self.phase != "result":
            return
        self.phase = "complete"
        self.completed = True
        self.complete_closed = True
        self.memory_unlocked = True
        self._log("tutorial finished")

    def _draw_complete_screen(self, painter: CL.Painter) -> None:
        veil = self.veil
        if veil is None or veil.get_size() != self.window.get_size():
            veil = pygame.Surface(self.window.get_size(), pygame.SRCALPHA)
            self.veil = veil
        veil.fill((3, 6, 11, 220))
        painter.surface.blit(veil, (0, 0))
        panel = pygame.Rect(W // 2 - 480, 300, 960, 480)
        painter.rect(PANEL, panel, radius=16)
        painter.rect(GREEN, panel, width=3, radius=16)
        painter.text("TUTORIAL COMPLETE", (panel.centerx, panel.y + 60), GREEN, 18, mono=True, center=True)
        painter.text("第一关完成", (panel.centerx, panel.y + 130), WHITE, 42, bold=True, center=True)
        painter.text("内存系统已解锁，第二关开始装配被动协议", (panel.centerx, panel.y + 196), TEXT, 18,
                     center=True)
        painter.text(f"击破 {self.kills} · 断连 {'已使用' if self.cut_used else '未使用'} · "
                     f"重试 {self.retries} 次", (panel.centerx, panel.y + 244), MUTED, 15, center=True)
        painter.text("按 Esc 退出 · 本关没有内存板 / 升星 / 大招，只有选角介绍与结算奖励",
                     (panel.centerx, panel.y + 306), DIM, 13, center=True)
        painter.text("点击任意位置关闭", (panel.centerx, panel.bottom - 44), MUTED, 14, center=True)

    def _draw_arena(self, painter: CL.Painter) -> None:
        rect = ARENA
        painter.rect(PANEL3, rect, radius=10)
        painter.rect(LINE, rect, width=1, radius=10)
        # 地面/纵深网格
        for y in range(rect.top + 40, rect.bottom, 56):
            painter.line((18, 27, 37), (rect.left + 1, y), (rect.right - 1, y), 1)
        for x in range(rect.left + 40, rect.right, 80):
            painter.line((17, 25, 34), (x, rect.top + 1), (x, rect.bottom - 1), 1)
        # 我方区域极淡底色；敌方区域不再用暗红色块，只留淡边界线/标签
        painter.fill((14, 22, 31), (rect.left + 12, rect.top + 92, 348, rect.height - 124))
        boundary_x = rect.left + 726
        for dash_y in range(rect.top + 96, rect.bottom - 14, 14):
            painter.line((27, 39, 53), (boundary_x, dash_y), (boundary_x, dash_y + 8), 1)
        painter.text("我方区域", (rect.left + 28, rect.top + 18), (44, 62, 78), 12)
        painter.text("敌方区域", (rect.right - 28, rect.top + 18), (44, 62, 78), 12,
                     right=(rect.right - 28, rect.top + 18))
        painter.text("自动战场", (rect.centerx, rect.top + 18), (38, 54, 68), 13, center=True)
        # 两侧装饰柱
        for side_x in (rect.left + 8, rect.right - 8):
            painter.line((30, 44, 58), (side_x, rect.top + 92), (side_x, rect.bottom - 12), 2)

    def _unit_shadow(self, painter: CL.Painter, x: float, y: float, width: float) -> None:
        painter.ellipse((0, 0, 0) if False else (18, 24, 32),
                        (x - width / 2, y - 9, width, 18))

    def _blit_anim(self, painter: CL.Painter, anim: CL.Animator, x: float, y: float,
                   facing: int, alpha: int = 255) -> None:
        clip = anim.clip
        if clip is None:
            return
        surface = anim.current_surface()
        if surface is None:
            return
        pivot = clip.pivot
        flip = facing < 0
        sprite = pygame.transform.flip(surface, True, False) if flip else surface
        px = sprite.get_width() - pivot[0] if flip else pivot[0]
        sx = painter.ox + int(round(x * painter.s)) - int(px)
        sy = painter.oy + int(round(y * painter.s)) - int(pivot[1])
        if alpha < 255:
            sprite = sprite.copy()
            sprite.set_alpha(alpha)
        painter.surface.blit(sprite, (sx, sy))
        if anim.prev_surface is not None and anim.fade > 0 and anim.fade_total > 0 and alpha >= 255:
            ratio = CL.clamp(anim.fade / anim.fade_total, 0.0, 1.0)
            prev = pygame.transform.flip(anim.prev_surface, True, False) if anim.prev_facing < 0 else anim.prev_surface
            prev_pivot = anim.prev_pivot or pivot
            ppx = prev.get_width() - prev_pivot[0] if anim.prev_facing < 0 else prev_pivot[0]
            prev = prev.copy()
            prev.set_alpha(int(alpha * ratio))
            painter.surface.blit(prev, (painter.ox + int(round(x * painter.s)) - int(ppx),
                                        painter.oy + int(round(y * painter.s)) - int(prev_pivot[1])))

    def _draw_battle_units(self, painter: CL.Painter) -> None:
        units: list[tuple[float, str, Any]] = []
        for ally in self.allies:
            units.append((ally.y, "ally", ally))
        for enemy in self.enemies:
            units.append((enemy.y, "enemy", enemy))
        units.sort(key=lambda item: item[0])
        for _y, kind, unit in units:
            if kind == "ally":
                self._draw_ally(painter, unit)
            else:
                self._draw_enemy(painter, unit)
        # 双方血条 / 名字在最上层
        for ally in self.allies:
            self._draw_ally_plate(painter, ally)
        for enemy in self.enemies:
            if enemy.alive:
                self._draw_enemy_plate(painter, enemy)

    def _draw_ally(self, painter: CL.Painter, ally: Ally) -> None:
        if not ally.alive and ally.dead_t > 1.2:
            return
        alpha = 255
        if not ally.alive:
            alpha = int(255 * (1.0 - min(1.0, ally.dead_t / 1.2)))
        self._unit_shadow(painter, ally.x, ally.y, 120)
        self._blit_anim(painter, ally.anim, ally.x, ally.y, ally.facing, alpha=alpha)
        if ally.state == "skill" or ally.skill_flash > 0:
            color = ALLY_STATS[ally.key]["color"]
            r = 86 + 20 * math.sin(self.time * 9)
            painter.circle(CL.tint(color, ally.y - 100, 0.5), (ally.x, ally.y - 100), r, 2)
        if ally.hit_flash > 0:
            painter.circle((255, 200, 200), (ally.x, ally.y - 110), 34, 2)

    def _draw_ally_plate(self, painter: CL.Painter, ally: Ally) -> None:
        width = 118
        x = ally.x - width / 2
        y = ally.y - 148
        if not ally.alive:
            painter.text("失去连接", (ally.x, y + 10), RED, 12, center=True)
            return
        ratio = CL.clamp(ally.hp / ally.max_hp, 0.0, 1.0)
        painter.fill((16, 22, 30), (x, y, width, 7))
        fill = (18, 40, 30) if ratio > 0.5 else ((56, 48, 18) if ratio > 0.25 else (58, 20, 22))
        painter.fill(fill, (x, y, width, 7))
        painter.fill(GREEN if ratio > 0.5 else (AMBER if ratio > 0.25 else RED), (x, y, int(width * ratio), 7))
        painter.rect(LINE, (x, y, width, 7), width=1)
        painter.text(f"{ally.display_name}  {int(ally.hp)}/{ally.max_hp}", (ally.x, y - 14),
                     TEXT, 11, center=True)
        if ally.shield > 0.5:
            painter.text(f"护盾 {int(ally.shield)}", (ally.x, y - 27), SHARE_CYAN, 10, center=True)

    def _draw_enemy(self, painter: CL.Painter, enemy: Enemy) -> None:
        k = ENEMY_DRAW_SCALE
        if not enemy.alive:
            if enemy.dead_t < 0.8:
                painter.text(f"{enemy.name} 已倒下", (enemy.x, enemy.y - 100 * k), enemy.color, 12,
                             center=True)
            return
        self._unit_shadow(painter, enemy.x, enemy.y, enemy.radius * 3.2 * k)
        x, y = enemy.x, enemy.y
        if enemy.kind == "MINION":
            bob = math.sin(enemy.bob) * 2
            points = [(x, y - 66 * k + bob), (x + 28 * k, y - 34 * k + bob),
                      (x, y - 4 * k + bob), (x - 28 * k, y - 34 * k + bob)]
            painter.polygon((66, 24, 26), points)
            painter.polygon(enemy.color, points, width=2)
            painter.circle((255, 200, 190), (x, y - 36 * k + bob), max(2, int(5 * k)))
        elif enemy.kind == "SENTINEL":
            bob = math.sin(enemy.bob * 0.6) * 2
            body = pygame.Rect(x - 42 * k, y - 118 * k + bob, 84 * k, 108 * k)
            painter.rect((52, 34, 20), body, radius=max(3, int(10 * k)))
            painter.rect(enemy.color, body, width=2, radius=max(3, int(10 * k)))
            painter.line(enemy.color, (x - 24 * k, y - 90 * k + bob), (x + 24 * k, y - 90 * k + bob), 2)
            painter.circle((255, 230, 170), (x - 16 * k, y - 66 * k + bob), max(2, int(6 * k)))
            painter.polygon((70, 44, 22),
                            [(x - 44 * k, y - 112 * k + bob), (x + 44 * k, y - 112 * k + bob),
                             (x + 30 * k, y - 130 * k + bob), (x - 30 * k, y - 130 * k + bob)],
                            width=1)
            if enemy.buff_active:
                painter.circle(BUFF_GOLD, (x, y - 70 * k), max(10, int(58 * k)), 2)
                painter.text("增益", (x, y - 142 * k), BUFF_GOLD, 10, center=True)
            if enemy.exposed:
                painter.line(RED, (x - 20 * k, y - 96 * k), (x + 22 * k, y - 52 * k), 2)
                painter.text("暴露", (x + 4 * k, y - 146 * k), RED, 10, center=True)
        elif enemy.kind == "BOMB":
            bob = math.sin(enemy.bob * 2.4) * 2
            radius = int((enemy.radius + 3) * k)
            painter.circle((58, 18, 20), (x, y - 40 * k + bob), radius + 3)
            painter.circle(enemy.color, (x, y - 40 * k + bob), radius)
            painter.circle((255, 200, 160), (x, y - 46 * k + bob), max(2, int(6 * k)))
            fuse_x = x + 14 * k
            painter.line((200, 180, 120), (fuse_x, y - 60 * k + bob),
                         (fuse_x + 10 * k, y - 84 * k + bob), 2)
        else:  # WARD
            bob = math.sin(enemy.bob * 0.7) * 2
            center = (x, y - 84 * k + bob)
            size = 40 * k
            points = [(center[0], center[1] - size), (center[0] + size, center[1]),
                      (center[0], center[1] + size), (center[0] - size, center[1])]
            painter.polygon((18, 40, 48), points)
            painter.polygon(SHARE_CYAN if enemy.share_active else LINE2, points, width=2)
            painter.circle(BUFF_GOLD if enemy.buff_active else (60, 92, 110), center, max(4, int(12 * k)))
            painter.circle((10, 20, 26), center, max(2, int(6 * k)))
            if enemy.share_active:
                painter.text("共享", (x, y - 148 * k), SHARE_CYAN, 10, center=True)

    def _draw_enemy_plate(self, painter: CL.Painter, enemy: Enemy) -> None:
        k = ENEMY_DRAW_SCALE
        width = (118 if enemy.kind != "SENTINEL" else 132) * k
        x = enemy.x - width / 2
        y = enemy.y - (172 if enemy.kind == "SENTINEL" else 150) * k
        ratio = CL.clamp(enemy.hp / enemy.max_hp, 0.0, 1.0)
        painter.fill((18, 22, 28), (x, y, width, 6))
        painter.fill(RED, (x, y, int(width * ratio), 6))
        painter.rect(LINE, (x, y, width, 6), width=1)
        painter.text(f"{enemy.name}", (enemy.x, y - 13), enemy.color, 10, center=True)

    def _draw_network(self, painter: CL.Painter) -> None:
        if self.wave_index != 2 or not self.edges:
            return
        for edge in self.edges:
            curve = self._edge_curve(edge)
            color = edge.color
            if edge.active:
                for i in range(len(curve) - 1):
                    painter.line(color, curve[i], curve[i + 1], 3)
                # 流动光点
                t = (self.time * 0.8) % 1.0
                for offset in (0.0, 0.5):
                    pos = (t + offset) % 1.0
                    idx = int(pos * (len(curve) - 1))
                    painter.circle((255, 255, 255), curve[idx], 4)
                mid = curve[len(curve) // 2]
                label = "SHARE 共享" if edge.kind == "share" else "BUFF 增益"
                label_offset = -34 if edge.kind == "share" else 24
                painter.text(label, (mid[0], mid[1] + label_offset), color, 13, center=True)
                self._draw_arrow_heads(painter, edge, curve, color)
            else:
                # 断开的引用：虚线 + ×
                for i in range(0, len(curve) - 1, 2):
                    painter.line((70, 76, 84), curve[i], curve[i + 1], 2)
                mid = curve[len(curve) // 2]
                painter.line((160, 80, 84), (mid[0] - 12, mid[1] - 12), (mid[0] + 12, mid[1] + 12), 3)
                painter.line((160, 80, 84), (mid[0] - 12, mid[1] + 12), (mid[0] + 12, mid[1] - 12), 3)
                label = "SHARE 已断" if edge.kind == "share" else "BUFF 已断"
                painter.text(label, (mid[0], mid[1] + 24), (150, 120, 120), 12, center=True)

    def _draw_arrow_heads(self, painter: CL.Painter, edge: Edge, curve: list[tuple[float, float]],
                          color: tuple[int, int, int]) -> None:
        def arrow(tip: tuple[float, float], prev: tuple[float, float]) -> None:
            dx, dy = tip[0] - prev[0], tip[1] - prev[1]
            length = max(1.0, math.hypot(dx, dy))
            ux, uy = dx / length, dy / length
            px, py = -uy, ux
            painter.polygon(color, [
                tip,
                (tip[0] - ux * 14 + px * 7, tip[1] - uy * 14 + py * 7),
                (tip[0] - ux * 14 - px * 7, tip[1] - uy * 14 - py * 7),
            ])
        if edge.kind == "share":
            arrow(curve[1], curve[0])
            arrow(curve[-2], curve[-1])
        else:
            arrow(curve[-2], curve[-3])

    # -- 绘制：UI -------------------------------------------------------
    def _draw_topbar(self, painter: CL.Painter) -> None:
        painter.fill(PANEL, (0, 0, W, TOPBAR_H))
        painter.fill(PANEL2, (0, 0, W, 64))
        painter.line(LINE, (0, TOPBAR_H - 1), (W, TOPBAR_H - 1))
        painter.fill(CYAN, (0, 0, 8, 64))
        painter.text("内存远征 · 第一关", (34, 8), WHITE, 28, bold=True)
        painter.text(f"TUTORIAL // WAVE {max(1, min(3, self.wave_index + 1))}/3",
                     (36, 52), MUTED, 13, mono=True)
        wave_label = WAVES[self.wave_index]["label"] if 0 <= self.wave_index < 3 else "WAVE"
        phase_label = {"intro": "准备", "wave": "战斗中", "clear": "波次结算",
                       "defeat": "全灭", "result": "结算", "complete": "完成"}.get(self.phase, self.phase)
        painter.text(f"{wave_label}  ·  {phase_label}", (W // 2, 10), CYAN, 20,
                     bold=True, center=True)
        # 顶部目标条：教程目标 / W3 引用图例（不再占用右侧面板）
        wave = WAVES[self.wave_index] if 0 <= self.wave_index < 3 else WAVES[0]
        painter.text("目标：" + wave["objective"], (W // 2, 38), TEXT, 15, center=True)
        if self.wave_index == 2 and self.phase in ("wave", "clear", "intro"):
            share = next((edge for edge in self.edges if edge.kind == "share"), None)
            buff = next((edge for edge in self.edges if edge.kind == "buff"), None)
            share_state = "生效" if (share is not None and share.active) else "已断"
            buff_state = "生效" if (buff is not None and buff.active) else "已断"
            painter.text("SHARE 共享", (W // 2 - 330, 66), SHARE_CYAN, 13)
            painter.text(share_state, (W // 2 - 224, 66),
                         SHARE_CYAN if share_state == "生效" else DIM, 13)
            painter.text("BUFF 增益", (W // 2 - 150, 66), BUFF_GOLD, 13)
            painter.text(buff_state, (W // 2 - 48, 66),
                         BUFF_GOLD if buff_state == "生效" else DIM, 13)
            cut_hint = "断连已使用（只允许一次）" if self.cut_used else "拖拽划过连线 = 断连（一次）"
            painter.text(cut_hint, (W // 2 + 40, 66), SHARE_CYAN if not self.cut_used else DIM, 13)
        else:
            painter.text("首次出现的新机制 / 敌人 / 操作会时停说明 · 点击继续", (W // 2, 66),
                         DIM, 12, center=True)
        painter.text(f"FPS {self.fps_value:5.1f}", (W - 30, 10), GREEN if self.fps_value > 50 else AMBER,
                     16, mono=True, right=(W - 30, 10))
        painter.text("自动战斗 · 无手动攻击", (W - 30, 34), MUTED, 12, right=(W - 30, 34))
        if self.modal is not None:
            painter.text("时停 // 机制说明", (W - 30, 58), AMBER, 12, right=(W - 30, 58))
        else:
            painter.text("点击左侧角色框 / 悬停角色查看范围圈", (W - 30, 58), DIM, 11,
                         right=(W - 30, 58))

    def _draw_left_panel(self, painter: CL.Painter) -> None:
        panel = LEFT_PANEL
        painter.rect(PANEL, panel, radius=10)
        painter.rect(LINE, panel, width=1, radius=10)
        painter.text("队伍 // 固定 3 人", (panel.x + 16, panel.y + 12), MUTED, 13, mono=True)
        painter.text("固定队伍 · 无替换", (panel.x + 16, panel.y + 32), DIM, 12)
        box_h = 232
        for index, ally in enumerate(self.allies):
            box = self._ally_box_rect(index)
            color = ALLY_STATS[ally.key]["color"]
            is_selected = self.selected_ally == ally.key
            is_hovered = self.hover_ally == ally.key
            painter.rect(PANEL3 if ally.alive else (18, 16, 20), box, radius=8)
            border_color = ALLY_RANGE_INNER_COLOR if is_selected and ally.alive else (
                _lighten(color, 36) if is_hovered and ally.alive else (color if ally.alive else (60, 48, 52)))
            painter.rect(border_color, box, width=2, radius=8)
            painter.fill(border_color if ally.alive else (60, 48, 52), (box.x + 2, box.y + 12, 4, box.h - 24))
            # 选中提示
            if is_selected:
                painter.text("范围预览", (box.right - 12, box.y + 12), ALLY_RANGE_INNER_COLOR, 10,
                             mono=True, right=(box.right - 12, box.y + 12))
            elif is_hovered:
                painter.text("悬停", (box.right - 12, box.y + 12), _lighten(color, 36), 10,
                             mono=True, right=(box.right - 12, box.y + 12))
            # 缩略图
            thumb_rect = pygame.Rect(box.x + 14, box.y + 16, 76, 96)
            painter.rect((12, 18, 26), thumb_rect, radius=6)
            painter.rect(LINE, thumb_rect, width=1, radius=6)
            self._draw_ally_thumb(painter, ally, thumb_rect)
            painter.text(ally.display_name, (box.x + 104, box.y + 14), WHITE, 20, bold=True)
            painter.text(f"{ALLY_DISPLAY[ally.key]['slot']} · {ALLY_DISPLAY[ally.key]['type']}",
                         (box.x + 104, box.y + 40), color, 12, mono=True)
            painter.text(ALLY_DISPLAY[ally.key]["desc"], (box.x + 104, box.y + 58), MUTED, 11)
            # HP 条
            ratio = CL.clamp(ally.hp / ally.max_hp, 0.0, 1.0)
            bar = pygame.Rect(box.x + 14, box.y + 124, box.w - 28, 14)
            painter.fill((20, 26, 34), bar)
            hp_color = GREEN if ratio > 0.5 else (AMBER if ratio > 0.25 else RED)
            painter.fill(hp_color, (bar.x, bar.y, int(bar.w * ratio), bar.h))
            painter.rect(LINE, bar, width=1)
            painter.text(f"HP {int(ally.hp)} / {ally.max_hp}", (box.x + 14, box.y + 142), TEXT, 12, mono=True)
            if ally.shield > 0.5:
                painter.text(f"护盾 {int(ally.shield)}", (box.x + 158, box.y + 142), SHARE_CYAN, 12, mono=True)
            state_text = {
                "idle": "待机", "move": "移动", "skill": "小技能", "dead": "失去连接",
            }.get(ally.state, ally.state)
            if not ally.alive:
                state_color = RED
            elif ally.state == "skill":
                state_color = color
            else:
                state_color = MUTED
            painter.text(f"状态：{state_text}", (box.x + 14, box.y + 166), state_color, 12)
            skill_ready = ally.skill_cd <= 0
            painter.text(f"小技能 {'就绪' if skill_ready else f'{ally.skill_cd:4.1f}s'}",
                         (box.x + 14, box.y + 186), GREEN if skill_ready else DIM, 12, mono=True)
            if not ally.alive:
                painter.text("KO · 本波自动重试", (box.x + 14, box.y + 206), RED, 13)

    def _draw_right_panel(self, painter: CL.Painter) -> None:
        panel = RIGHT_PANEL
        painter.rect(PANEL, panel, radius=10)
        painter.rect(LINE, panel, width=1, radius=10)
        painter.text("战斗面板 // 第一关", (panel.x + 16, panel.y + 12), MUTED, 13)
        y = panel.y + 40
        # ---------------- 内存板 ----------------
        painter.text("内存板", (panel.x + 16, y), TEXT, 16, bold=True)
        painter.text("5 × 5", (panel.right - 16, y + 2), DIM, 12, mono=True,
                     right=(panel.right - 16, y + 2))
        board_cell = 36
        board_gap = 4
        board_side = 5 * board_cell + 4 * board_gap
        bx = panel.centerx - board_side // 2
        by = y + 28
        for row in range(5):
            for col in range(5):
                cell = pygame.Rect(bx + col * (board_cell + board_gap),
                                   by + row * (board_cell + board_gap), board_cell, board_cell)
                painter.rect((17, 22, 30), cell, radius=5)
                painter.rect((38, 48, 60), cell, width=1, radius=5)
        # 锁图标 + 锁定说明（第一关全部锁定）
        cx, cy = bx + board_side // 2, by + board_side // 2
        lock_color = (120, 136, 152)
        painter.rect((10, 15, 22), (cx - 34, cy - 34, 68, 68), radius=10)
        painter.rect((60, 74, 90), (cx - 34, cy - 34, 68, 68), width=1, radius=10)
        painter.rect(lock_color, (cx - 26, cy - 4, 52, 42), radius=5)
        painter.line(lock_color, (cx - 16, cy - 4), (cx - 16, cy - 26), 3)
        painter.line(lock_color, (cx - 16, cy - 26), (cx + 16, cy - 26), 3)
        painter.line(lock_color, (cx + 16, cy - 26), (cx + 16, cy - 4), 3)
        painter.circle((10, 15, 22), (cx, cy + 14), 6)
        painter.text("第一关未解锁", (panel.centerx, by + board_side + 18), AMBER, 14, center=True)
        painter.text("全部锁定 · 第二关开始装配", (panel.centerx, by + board_side + 38), DIM, 11,
                     center=True)
        y = by + board_side + 62
        painter.line(LINE, (panel.x + 16, y), (panel.right - 16, y))
        y += 12
        # ---------------- 主动 / ACTIVE ----------------
        painter.text("主动 / ACTIVE", (panel.x + 16, y), MUTED, 13)
        item = pygame.Rect(panel.x + 16, y + 24, panel.w - 32, 62)
        if not self.cut_unlocked:
            state_text, state_color = "LOCKED", (150, 108, 108)
            sub_text = "WAVE 3 解锁"
        elif not self.cut_used:
            state_text, state_color = "CD 0.0s", GREEN
            sub_text = "拖拽划过引用连线 / 只允许一次"
        else:
            state_text, state_color = "已使用", DIM
            sub_text = "本关断连已消耗"
        painter.rect(PANEL3, item, radius=8)
        painter.rect(SHARE_CYAN if self.cut_unlocked and not self.cut_used else LINE,
                     item, width=1, radius=8)
        # 剪刀图标
        ix, iy = item.x + 30, item.centery
        icon_color = SHARE_CYAN if self.cut_unlocked and not self.cut_used else (90, 100, 112)
        painter.line(icon_color, (ix - 10, iy - 10), (ix + 8, iy + 8), 2)
        painter.line(icon_color, (ix - 10, iy + 10), (ix + 8, iy - 8), 2)
        painter.circle(icon_color, (ix - 13, iy - 12), 4, 1)
        painter.circle(icon_color, (ix - 13, iy + 12), 4, 1)
        painter.text("断连", (item.x + 54, item.y + 10), TEXT, 18, bold=True)
        painter.text(sub_text, (item.x + 54, item.y + 36), DIM, 11)
        painter.text(state_text, (item.right - 14, item.centery), state_color, 14,
                     mono=True, right=(item.right - 14, item.centery))
        y = item.bottom + 18
        painter.line(LINE, (panel.x + 16, y), (panel.right - 16, y))
        y += 12
        # ---------------- 被动 / PASSIVE ----------------
        painter.text("被动 / PASSIVE", (panel.x + 16, y), MUTED, 13)
        passive = pygame.Rect(panel.x + 16, y + 24, panel.w - 32, 62)
        painter.rect(PANEL3, passive, radius=8)
        painter.rect(LINE, passive, width=1, radius=8)
        painter.text("未装载", (passive.x + 16, passive.y + 10), DIM, 18, bold=True)
        painter.text("第一关没有内存板 / 被动装配", (passive.x + 16, passive.y + 36), DIM, 11)
        painter.text("LOCKED", (passive.right - 14, passive.centery), (120, 128, 138), 12,
                     mono=True, right=(passive.right - 14, passive.centery))
        y = passive.bottom + 22
        painter.text("结算后展示被动协议卡；第二关再接入 5×5", (panel.x + 16, y), DIM, 11)
        painter.text("范围圈：点击左侧角色框 / 悬停角色查看", (panel.x + 16, y + 18), DIM, 11)
        painter.text("本关仅 1 个主动 · 无大招 / 无升星 / 无商店", (panel.x + 16, y + 36), DIM, 11)

    def _draw_bottom_bar(self, painter: CL.Painter) -> None:
        painter.fill(PANEL, (0, BOTTOM_Y, W, H - BOTTOM_Y))
        painter.line(LINE, (0, BOTTOM_Y), (W, BOTTOM_Y))
        # 波次进度
        painter.text(f"WAVE {self.wave_index + 1} / 3", (36, BOTTOM_Y + 22), MUTED, 14, mono=True)
        for index in range(3):
            done = index < self.waves_cleared
            color = GREEN if done else (CYAN if index == self.wave_index else DIM)
            painter.rect(color, (36 + index * 64, BOTTOM_Y + 52, 54, 8), radius=3)
        painter.text(f"击破 {self.kills}  ·  重试 {self.retries}", (36, BOTTOM_Y + 76), DIM, 12, mono=True)
        # 唯一的主动技能槽：断连
        slot = pygame.Rect(W // 2 - 230, BOTTOM_Y + 16, 460, 104)
        if self.cut_unlocked and not self.cut_used:
            border = SHARE_CYAN
            fill = (14, 30, 36)
            title = "断连"
            state = "就绪 · 拖拽划过引用连线"
            state_color = SHARE_CYAN
        elif self.cut_used:
            border = (86, 92, 100)
            fill = (18, 22, 28)
            title = "断连"
            state = "已使用 · 本关只允许一次"
            state_color = DIM
        else:
            border = LINE
            fill = PANEL3
            title = "断连"
            state = "锁定 · WAVE 3 解锁" if self.wave_index < 2 else "锁定 · 完成网络说明后解锁"
            state_color = DIM
        painter.rect(fill, slot, radius=10)
        painter.rect(border, slot, width=2, radius=10)
        # 剪刀图标（两条交叉线 + 两个圆）
        cx, cy = slot.x + 48, slot.centery
        painter.line(border, (cx - 16, cy - 16), (cx + 12, cy + 12), 2)
        painter.line(border, (cx - 16, cy + 16), (cx + 12, cy - 12), 2)
        painter.circle(border, (cx - 20, cy - 18), 6, 1)
        painter.circle(border, (cx - 20, cy + 18), 6, 1)
        painter.text(title, (slot.x + 86, slot.y + 22), WHITE if border != LINE else MUTED, 24, bold=True)
        painter.text("唯一主动 · 无大招 / 无模块", (slot.x + 86, slot.y + 52), DIM, 12)
        painter.text(state, (slot.x + 86, slot.y + 74), state_color, 14)
        painter.text("W3 只允许剪一次", (slot.right - 16, slot.y + 74), DIM, 11,
                     right=(slot.right - 16, slot.y + 74))
        # 右侧提示
        painter.text("自动战斗 · 无手动普攻", (W - 36, BOTTOM_Y + 22), MUTED, 13, right=(W - 36, BOTTOM_Y + 22))
        painter.text("首次机制均有时停弹窗；全灭不惩罚", (W - 36, BOTTOM_Y + 44), DIM, 12,
                     right=(W - 36, BOTTOM_Y + 44))
        painter.text("Esc 退出 · F11 全屏/窗口", (W - 36, BOTTOM_Y + 66), DIM, 12,
                     right=(W - 36, BOTTOM_Y + 66))

    def _draw_projectiles(self, painter: CL.Painter) -> None:
        for projectile in self.projectiles:
            color = projectile.color
            radius = projectile.radius
            if projectile.kind == "bubble":
                painter.circle(CL.tint(color, projectile.y, 0.35), (projectile.x, projectile.y), radius + 5, 2)
                painter.circle(color, (projectile.x, projectile.y), radius)
                painter.circle((240, 250, 255), (projectile.x - 2, projectile.y - 3), 2)
            elif projectile.kind == "orb":
                painter.circle(CL.tint(color, projectile.y, 0.35), (projectile.x, projectile.y), radius + 6, 2)
                painter.circle(color, (projectile.x, projectile.y), radius)
                painter.line((230, 255, 235), (projectile.x, projectile.y - 5), (projectile.x, projectile.y + 5), 2)
                painter.line((230, 255, 235), (projectile.x - 5, projectile.y), (projectile.x + 5, projectile.y), 2)
            elif projectile.kind == "bolt":
                painter.line(CL.tint(color, projectile.y, 0.4), (projectile.x - 16, projectile.y),
                             (projectile.x + 16, projectile.y), 3)
                painter.circle(color, (projectile.x + 12, projectile.y), radius)
                painter.circle((255, 240, 200), (projectile.x + 12, projectile.y), 3)

    def _draw_fx(self, painter: CL.Painter) -> None:
        for fx in self.fx:
            p = CL.clamp(fx.t / max(0.001, fx.life), 0.0, 1.0)
            color = fx.color
            if fx.kind == "slash":
                facing = fx.facing
                r = fx.radius
                start = -0.8 if facing > 0 else math.pi - 0.8
                painter.arc(color, (fx.x - r, fx.y - r, r * 2, r * 2), start, start + 1.6, 4)
            elif fx.kind in ("burst", "explosion", "shield_all", "heal_all"):
                radius = fx.radius * (0.3 + 0.7 * p)
                alpha_color = CL.tint(color, fx.y, 0.35 * (1 - p))
                painter.circle(alpha_color, (fx.x, fx.y - 30), radius, 2)
                if fx.kind == "explosion":
                    painter.circle(color, (fx.x, fx.y - 30), radius * 0.7, 2)
            elif fx.kind == "cut":
                radius = fx.radius * (0.4 + 0.8 * p)
                painter.circle(color, (fx.x, fx.y), radius, 3)
                for index in range(6):
                    angle = math.tau * index / 6 + p * 2
                    painter.line(color, (fx.x, fx.y),
                                 (fx.x + math.cos(angle) * radius, fx.y + math.sin(angle) * radius), 2)
            elif fx.kind == "enemy_hit":
                painter.circle((255, 180, 170), (fx.x, fx.y - 100), fx.radius * (1 - p) + 6, 2)
            elif fx.kind == "death":
                radius = fx.radius * (0.4 + 0.8 * p)
                painter.circle((90, 70, 70), (fx.x, fx.y - 30), radius, 2)
            elif fx.kind == "pop":
                painter.circle(color, (fx.x, fx.y - 90), fx.radius * (1 - p) + 3, 2)
        for item in self.floats:
            p = CL.clamp(item.t / max(0.001, item.life), 0.0, 1.0)
            alpha = int(255 * (1.0 - p * p))
            painter.text(item.message, (item.x, item.y - item.vy * p), item.color,
                         item.size, center=True, alpha=alpha)

    def _draw_cut_drag(self, painter: CL.Painter) -> None:
        if len(self.cut_drag) < 2:
            return
        for i in range(1, len(self.cut_drag)):
            painter.line((255, 255, 255), self.cut_drag[i - 1], self.cut_drag[i], 3)
        painter.circle(SHARE_CYAN, self.cut_drag[-1], 8, 2)
        painter.text("滑剪", (self.cut_drag[-1][0], self.cut_drag[-1][1] - 22), SHARE_CYAN, 14, center=True)

    def _draw_banner(self, painter: CL.Painter) -> None:
        alpha = int(255 * CL.clamp(self.banner_time / 2.2, 0.0, 1.0))
        painter.text(self.banner_text, (W // 2, 216), CYAN, 34, bold=True, center=True, alpha=alpha)

    def _draw_cut_banner(self, painter: CL.Painter) -> None:
        alpha = int(255 * CL.clamp(self.cut_banner_time / 3.0, 0.0, 1.0))
        rect = pygame.Rect(W // 2 - 420, 176, 840, 56)
        painter.rect((18, 26, 34), rect, radius=8)
        painter.rect(AMBER, rect, width=2, radius=8)
        painter.text(self.cut_banner, (W // 2, 204), AMBER, 20, center=True, alpha=alpha)

    # -- 模态弹窗 -------------------------------------------------------
    def _draw_modal(self, painter: CL.Painter) -> None:
        veil = self.veil
        if veil is None or veil.get_size() != self.window.get_size():
            veil = pygame.Surface(self.window.get_size(), pygame.SRCALPHA)
            self.veil = veil
        veil.fill((3, 6, 11, 205))
        painter.surface.blit(veil, (0, 0))
        modal = self.modal
        assert modal is not None
        panel_w, panel_h = 1120, 640
        panel = pygame.Rect((W - panel_w) // 2, 220, panel_w, panel_h)
        painter.rect(PANEL, panel, radius=14)
        border = {"opening": CYAN, "w1": CYAN, "w2": AMBER, "w3": SHARE_CYAN,
                  "cut": BUFF_GOLD, "defeat": RED, "complete": GREEN}.get(modal.kind, CYAN)
        if modal.kind.startswith("enemy_"):
            border = ENEMY_STATS[modal.kind[len("enemy_"):]]["color"]
        painter.rect(border, panel, width=3, radius=14)
        painter.fill(border, (panel.x + 20, panel.y + 20, 6, panel.h - 40))
        painter.text("时停 // 点击继续" if modal.kind != "complete" else "TUTORIAL COMPLETE",
                     (panel.x + 42, panel.y + 22), border, 13, mono=True)
        painter.text(modal.title, (panel.x + 42, panel.y + 50), WHITE, 32, bold=True)
        illustration_h = self._draw_modal_illustration(painter, modal, panel, border)
        line_y = panel.y + 170 + illustration_h
        for line in modal.lines:
            painter.text("· " + line, (panel.x + 44, line_y), TEXT, 18)
            line_y += 30
        button = pygame.Rect(panel.centerx - 190, panel.bottom - 92, 380, 56)
        self.modal_button_rect = button
        hovered = self.modal_button_rect.collidepoint(self.mouse_logical)
        painter.rect(CL.blend((24, 34, 44), border, 0.25 if hovered else 0.12), button, radius=10)
        painter.rect(border, button, width=2, radius=10)
        painter.text(modal.button, button.center, WHITE if hovered else TEXT, 20, center=True, bold=True)
        painter.text("点击继续 / 面板任意位置", (panel.centerx, panel.bottom - 18), DIM, 12, center=True)

    def _draw_modal_illustration(self, painter: CL.Painter, modal: Modal, panel: pygame.Rect,
                                 border: tuple[int, int, int]) -> int:
        top = panel.y + 104
        height = 0
        if modal.illustration.startswith("enemy_"):
            kind = modal.illustration[len("enemy_"):]
            stats = ENEMY_STATS.get(kind, ENEMY_STATS["MINION"])
            height = 156
            card = pygame.Rect(panel.centerx - 300, top, 600, 140)
            painter.rect((12, 18, 26), card, radius=10)
            painter.rect(stats["color"], card, width=2, radius=10)
            painter.circle(stats["color"], (card.x + 80, card.y + 70), 42)
            painter.circle((12, 18, 26), (card.x + 80, card.y + 70), 18)
            painter.text(stats["name"], (card.x + 150, card.y + 26), WHITE, 26, bold=True)
            painter.text(stats["desc"], (card.x + 150, card.y + 66), MUTED, 15)
            painter.text("主动接近 · 有 HP / 攻击距离", (card.x + 150, card.y + 92), DIM, 13)
            if kind == "BOMB":
                painter.text("死亡时爆炸（注意范围）", (card.x + 150, card.y + 112), RED, 13)
            elif kind == "WARD":
                painter.text("金线被剪断 → 增益/护盾消失", (card.x + 150, card.y + 112), BUFF_GOLD, 13)
        elif modal.illustration == "roles":
            height = 128
            card_w = 320
            for index, ally in enumerate(self.allies):
                card = pygame.Rect(panel.x + 42 + index * (card_w + 18), top, card_w, 116)
                color = ALLY_STATS[ally.key]["color"]
                painter.rect((12, 18, 26), card, radius=8)
                painter.rect(color, card, width=2, radius=8)
                self._draw_ally_thumb(painter, ally, pygame.Rect(card.x + 10, card.y + 10, 76, 96))
                painter.text(ally.display_name, (card.x + 96, card.y + 12), WHITE, 20, bold=True)
                painter.text(f"{ALLY_DISPLAY[ally.key]['slot']} · {ALLY_DISPLAY[ally.key]['type']}",
                             (card.x + 96, card.y + 40), color, 13, mono=True)
                painter.text(ALLY_DISPLAY[ally.key]["desc"], (card.x + 96, card.y + 60), MUTED, 12)
                painter.text("固定上场 · 不替换", (card.x + 96, card.y + 84), DIM, 11)
        elif modal.illustration == "auto":
            height = 96
            painter.text("自动移动", (panel.x + 160, top + 12), CYAN, 16, center=True)
            painter.text("自动普攻", (panel.centerx, top + 12), GREEN, 16, center=True)
            painter.text("自动小技能", (panel.right - 160, top + 12), PURPLE, 16, center=True)
            for cx in (panel.x + 160, panel.centerx, panel.right - 160):
                painter.circle(border, (cx, top + 56), 24, 2)
                painter.circle(border, (cx, top + 56), 8)
            painter.line(border, (panel.x + 184, top + 56), (panel.centerx - 24, top + 56), 2)
            painter.line(border, (panel.centerx + 24, top + 56), (panel.right - 184, top + 56), 2)
            painter.text("角色全自动 · 你只负责在 W3 剪一条引用", (panel.centerx, top + 92), MUTED, 13, center=True)
        elif modal.illustration == "enemies":
            height = 150
            kinds = ["MINION", "SENTINEL", "BOMB"]
            card_w = 320
            for index, kind in enumerate(kinds):
                stats = ENEMY_STATS[kind]
                card = pygame.Rect(panel.x + 42 + index * (card_w + 18), top, card_w, 136)
                painter.rect((12, 18, 26), card, radius=8)
                painter.rect(stats["color"], card, width=2, radius=8)
                painter.circle(stats["color"], (card.x + 52, card.y + 62), 30)
                painter.text(stats["name"], (card.x + 100, card.y + 18), WHITE, 18, bold=True)
                painter.text(stats["cn"], (card.x + 100, card.y + 44), stats["color"], 13)
                painter.text(stats["desc"][:16], (card.x + 100, card.y + 66), MUTED, 12)
                painter.text(stats["desc"][16:32], (card.x + 100, card.y + 84), MUTED, 12)
        elif modal.illustration == "network":
            height = 190
            center_y = top + 86
            sentinel = pygame.Rect(panel.x + 120, center_y - 60, 190, 120)
            ward = pygame.Rect(panel.right - 310, center_y - 60, 190, 120)
            painter.rect((52, 34, 20), sentinel, radius=10)
            painter.rect(ORANGE, sentinel, width=2, radius=10)
            painter.text("哨兵", sentinel.center, ORANGE, 18, bold=True, center=True)
            painter.text("远程射击", (sentinel.centerx, sentinel.centery + 24), MUTED, 12, center=True)
            painter.rect((18, 40, 48), ward, radius=10)
            painter.rect(SHARE_CYAN, ward, width=2, radius=10)
            painter.text("护盾守卫", ward.center, SHARE_CYAN, 18, bold=True, center=True)
            painter.text("增益 / 护盾", (ward.centerx, ward.centery + 24), MUTED, 12, center=True)
            # 两条引用弧线
            share_points = []
            buff_points = []
            for i in range(13):
                t = i / 12
                mx = (sentinel.right + ward.left) / 2
                share_points.append((sentinel.right + (ward.left - sentinel.right) * t,
                                     sentinel.centery - 46 * math.sin(math.pi * t) - 16))
                buff_points.append((sentinel.right + (ward.left - sentinel.right) * t,
                                    sentinel.centery + 46 * math.sin(math.pi * t) + 16))
            for i in range(len(share_points) - 1):
                painter.line(SHARE_CYAN, share_points[i], share_points[i + 1], 3)
                painter.line(BUFF_GOLD, buff_points[i], buff_points[i + 1], 3)
            painter.polygon(SHARE_CYAN, [share_points[1], (share_points[1][0] - 12, share_points[1][1] - 6),
                                         (share_points[1][0] - 12, share_points[1][1] + 6)])
            painter.polygon(SHARE_CYAN, [share_points[-2], (share_points[-2][0] + 12, share_points[-2][1] - 6),
                                         (share_points[-2][0] + 12, share_points[-2][1] + 6)])
            painter.polygon(BUFF_GOLD, [buff_points[-2], (buff_points[-2][0] + 12, buff_points[-2][1] - 6),
                                        (buff_points[-2][0] + 12, buff_points[-2][1] + 6)])
            painter.text("SHARE（青）：伤害共享", (sentinel.centerx + 10, top + 6), SHARE_CYAN, 14)
            painter.text("BUFF（金）：护盾守卫 → 哨兵", (panel.centerx - 60, top + 6), BUFF_GOLD, 14)
            painter.text("剪断一条 = 隔离；失去 SHARE 的哨兵会暴露（受伤 +40%）",
                         (panel.centerx, top + 166), RED, 13, center=True)
        elif modal.illustration == "cut":
            height = 130
            y = top + 50
            painter.line(SHARE_CYAN, (panel.x + 180, y), (panel.right - 180, y), 4)
            painter.text("SHARE", (panel.centerx, y - 22), SHARE_CYAN, 15, center=True)
            painter.line((255, 255, 255), (panel.centerx - 90, y - 60), (panel.centerx + 90, y + 60), 4)
            painter.circle((255, 255, 255), (panel.centerx - 90, y - 60), 8, 2)
            painter.text("按住左键拖拽划过连线", (panel.centerx, y + 78), TEXT, 15, center=True)
            painter.text("只允许一次", (panel.centerx, y + 104), AMBER, 14, center=True)
        elif modal.illustration == "complete":
            height = 90
            painter.text("3 WAVES CLEARED", (panel.centerx, top + 16), GREEN, 22, bold=True, center=True)
            painter.text(f"击破 {self.kills}  ·  断连 {'已使用' if self.cut_used else '未使用'}  ·  "
                         f"重试 {self.retries}", (panel.centerx, top + 54), TEXT, 16, center=True)
        return height


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Tutorial Battle: 3 allies × 3 waves network tutorial")
    parser.add_argument("--windowed", action="store_true", help="窗口模式（默认全屏）")
    parser.add_argument("--size", default=None, help="窗口物理尺寸 WxH，例如 1920x1080")
    parser.add_argument("--shot", default=None, help="无窗口截图路径（PNG，窗口物理分辨率），保存后退出")
    parser.add_argument("--time", type=float, default=SHOT_DEFAULT_TIME, help="--shot 模拟到第几秒")
    parser.add_argument("--seed", type=int, default=SEED, help="随机种子")
    parser.add_argument("--start-wave", type=int, default=1, help="--shot 用：直接从第 1/2/3 波开始")
    parser.add_argument("--auto-cut", action="store_true", help="--shot 用：W3 自动剪断 SHARE")
    parser.add_argument("--verbose", action="store_true", help="打印事件日志")
    parser.add_argument("--smoke", action="store_true", help="无窗口 smoke 自检（自动使用 dummy SDL）")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.smoke and "SDL_VIDEODRIVER" not in os.environ:
        os.environ["SDL_VIDEODRIVER"] = "dummy"
    if "SDL_AUDIODRIVER" not in os.environ:
        os.environ["SDL_AUDIODRIVER"] = "dummy"
    app = TutorialBattle(args)
    return app.run()


if __name__ == "__main__":
    sys.exit(main())
