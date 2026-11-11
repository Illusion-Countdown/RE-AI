"""RUNTIME 4.0 demo 数据模型。core 不 import pygame。"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any


Cell = tuple[int, int]


@dataclass
class PieceDef:
    id: str
    name: str
    en: str = ""
    time_complexity: str = "O(1)"
    space_complexity: str = "O(1)"
    shape: list[Cell] = field(default_factory=lambda: [(0, 0)])
    hp: int = 60
    damage: int = 10
    interval: float = 1.2
    range: int = 1
    method: str = "damage"
    tags: list[str] = field(default_factory=list)
    role: str = ""
    desc: str = ""
    special: str = ""
    star3: str = ""


@dataclass
class CardDef:
    id: str
    name: str
    system_call: str = ""
    cost: int = 1
    kind: str = "global"  # global / single / area
    target: str = ""
    effect: str = ""
    value: Any = None
    desc: str = ""
    unlock: str = "common"


@dataclass
class EnemyDef:
    id: str
    name: str
    en: str = ""
    fault: str = "data"
    hp: int = 32
    damage: int = 5
    speed: float = 1.0
    range: int = 1
    size: int = 1
    special: str = ""
    desc: str = ""
    handling: str = "damage"


@dataclass
class LanguageDef:
    id: str
    name: str
    color: tuple[int, int, int] = (200, 200, 200)
    rules: list[dict[str, Any]] = field(default_factory=list)
    counters: dict[str, float] = field(default_factory=dict)
    weak: dict[str, float] = field(default_factory=dict)
    special_cards: list[str] = field(default_factory=list)


@dataclass
class AIDef:
    id: str
    name: str
    context: int = 12
    color: tuple[int, int, int] = (37, 99, 235)
    passive: list[dict[str, Any]] = field(default_factory=list)
    ultimate: dict[str, Any] = field(default_factory=dict)


@dataclass
class MapNodeDef:
    id: str
    type: str
    title: str
    desc: str = ""
    language_pool: list[str] = field(default_factory=list)
    enemy_ids: list[str] = field(default_factory=list)
    wave_count: int = 3
    rewards: list[str] = field(default_factory=list)
    next: list[str] = field(default_factory=list)
    layer: int = 0


@dataclass
class MapLayerDef:
    id: str
    name: str
    subtitle: str
    nodes: list[MapNodeDef] = field(default_factory=list)


@dataclass
class BossPhaseDef:
    id: str
    name: str
    hp_ratio: float = 1.0
    behavior: str = ""
    spawns: list[str] = field(default_factory=list)
    desc: str = ""


@dataclass
class BossDef:
    total_hp: int = 2400
    core_damage: int = 40
    phases: list[BossPhaseDef] = field(default_factory=list)


@dataclass
class PieceInstance:
    definition: PieceDef
    star: int = 1
    cells: list[Cell] = field(default_factory=list)
    hp: float = 0
    max_hp: float = 0
    next_action: float = 0.0
    stall: float = 0.0
    state: dict[str, Any] = field(default_factory=dict)
    alive: bool = True
    main_thread: bool = False
    durability: int = 3

    def __post_init__(self) -> None:
        if self.max_hp <= 0:
            self.max_hp = self.definition.hp
        if self.hp <= 0:
            self.hp = self.max_hp

    @property
    def name(self) -> str:
        return self.definition.name

    @property
    def interval(self) -> float:
        return self.definition.interval

    @property
    def damage(self) -> float:
        return self.definition.damage * (1.0 if self.star == 1 else 1.6 if self.star == 2 else 2.6)

    @property
    def hp_ratio(self) -> float:
        return max(0.0, min(1.0, self.hp / max(1.0, self.max_hp)))

    def clone(self) -> "PieceInstance":
        return copy.deepcopy(self)


@dataclass
class EnemyInstance:
    definition: EnemyDef
    cell: Cell | None = None
    path: list[Cell] = field(default_factory=list)
    path_index: int = 0
    hp: float = 0
    max_hp: float = 0
    next_move: float = 0.0
    next_attack: float = 0.0
    status: set[str] = field(default_factory=set)
    ghost: bool = False
    boss: bool = False

    def __post_init__(self) -> None:
        if self.max_hp <= 0:
            self.max_hp = self.definition.hp
        if self.hp <= 0:
            self.hp = self.max_hp
        if self.cell is None and self.path:
            self.cell = self.path[0]

    @property
    def hp_ratio(self) -> float:
        return max(0.0, min(1.0, self.hp / max(1.0, self.max_hp)))


@dataclass
class CardInstance:
    definition: CardDef
    used: bool = False


@dataclass
class RunState:
    ai: AIDef
    languages: dict[str, LanguageDef]
    pieces: list[PieceInstance] = field(default_factory=list)
    bench: list[PieceInstance] = field(default_factory=list)
    hand: list[CardDef] = field(default_factory=list)
    memory: set[Cell] = field(default_factory=set)
    sector_types: dict[Cell, str] = field(default_factory=dict)
    jurisdiction: set[Cell] = field(default_factory=set)
    language: str = "C"
    prompt_mode: str = "nearest"
    core_hp: int = 100
    max_core_hp: int = 100
    compute: int = 4
    max_compute: int = 8
    vram: int = 6
    max_vram: int = 12
    fragments: int = 20
    quota: int = 6
    tech_debt: int = 0
    layer: int = 0
    node: MapNodeDef | None = None
    completed: list[str] = field(default_factory=list)
    path: list[str] = field(default_factory=list)
    active_ports: set[int] = field(default_factory=set)
    ai_charge: int = 0
    ai_ultimate_wave: int = -1
    overclocked: set[int] = field(default_factory=set)
    broken_cells: set[Cell] = field(default_factory=set)
    traps: set[Cell] = field(default_factory=set)
    flags: dict[str, Any] = field(default_factory=dict)
    log: list[str] = field(default_factory=list)
    seed: int = 1
    turn: int = 0

    def clone(self) -> "RunState":
        return copy.deepcopy(self)

    def add_log(self, text: str) -> None:
        if text:
            self.log.append(str(text))
            self.log = self.log[-80:]
