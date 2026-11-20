# -*- coding: utf-8 -*-
"""全项目事件名注册表与每场战斗独立的事件总线。

命名规范见 ``docs/EVENT_NAMING.md``。

设计约束：
- 事件是“已经发生的事实”，不是命令；发送方不 import 监听方。
- 同一次 emit 内同步调用监听方，保证表现与旧代码同一帧、同一顺序。
- payload 是只读快照；监听方不要修改游戏状态，也不要长期持有 payload。
- 总线按战斗创建，不放进全局；战斗结束后随 Battle 一起丢弃。
"""

# --- 战斗开始 / 手牌 ---
BATTLE_DECK_ONLINE = "BATTLE_DECK_ONLINE"
BATTLE_DRAW = "BATTLE_DRAW"
BATTLE_CARD_CAST = "BATTLE_CARD_CAST"
BATTLE_CARD_RELEASED = "BATTLE_CARD_RELEASED"
BATTLE_NOTICE = "BATTLE_NOTICE"
BATTLE_CUT_RESULT = "BATTLE_CUT_RESULT"

# --- 边与卡牌动作 ---
BATTLE_EDGE_CUT = "BATTLE_EDGE_CUT"
BATTLE_EDGE_BARRIER = "BATTLE_EDGE_BARRIER"
BATTLE_PARRY = "BATTLE_PARRY"
BATTLE_LINK = "BATTLE_LINK"
BATTLE_WEAK = "BATTLE_WEAK"
BATTLE_WEAKEN_EDGE = "BATTLE_WEAKEN_EDGE"
BATTLE_SWEEP = "BATTLE_SWEEP"
BATTLE_ALIAS = "BATTLE_ALIAS"
BATTLE_CAST = "BATTLE_CAST"
BATTLE_REFLECT = "BATTLE_REFLECT"
BATTLE_STEAL = "BATTLE_STEAL"
BATTLE_COMPRESS = "BATTLE_COMPRESS"
BATTLE_ECC = "BATTLE_ECC"
BATTLE_DOWNSAMPLE = "BATTLE_DOWNSAMPLE"
BATTLE_DELAY_SET = "BATTLE_DELAY_SET"
BATTLE_LOSSY = "BATTLE_LOSSY"

# --- 伤害、GC 与节点 ---
BATTLE_EXPLODE = "BATTLE_EXPLODE"
BATTLE_DAMAGE = "BATTLE_DAMAGE"
BATTLE_NODE_KILLED = "BATTLE_NODE_KILLED"
BATTLE_ALIAS_POOL_KILLED = "BATTLE_ALIAS_POOL_KILLED"
BATTLE_SCORE = "BATTLE_SCORE"
BATTLE_LEAK = "BATTLE_LEAK"
BATTLE_GC_SHOCKWAVE = "BATTLE_GC_SHOCKWAVE"
BATTLE_SHOCK_HIT = "BATTLE_SHOCK_HIT"
BATTLE_GC_ERASED = "BATTLE_GC_ERASED"
BATTLE_CASCADE = "BATTLE_CASCADE"
BATTLE_ALIAS_EXPIRED = "BATTLE_ALIAS_EXPIRED"

# --- 敌人 ---
BATTLE_WARD = "BATTLE_WARD"
BATTLE_REINFORCEMENT = "BATTLE_REINFORCEMENT"
BATTLE_MINION_SPAWN = "BATTLE_MINION_SPAWN"
BATTLE_MELEE_TELEGRAPH = "BATTLE_MELEE_TELEGRAPH"
BATTLE_MELEE_WINDUP = "BATTLE_MELEE_WINDUP"
BATTLE_MELEE_HIT = "BATTLE_MELEE_HIT"
BATTLE_ENEMY_SHOT = "BATTLE_ENEMY_SHOT"
BATTLE_CYCLER_LINK = "BATTLE_CYCLER_LINK"
BATTLE_BOSS_EXPOSED = "BATTLE_BOSS_EXPOSED"
BATTLE_BOSS_RING = "BATTLE_BOSS_RING"
BATTLE_AUDIT = "BATTLE_AUDIT"
BATTLE_BAD_ACCESS = "BATTLE_BAD_ACCESS"

# --- 玩家与房间 ---
BATTLE_PLAYER_HURT = "BATTLE_PLAYER_HURT"
BATTLE_PLAYER_DIED = "BATTLE_PLAYER_DIED"
BATTLE_REDUNDANCY = "BATTLE_REDUNDANCY"
BATTLE_DASH = "BATTLE_DASH"
BATTLE_WRITE = "BATTLE_WRITE"
BATTLE_WRITE_HIT = "BATTLE_WRITE_HIT"
BATTLE_FREE_GC = "BATTLE_FREE_GC"
BATTLE_NECRO_BOMB = "BATTLE_NECRO_BOMB"
BATTLE_DEAD_CODE = "BATTLE_DEAD_CODE"
BATTLE_SLASH_TRAIL = "BATTLE_SLASH_TRAIL"
BATTLE_TARGET_PICK = "BATTLE_TARGET_PICK"
BATTLE_ROOM_CLEAR = "BATTLE_ROOM_CLEAR"


class EventBus:
    """一场战斗内的同步事件总线。

    监听方按订阅顺序同步执行；发送方不会知道监听方是谁。
    """

    __slots__ = ("_subs",)

    def __init__(self):
        self._subs = {}

    def subscribe(self, name, handler):
        self._subs.setdefault(name, []).append(handler)
        return handler

    def unsubscribe(self, name, handler):
        handlers = self._subs.get(name)
        if not handlers:
            return False
        try:
            handlers.remove(handler)
        except ValueError:
            return False
        if not handlers:
            self._subs.pop(name, None)
        return True

    def emit(self, name, **payload):
        """同步派发；返回实际调用到的监听方数量。"""
        handlers = self._subs.get(name)
        if not handlers:
            return 0
        for handler in tuple(handlers):
            handler(payload)
        return len(handlers)

    def clear(self):
        self._subs.clear()

    def subscriber_count(self, name=None):
        if name is None:
            return sum(len(v) for v in self._subs.values())
        return len(self._subs.get(name, ()))
