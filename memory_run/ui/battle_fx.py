# -*- coding: utf-8 -*-
"""战斗事件 → 屏幕表现。

Battle 只发事实，不 import UI；这里把事实翻译成原来的 FX 调用。
所有坐标/颜色都在事件 payload 里，监听器不改战斗状态。
"""
from memory_run import events
from memory_run.battle.constants import NODE_COLOR
from memory_run.const import *


class BattleFx:
    def __init__(self, bus, fx):
        self.fx = fx
        handlers = (
            (events.BATTLE_DECK_ONLINE, self._deck_online),
            (events.BATTLE_DRAW, self._draw),
            (events.BATTLE_CARD_CAST, self._card_cast),
            (events.BATTLE_CARD_RELEASED, self._card_released),
            (events.BATTLE_NOTICE, self._notice),
            (events.BATTLE_CUT_RESULT, self._cut_result),
            (events.BATTLE_EDGE_CUT, self._edge_cut),
            (events.BATTLE_EDGE_BARRIER, self._edge_barrier),
            (events.BATTLE_PARRY, self._parry),
            (events.BATTLE_LINK, self._link),
            (events.BATTLE_WEAK, self._weak),
            (events.BATTLE_WEAKEN_EDGE, self._weaken_edge),
            (events.BATTLE_SWEEP, self._sweep),
            (events.BATTLE_ALIAS, self._alias),
            (events.BATTLE_CAST, self._cast),
            (events.BATTLE_REFLECT, self._reflect),
            (events.BATTLE_STEAL, self._steal),
            (events.BATTLE_COMPRESS, self._compress),
            (events.BATTLE_ECC, self._ecc),
            (events.BATTLE_DOWNSAMPLE, self._downsample),
            (events.BATTLE_DELAY_SET, self._delay_set),
            (events.BATTLE_LOSSY, self._lossy),
            (events.BATTLE_EXPLODE, self._explode),
            (events.BATTLE_DAMAGE, self._damage),
            (events.BATTLE_NODE_KILLED, self._node_killed),
            (events.BATTLE_ALIAS_POOL_KILLED, self._alias_pool_killed),
            (events.BATTLE_SCORE, self._score),
            (events.BATTLE_LEAK, self._leak),
            (events.BATTLE_GC_SHOCKWAVE, self._gc_shockwave),
            (events.BATTLE_SHOCK_HIT, self._shock_hit),
            (events.BATTLE_GC_ERASED, self._gc_erased),
            (events.BATTLE_CASCADE, self._cascade),
            (events.BATTLE_ALIAS_EXPIRED, self._alias_expired),
            (events.BATTLE_WARD, self._ward),
            (events.BATTLE_REINFORCEMENT, self._reinforcement),
            (events.BATTLE_MINION_SPAWN, self._minion_spawn),
            (events.BATTLE_MELEE_TELEGRAPH, self._melee_telegraph),
            (events.BATTLE_MELEE_WINDUP, self._melee_windup),
            (events.BATTLE_MELEE_HIT, self._melee_hit),
            (events.BATTLE_CYCLER_LINK, self._cycler_link),
            (events.BATTLE_BOSS_EXPOSED, self._boss_exposed),
            (events.BATTLE_BOSS_RING, self._boss_ring),
            (events.BATTLE_AUDIT, self._audit),
            (events.BATTLE_BAD_ACCESS, self._bad_access),
            (events.BATTLE_PLAYER_HURT, self._player_hurt),
            (events.BATTLE_PLAYER_DIED, self._player_died),
            (events.BATTLE_REDUNDANCY, self._redundancy),
            (events.BATTLE_DASH, self._dash),
            (events.BATTLE_WRITE, self._write),
            (events.BATTLE_WRITE_HIT, self._write_hit),
            (events.BATTLE_FREE_GC, self._free_gc),
            (events.BATTLE_DEAD_CODE, self._dead_code),
            (events.BATTLE_SLASH_TRAIL, self._slash_trail),
            (events.BATTLE_TARGET_PICK, self._target_pick),
            (events.BATTLE_ROOM_CLEAR, self._room_clear),
        )
        for name, handler in handlers:
            bus.subscribe(name, handler)

    def _deck_online(self, p):
        n = p["player"]
        self.fx.add_text(n.x, n.y - 40, "DECK ONLINE", CYAN, 18, 1.2)

    def _draw(self, p):
        n, card = p["player"], p["card"]
        self.fx.add_text(n.x, n.y - 54, card.name, card.color, 14, 0.8)

    def _card_cast(self, p):
        card, n, work = p["card"], p["player"], p["work"]
        self.fx.add_flash(0.025, card.color, 11)
        self.fx.add_shake(1.2, 9)
        if work:
            self.fx.add_text(n.x + 26, n.y - 18, f"-{work} WORK",
                             AMBER, 11, 0.7)
        self.fx.add_ring(n.x, n.y, 6, 42, card.color, 0.3, 2)

    def _card_released(self, p):
        n, card = p["player"], p["card"]
        self.fx.add_text(n.x, n.y - 34, f"{card.name} · 无目标释放",
                         card.color, 12, 0.8)

    def _notice(self, p):
        n = p["player"]
        self.fx.add_text(n.x, n.y - 34, p["msg"], AMBER, 15, 0.8)

    def _cut_result(self, p):
        n = p["player"]
        self.fx.add_text(n.x, n.y - 40, f"CUT x{p['count']}", CYAN, 16, 0.8)

    def _edge_cut(self, p):
        e, dst = p["edge"], p["dst"]
        self.fx.add_spark((e.src.x, e.src.y), (dst.x, dst.y), CYAN, 0.3, 3)
        self.fx.add_parts(dst.x, dst.y, CYAN, 6, 120, 0.35, 1.8)
        self.fx.add_flash(0.025, CYAN, 12)
        self.fx.add_shake(1.8, 8)

    def _edge_barrier(self, p):
        dst = p["dst"]
        self.fx.add_ring(dst.x, dst.y, dst.r * 0.7, dst.r * 2.2,
                         BLUE, 0.4, 3)
        self.fx.add_text(dst.x, dst.y - dst.r - 12, "BARRIER",
                         BLUE, 14, 1.0)

    def _parry(self, p):
        src, n = p["src"], p["player"]
        a = (src.x, src.y) if src else (n.x, n.y)
        self.fx.add_spark(a, (n.x, n.y), GOLD, 0.32, 4)
        self.fx.add_ring(n.x, n.y, 10, 90, GOLD, 0.4, 3)
        self.fx.add_text(n.x, n.y - 42, "PARRY", GOLD, 20, 0.9)
        self.fx.add_flash(0.08, GOLD, 6)

    def _link(self, p):
        a, b, angle = p["a"], p["b"], p["angle"]
        self.fx.add_dir_parts(a.x, a.y, angle, CYAN, 9, 210, 0.42, 2.0, 0.5)
        self.fx.add_ring(b.x, b.y, 5, 36, CYAN, 0.35, 2)
        self.fx.add_flash(0.03, CYAN, 12)
        self.fx.add_shake(1.0, 10)

    def _weak(self, p):
        a, b, angle = p["a"], p["b"], p["angle"]
        label = p["label"]
        self.fx.add_dir_parts(a.x, a.y, angle, PURPLE, 8, 200, 0.4, 2.0, 0.5)
        self.fx.add_ring(b.x, b.y, 6, 34, PURPLE, 0.35, 2)
        if label == "STRONG→WEAK":
            self.fx.add_text(b.x, b.y - b.r - 14, label, PURPLE, 13, 0.8)
        else:
            self.fx.add_text(b.x, b.y - b.r - 14, label, PURPLE, 12, 0.75)
        self.fx.add_shake(1.6, 8)

    def _weaken_edge(self, p):
        e = p["edge"]
        self.fx.add_spark((e.src.x, e.src.y), (e.dst.x, e.dst.y),
                          PURPLE, 0.3, 3)
        self.fx.add_text(e.dst.x, e.dst.y - e.dst.r - 10, "WEAKEN",
                         PURPLE, 14, 0.9)

    def _sweep(self, p):
        x, y = p["point"]
        self.fx.add_ring(x, y, 10, 170, GREEN, 0.45, 4)
        self.fx.add_text(x, y - 20, f"SWEEP x{p['count']}", GREEN, 18, 1.0)

    def _alias(self, p):
        a, b, mid = p["a"], p["b"], p["mid"]
        self.fx.add_ring(a.x, a.y, 6, 48, MAGENTA, 0.45, 3)
        self.fx.add_ring(b.x, b.y, 6, 48, MAGENTA, 0.45, 3)
        self.fx.add_ring(mid[0], mid[1], 10, 90, MAGENTA, 0.55, 3)
        self.fx.add_parts(mid[0], mid[1], MAGENTA, 22, 240, 0.6, 2.6)
        self.fx.add_text(mid[0], mid[1] - 26, "ALIAS", MAGENTA, 18, 1.0)
        self.fx.add_flash(0.12, MAGENTA, 5)
        self.fx.add_shake(6, 5)

    def _cast(self, p):
        n, color = p["node"], p["color"]
        self.fx.add_ring(n.x, n.y, n.r * 0.5, n.r * 2.4, color, 0.5, 3)
        self.fx.add_flash(0.05, color, 9)
        self.fx.add_shake(2.2, 8)
        self.fx.add_parts(n.x, n.y, color, 14, 170, 0.5, 2.0)
        label = "CAST<void>" if p["void"] else "CAST<int>"
        self.fx.add_text(n.x, n.y - n.r - 16, label, color, 15, 1.1)

    def _reflect(self, p):
        self.fx.add_spark(p["start"], p["end"], GOLD, 0.4, 3)

    def _steal(self, p):
        e, dst = p["edge"], p["dst"]
        self.fx.add_spark((e.src.x, e.src.y), (dst.x, dst.y),
                          GREEN, 0.35, 3)
        self.fx.add_text(dst.x, dst.y - dst.r - 12, "STOLEN",
                         GREEN, 15, 1.1)

    def _compress(self, p):
        n = p["player"]
        self.fx.add_flash(0.15, RED, 5)
        self.fx.add_glitch(0.35)
        self.fx.add_text(n.x, n.y - 42, "COMPRESS +30%", RED, 18, 1.2)

    def _ecc(self, p):
        n, count = p["player"], p["count"]
        for _ in range(count):
            self.fx.add_parts(n.x, n.y, GREEN, 12, 160, 0.6, 2.0)
        self.fx.add_ring(n.x, n.y, 8, 80, GREEN, 0.5, 3)

    def _downsample(self, p):
        x, y = p["point"]
        self.fx.add_flash(0.15, CYAN, 5)
        self.fx.add_ring(x, y, 10, 260, CYAN, 0.6, 3)

    def _delay_set(self, p):
        n, delay = p["player"], p["delay"]
        self.fx.add_text(n.x, n.y - 40, f"DELAY {delay:.0f}s",
                         AMBER, 15, 0.9)

    def _lossy(self, p):
        self.fx.add_shake(14, 3)

    def _explode(self, p):
        x, y, rad, color = p["x"], p["y"], p["radius"], p["color"]
        if p["dud"]:
            self.fx.add_ring(x, y, 10, rad, GREEN, 0.4, 3)
            return
        self.fx.add_ring(x, y, 10, rad, color, 0.55, 5)
        self.fx.add_parts(x, y, color, 28, 280, 0.7, 2.6)
        self.fx.add_flash(0.25, color, 3)
        self.fx.add_shake(8, 4)

    def _damage(self, p):
        n, dmg, color, mode = p["node"], p["dmg"], p["color"], p["mode"]
        if mode == "immune":
            self.fx.add_text(n.x, n.y - n.r - 14, "IMMUNE", DIM, 14, 0.7)
            return
        if mode == "shielded":
            self.fx.add_text(n.x, n.y - n.r - 14, "SHIELD", AMBER, 14, 0.6)
        self.fx.add_text(n.x, n.y - n.r, f"-{int(dmg)}", color, 15, 0.6)
        if mode != "alias":
            self.fx.add_parts(n.x, n.y, color, 5, 110, 0.3, 1.6)

    def _node_killed(self, p):
        n = p["node"]
        color = NODE_COLOR.get(n.kind, WHITE)
        self.fx.add_parts(n.x, n.y, color, 12, 160, 0.5, 2.0)
        self.fx.add_ring(n.x, n.y, 6, 46, color, 0.35, 2)
        self.fx.add_flash(0.03, color, 12)
        self.fx.add_shake(2.0, 8)
        if n.data.get("boss"):
            self.fx.add_flash(0.28, WHITE, 3)
            self.fx.add_shake(16, 2.5)

    def _alias_pool_killed(self, p):
        self.fx.add_flash(0.35, MAGENTA, 3)
        self.fx.add_glitch(0.5)

    def _score(self, p):
        n, score = p["node"], p["score"]
        self.fx.add_text(n.x + 18, n.y, f"+{score}", GREEN, 13, 0.7)

    def _leak(self, p):
        n = p["node"]
        self.fx.add_text(n.x, n.y - 20, "LEAK", DIM, 14, 1.0)

    def _gc_shockwave(self, p):
        n, radius, color = p["node"], p["radius"], p["color"]
        self.fx.add_ring(n.x, n.y, max(6.0, n.r * 0.5), radius, color, 0.55, 4)
        self.fx.add_ring(n.x, n.y, max(4.0, n.r * 0.35), radius * 0.72,
                         color, 0.40, 2)
        if p["big"]:
            self.fx.add_flash(0.06, color, 5)
            self.fx.add_shake(7, 4)

    def _shock_hit(self, p):
        n, color = p["player"], p["color"]
        if p["corrupt"]:
            self.fx.add_text(n.x, n.y - 48, "CORRUPT", MAGENTA, 14, 1.0)
        self.fx.add_text(n.x, n.y - 34, f"SHOCK -{int(p['dmg'])}",
                         color, 15, 0.7)

    def _gc_erased(self, p):
        n = p["node"]
        self.fx.add_parts(n.x, n.y, CYAN, 10, 130, 0.5, 1.8)
        self.fx.add_text(n.x, n.y - n.r - 14, "GC", CYAN, 14, 0.8)
        self.fx.add_flash(0.025, CYAN, 14)
        self.fx.add_shake(3, 6)

    def _cascade(self, p):
        tier, n = p["tier"], p["player"]
        if tier == 3:
            self.fx.add_text(n.x, n.y - 44, "CASCADE x3  工作内存 +1",
                             GREEN, 18, 1.2)
        elif tier == 5:
            self.fx.add_text(n.x, n.y - 44, "CASCADE x5  抽 1 张",
                             GREEN, 19, 1.3)
        else:
            self.fx.add_flash(0.3, GREEN, 4)
            self.fx.add_glitch(0.8)
            self.fx.add_text(n.x, n.y - 50, "CASCADE x8  免费 GC",
                             GREEN, 22, 1.5)

    def _alias_expired(self, p):
        n = p["player"]
        self.fx.add_text(n.x, n.y - 30, "ALIAS EXPIRED", MAGENTA, 13, 0.8)

    def _ward(self, p):
        t = p["target"]
        self.fx.add_ring(t.x, t.y, t.r + 4, t.r + 26, BLUE, 0.4, 2)
        self.fx.add_text(t.x, t.y - t.r - 12, "WARD", BLUE, 10, 0.5)

    def _reinforcement(self, p):
        self.fx.add_shake(2.0, 8)
        self.fx.add_ring(p["x"], p["y"], 6, 50, AMBER, 0.45, 2)

    def _minion_spawn(self, p):
        x, y = p["x"], p["y"]
        self.fx.add_ring(x, y, 4, 34, TEAL, 0.4, 2)
        self.fx.add_text(x, y - 24, "ALLOC", TEAL, 12, 0.8)

    def _melee_telegraph(self, p):
        n = p["node"]
        self.fx.add_ring(n.x, n.y, n.r * 0.6, n.r * 3.2, GOLD, 0.35, 3)
        self.fx.add_text(n.x, n.y - n.r - 14, "CUT!", GOLD, 16, 0.7)

    def _melee_windup(self, p):
        n = p["node"]
        self.fx.add_text(n.x, n.y - n.r - 12, "WINDUP", RED, 12, 0.5)

    def _melee_hit(self, p):
        n, player = p["node"], p["player"]
        self.fx.add_spark((n.x, n.y), (player.x, player.y), RED, 0.28, 4)
        self.fx.add_flash(0.05, RED, 8)
        self.fx.add_shake(5, 6)

    def _cycler_link(self, p):
        n, other = p["node"], p["other"]
        self.fx.add_spark((n.x, n.y), (other.x, other.y), PURPLE, 0.3, 2)

    def _boss_exposed(self, p):
        n = p["node"]
        self.fx.add_flash(0.22, MAGENTA, 4)
        self.fx.add_shake(12, 3.5)
        self.fx.add_ring(n.x, n.y, 20, 220, MAGENTA, 0.7, 5)
        self.fx.add_text(n.x, n.y - 70, "CORE EXPOSED", MAGENTA, 24, 1.6)

    def _boss_ring(self, p):
        n = p["node"]
        self.fx.add_ring(n.x, n.y, 20, 120, MAGENTA, 0.5, 4)

    def _audit(self, p):
        n = p["node"]
        if p["corrupted"]:
            self.fx.add_glitch(0.4)
        self.fx.add_text(n.x, n.y - n.r - 16, "AUDIT", AMBER, 15, 0.9)

    def _bad_access(self, p):
        n = p["player"]
        self.fx.add_text(n.x, n.y - 40, "BAD ACCESS", RED, 14, 1.0)

    def _player_hurt(self, p):
        n, dmg, mode = p["player"], p["dmg"], p["mode"]
        if mode == "alias":
            self.fx.add_text(n.x, n.y - 30, f"-{int(dmg)}", RED, 17, 0.7)
            return
        self.fx.add_flash(0.10, RED, 6)
        self.fx.add_shake(5, 6)
        self.fx.add_text(n.x, n.y - 34, f"-{int(dmg)}", RED, 17, 0.8)
        if p["linked"]:
            share = p["share"]
            self.fx.add_text(n.x, n.y - 52,
                             f"HOLD -{int(share * 100)}%", CYAN, 11, 0.6)

    def _player_died(self, p):
        n, reason = p["player"], p["reason"]
        self.fx.add_flash(0.55, (255, 40, 50), 2.2)
        self.fx.add_glitch(1.2)
        self.fx.add_shake(20, 2.2)
        text = "SEGFAULT" if reason == "hp" else "RENDER CRASH"
        self.fx.add_text(n.x, n.y - 60, text, RED, 34, 2.0)

    def _redundancy(self, p):
        self.fx.add_flash(0.2, GREEN, 4)

    def _dash(self, p):
        n, start, end = p["player"], p["start"], p["end"]
        self.fx.add_spark(start, end, CYAN, 0.3, 4)
        self.fx.add_ring(end[0], end[1], 8, 40, CYAN, 0.3, 2)

    def _write(self, p):
        start, end = p["start"], p["end"]
        self.fx.add_spark(start, end, CYAN, 0.18, 3)
        mid = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
        self.fx.add_parts(mid[0], mid[1], CYAN, 4, 90, 0.25, 1.5)

    def _write_hit(self, p):
        if p["hit"]:
            self.fx.add_flash(0.018, CYAN, 16)
            self.fx.add_shake(1.8, 10)

    def _free_gc(self, p):
        self.fx.add_flash(0.18, CYAN, 6)
        self.fx.add_glitch(0.3)

    def _dead_code(self, p):
        self.fx.add_flash(0.2, CYAN, 5)

    def _slash_trail(self, p):
        x, y = p["pos"]
        self.fx.add_parts(x, y, CYAN, 1, 40, 0.18, 1.2)

    def _target_pick(self, p):
        n, color = p["node"], p["color"]
        self.fx.add_ring(n.x, n.y, 5, 28, color, 0.25, 2)

    def _room_clear(self, p):
        n = p["player"]
        self.fx.add_flash(0.35, GREEN, 2.4)
        self.fx.add_glitch(0.25)
        self.fx.add_text(n.x, n.y - 70, "ROOM CLEARED", GREEN, 30, 2.0)
