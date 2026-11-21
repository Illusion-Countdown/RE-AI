# -*- coding: utf-8 -*-
"""构造一场战斗并完成 C/D 反馈接线。

App 和测试都走这里，避免出现“Battle 能跑但没有任何监听器”的静默路径。
"""
from memory_run.events import EventBus
from memory_run.battle.battle import Battle
from memory_run.ui.battle_fx import BattleFx
from memory_run.ui.fx import FX
from memory_run.platform.audio_feedback import BattleAudio


def create_battle(run, strict=False):
    fx = FX()
    bus = EventBus(strict=strict)
    BattleFx(bus, fx)
    BattleAudio(bus)
    return Battle(run, fx, bus)
