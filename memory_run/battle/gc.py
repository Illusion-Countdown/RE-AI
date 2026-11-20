# -*- coding: utf-8 -*-
from .deps import *

class GcMixin:
    def apply_damage(self, n, dmg, color=WHITE, source=None):
        if n is None or not n.alive:
            return
        if n.kind == "ROOT":
            return
        if n.data.get("weak_mark"):
            dmg *= 1.35
        if n.data.get("shield_t", 0) > 0:
            dmg *= 0.55
        if n.data.get("boss") == "gc" and any(
                p.alive and p.kind == "PYLON" for p in self.graph.nodes):
            self.bus.emit(events.BATTLE_DAMAGE, node=n, dmg=dmg,
                          color=DIM, mode="immune", shielded=False)
            return
        shielded = False
        if n.data.get("boss") == "auditor" and self.quality() < 75.0:
            q = self.quality()
            dmg *= max(0.2, 1.0 - (75.0 - q) * 0.04)
            shielded = True
        if n.alias:
            pool = n.alias
            pool.hp -= dmg
            pool.sync()
            n.hit_flash = 1.0
            self.bus.emit(events.BATTLE_DAMAGE, node=n, dmg=dmg,
                          color=color, mode="alias", shielded=shielded)
            if pool.hp <= 0:
                self.kill_pool(pool)
            return
        n.hp -= dmg
        n.hit_flash = 1.0
        self.stats["dmg"] += dmg
        self.run.stats["dmg"] += dmg
        self.bus.emit(events.BATTLE_DAMAGE, node=n, dmg=dmg, color=color,
                      mode="shielded" if shielded else "normal",
                      shielded=shielded)
        if n.hp <= 0:
            self.kill_node(n, source=source)

    def kill_pool(self, pool):
        members = list(pool.alive_members())
        pool.clear()
        self.aliases = [a for a in self.aliases if a is not pool]
        if pool is self.alias_pool:
            self.alias_pool = None
        for m in members:
            if m is self.player_node:
                self.die("alias")
            elif m.alive:
                self.kill_node(m, source="alias")
        self.bus.emit(events.BATTLE_ALIAS_POOL_KILLED)

    def kill_node(self, n, source=None):
        if n is None or not n.alive:
            return
        if n is self.player_node:
            self.die("self")
            return
        x, y, kind = n.x, n.y, n.kind
        dtor = (n.data.get("destructor") and
                not n.data.get("cast_stripped")) or kind == "BOMB"
        if dtor:
            if self.run.has("exception") and not self.exception_used:
                self.exception_used = True
                self.pending_explosions.append((x, y, 150, 0, "exception"))
                self.toast("异常捕获：第一次析构伤害被吃掉")
            else:
                self.pending_explosions.append((x, y, 160, 26, "dtor"))
        self.graph.remove_node(n)
        self.clock.add_hitstop(0.015)
        if n.data.get("boss"):
            self.clock.slow(0.28, 0.9)
        self.bus.emit(events.BATTLE_NODE_KILLED, node=n, source=source)
        self.note_erase(n, source)
        if source in ("write", "lossy") and not self.run.has("inline") and \
                (n.data.get("boss") or n.max_hp >= 100 or self.run.rng.random() < 0.15):
            if self.run.add_dead_cells(1):
                self.bus.emit(events.BATTLE_LEAK, node=n)
        self.gc_dirty = True
        self.resolve_gc()

    def note_erase(self, n, source=None):
        self.erase_streak += 1
        self.streak_t = 3.0 if self.run.has_rule("window") else 2.0
        self.run.stats["gc"] += 1
        self.stats["gc"] += 1
        score = 60 * self.erase_streak
        self.run.score += score
        self.bus.emit(events.BATTLE_SCORE, node=n, score=score)
        if self.erase_streak >= 3 and 3 not in self.cascade_marks:
            self.cascade_marks.add(3)
            self.work_used = max(0.0, self.work_used - 1)
            self.run.shards += 1
            self.bus.emit(events.BATTLE_CASCADE, tier=3, player=self.player_node)
        if self.erase_streak >= 5 and 5 not in self.cascade_marks:
            self.cascade_marks.add(5)
            self.work_used = max(0.0, self.work_used - 2)
            self.draw_one()
            self.bus.emit(events.BATTLE_CASCADE, tier=5, player=self.player_node)
        if self.erase_streak >= 8 and 8 not in self.cascade_marks:
            self.cascade_marks.add(8)
            self.run.shards += 2
            self.gc_dirty = True
            self.extra_gc = True
            self.clock.slow(0.35, 0.55)
            self.bus.emit(events.BATTLE_CASCADE, tier=8, player=self.player_node)

    def explode(self, x, y, rad, dmg, color=GOLD, hit_player=True):
        hit = set()
        for n in list(self.graph.hostiles()):
            if not n.alive:
                continue
            if n.alias:
                if n.alias.gid in hit:
                    continue
                hit.add(n.alias.gid)
            d = vdist(n.x, n.y, x, y)
            if d <= rad + n.r * 0.5:
                self.apply_damage(n, dmg * (1 - 0.35 * d / rad), color,
                                  source="lossy" if dmg > 40 else "boom")
        if hit_player:
            d = vdist(self.player_node.x, self.player_node.y, x, y)
            if d <= rad:
                self.damage_player(dmg * 0.25 * (1 - d / rad), force=True)
        self.bus.emit(events.BATTLE_EXPLODE, x=x, y=y, radius=rad,
                      color=color, dud=False)

    def flush_explosions(self):
        while self.pending_explosions:
            x, y, rad, dmg, kind = self.pending_explosions.pop(0)
            if dmg > 0:
                self.explode(x, y, rad, dmg, GOLD)
            else:
                self.bus.emit(events.BATTLE_EXPLODE, x=x, y=y, radius=rad,
                              color=GREEN, dud=True)

    def shock_radius(self, n, count, max_depth):
        """按当前子树大小和深度缩放；清掉子节点后半径会下降。"""
        base = n.r * 4.5
        radius = base * (1.0 + 0.85 * count + 1.0 * max_depth)
        return min(780.0, radius)

    def shock_damage(self, count, max_depth, dist, radius):
        base = 4.0 + min(12.0, 0.9 * count + 2.0 * max_depth)
        falloff = max(0.35, 1.0 - 0.65 * dist / max(1.0, radius))
        return base * falloff

    def apply_shockwave(self, n, count, max_depth):
        radius = self.shock_radius(n, count, max_depth)
        dist = vdist(n.x, n.y, self.player_node.x, self.player_node.y)
        color = WHITE if radius > 500 else CYAN
        # GC 环本身就是冲击波：从节点半径扩到冲击半径
        self.bus.emit(events.BATTLE_GC_SHOCKWAVE, node=n, radius=radius,
                      color=color, big=radius > 360)
        if self.state != "playing" or dist > radius:
            return
        dmg = self.shock_damage(count, max_depth, dist, radius)
        self.damage_player(dmg, force=True)
        added = bool(self.run.add_dead_cells(1))
        self.bus.emit(events.BATTLE_SHOCK_HIT, player=self.player_node,
                      dmg=dmg, color=color, corrupt=added)

    def resolve_gc(self):
        if not self.gc_dirty:
            return
        if self._resolving:
            return
        self._resolving = True
        self.gc_dirty = False
        try:
            for _ in range(120):
                victim = None
                for n in self.graph.nodes:
                    if not n.alive or n is self.player_node or n.kind == "ROOT":
                        continue
                    if not n.collectible or n.immortal:
                        continue
                    if self.graph.refcount(n) == 0:
                        victim = n
                        break
                if victim is None:
                    self.flush_explosions()
                    if self.gc_dirty:
                        self.gc_dirty = False
                        continue
                    break
                self.gc_erase(victim)
            if self.extra_gc:
                self.extra_gc = False
                self.gc_dirty = True
        finally:
            self._resolving = False
        if self.gc_dirty:
            self.resolve_gc()
        self.check_clear()

    def gc_erase(self, n):
        x, y, kind = n.x, n.y, n.kind
        count, max_depth = self.graph.subtree_stats(n)
        dtor = (n.data.get("destructor") and
                not n.data.get("cast_stripped")) or kind == "BOMB"
        if dtor:
            self.pending_explosions.append((x, y, 160, 26, "dtor"))
        self.graph.remove_node(n)
        self.apply_shockwave(n, count, max_depth)
        self.clock.add_hitstop(0.012)
        self.bus.emit(events.BATTLE_GC_ERASED, node=n)
        self.note_erase(n, source="gc")
        self.gc_dirty = True

    def check_clear(self):
        if self.state not in ("playing", "intro"):
            return
        for n in self.graph.nodes:
            if not n.alive or not n.hostile or n.kind == "ROOT":
                continue
            return
        self.state = "clear"
        self.ending = "clear"
        self.end_t = 1.8
        self.aim = None
        self.bus.emit(events.BATTLE_ROOM_CLEAR, player=self.player_node)

    # ================================================================ 战斗更新
