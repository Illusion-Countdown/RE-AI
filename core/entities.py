# -*- coding: utf-8 -*-
"""游戏里的实体：玩家、敌人、子弹。

只用 dataclass，不写继承 —— 和上一版一样的理由：
一旦有 Boss(Enemy)、FireBoss(Boss)，继承树就会失控。
"""
from dataclasses import dataclass, field


@dataclass
class Player:
    """你的 AI。自动普攻，玩家只控制走位和放卡。"""

    x: float
    y: float
    hp: float
    max_hp: float
    speed: float
    lang: str
    engine: str

    radius: float = 18.0
    attack_timer: float = 0.0
    moving: bool = False

    @property
    def alive(self) -> bool:
        return self.hp > 0


@dataclass
class Enemy:
    uid: int
    kind: str
    x: float
    y: float
    hp: float
    max_hp: float
    speed: float
    damage: float
    radius: float
    etype: str            # data / hardware / memory / concurrency
    special: str = ""     # smash_memory / ...
    slow_timer: float = 0.0
    marked: bool = False
    smash_timer: float = 6.0
    frozen: float = 0.0   # 被 commit 冻结成地形的倒计时
    base_speed: float = 0.0
    phase: int = 1
    phase_timer: float = 0.0

    @property
    def alive(self) -> bool:
        return self.hp > 0

    @property
    def coef(self) -> float:
        """减速后的速度系数。"""
        return 0.4 if self.slow_timer > 0 else 1.0


@dataclass
class Bullet:
    x: float
    y: float
    vx: float
    vy: float
    damage: float
    radius: float = 6.0
    life: float = 1.2
    pierce: bool = False
    hits: set = field(default_factory=set)


@dataclass
class Drop:
    """地图上掉的东西（swap / 卡包）。"""

    kind: str          # swap / card / dump
    x: float
    y: float
    radius: float = 12.0
