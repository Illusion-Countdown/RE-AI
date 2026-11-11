# -*- coding: utf-8 -*-
"""GameState：全局唯一的状态。

铁律：UI 只读它，逻辑只通过 actions 改它。
"""
from dataclasses import dataclass, field

import config
from core.commitmap import CommitMap
from core.entities import Player
from core.memory import Memory
from data import CARDS, CHARACTERS


def card_shape(card) -> tuple:
    """空间复杂度 → 在内存里的形状。"""
    cells = card["cells"]
    if cells <= 1:
        return 1, 1
    if cells == 2:
        return 1, 2
    return 2, 2


@dataclass
class GameState:
    # 实体
    player: Player
    memory: Memory
    map: CommitMap

    enemies: list = field(default_factory=list)
    bullets: list = field(default_factory=list)
    drops: list = field(default_factory=list)

    # 牌
    hand: list = field(default_factory=list)
    cooldowns: dict = field(default_factory=dict)
    draw_timer: float = 0.0
    pending_cards: int = 0

    # 资源
    quota: int = config.START_QUOTA
    corruption: float = 0.0

    # 战斗
    move: tuple = (0.0, 0.0)
    invuln: float = 0.0
    freeze: float = 0.0          # commit 的全场冻结倒计时
    smash_cd: float = 0.0        # 巨兽拆内存的全局冷却
    time: float = 0.0
    kills: int = 0

    # 流程
    over: bool = False
    win: bool = False
    player_down: bool = False
    node_cleared: bool = False

    # 日志 / 事件
    events: list = field(default_factory=list)
    logs: list = field(default_factory=list)

    # 肉鸽：分支暂存
    branch_loot: list = field(default_factory=list)

    _uid: int = 1000

    # ---------------- 工具 ----------------

    def next_uid(self) -> int:
        self._uid += 1
        return self._uid

    def emit(self, event, **kw):
        """往事件队列里塞一条。UI 靠它播特效。

        参数名故意叫 event 而不是 kind —— 因为有些事件自己也带 kind 字段，
        叫 kind 会撞参数。
        """
        self.events.append({"type": event, **kw})

    def pop_events(self):
        out = self.events
        self.events = []
        return out

    def log(self, text):
        self.logs.append(text)

    def alive_enemies(self) -> list:
        return [e for e in self.enemies if e.alive]

    # ---------------- 构造 ----------------

    @staticmethod
    def new(character_id="deepquest") -> "GameState":
        char = CHARACTERS[character_id]
        x0, y0, w, h = config.ARENA
        player = Player(
            x=x0 + w / 2, y=y0 + h / 2,
            hp=char["hp"], max_hp=char["hp"],
            speed=char["speed"],
            lang=char["lang"], engine=char["engine"],
        )
        state = GameState(player=player, memory=Memory(5, 5), map=CommitMap())

        # 初始牌库：4 张卡先进内存
        for cid in ("hash", "binary", "bfs", "cache"):
            cw, ch = card_shape(CARDS[cid])
            if not state.memory.place(cid, cw, ch):
                state.log(f"内存不足：{CARDS[cid]['name']} 装载失败")

        state.log(f"初始化：{char['name']} / {char['lang']} / {char['engine']}")
        return state
