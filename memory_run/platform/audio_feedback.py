# -*- coding: utf-8 -*-
"""战斗事件 → 音频 cue。

只做事件名到音效的映射；战斗逻辑不 import 这个模块。
"""
from memory_run import events
from . import audio


class BattleAudio:
    def __init__(self, bus):
        handlers = (
            (events.BATTLE_CARD_CAST, self._select),
            (events.BATTLE_CARD_RELEASED, self._select),
            (events.BATTLE_EDGE_CUT, self._cut),
            (events.BATTLE_EDGE_BARRIER, self._weak),
            (events.BATTLE_PARRY, self._alias),
            (events.BATTLE_LINK, self._link),
            (events.BATTLE_WEAK, self._weak),
            (events.BATTLE_WEAKEN_EDGE, self._weak),
            (events.BATTLE_ALIAS, self._alias),
            (events.BATTLE_CAST, self._cast),
            (events.BATTLE_STEAL, self._hijack),
            (events.BATTLE_COMPRESS, self._glitch),
            (events.BATTLE_ECC, self._clear),
            (events.BATTLE_DOWNSAMPLE, self._glitch),
            (events.BATTLE_LOSSY, self._boom),
            (events.BATTLE_EXPLODE, self._explode),
            (events.BATTLE_ALIAS_POOL_KILLED, self._death),
            (events.BATTLE_GC_ERASED, self._gc),
            (events.BATTLE_CASCADE, self._cascade),
            (events.BATTLE_MINION_SPAWN, self._minion),
            (events.BATTLE_MELEE_TELEGRAPH, self._weak),
            (events.BATTLE_MELEE_WINDUP, self._ui),
            (events.BATTLE_MELEE_HIT, self._hurt),
            (events.BATTLE_ENEMY_SHOT, self._enemy_shot),
            (events.BATTLE_BOSS_EXPOSED, self._gcstart),
            (events.BATTLE_PLAYER_HURT, self._hurt),
            (events.BATTLE_PLAYER_DIED, self._death),
            (events.BATTLE_DASH, self._dash),
            (events.BATTLE_WRITE_HIT, self._write),
            (events.BATTLE_NECRO_BOMB, self._boom),
            (events.BATTLE_DEAD_CODE, self._cast),
            (events.BATTLE_ROOM_CLEAR, self._clear),
        )
        for name, handler in handlers:
            bus.subscribe(name, handler)

    def _select(self, p):
        audio.play("select")

    def _cut(self, p):
        audio.play("cut")

    def _alias(self, p):
        audio.play("alias")

    def _link(self, p):
        audio.play("link")

    def _weak(self, p):
        audio.play("weak")

    def _cast(self, p):
        audio.play("cast")

    def _hijack(self, p):
        audio.play("hijack")

    def _glitch(self, p):
        audio.play("glitch")

    def _clear(self, p):
        audio.play("clear")

    def _boom(self, p):
        audio.play("boom")

    def _death(self, p):
        audio.play("death")

    def _gc(self, p):
        audio.play("gc")

    def _gcstart(self, p):
        audio.play("gcstart")

    def _hurt(self, p):
        if p.get("mode") == "alias":
            return
        audio.play("hurt")

    def _dash(self, p):
        audio.play("dash")

    def _write(self, p):
        audio.play("write")

    def _ui(self, p):
        audio.play("ui")

    def _explode(self, p):
        if p["dud"]:
            audio.play("weak")

    def _cascade(self, p):
        if p["tier"] == 8:
            audio.play("hijack")
        else:
            audio.play("clear")

    def _minion(self, p):
        audio.play("link", 0.5)

    def _enemy_shot(self, p):
        audio.play("write", 0.35)
