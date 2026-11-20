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
            self.fx.add_text(n.x, n.y - n.r - 14, "IMMUNE", DIM, 14, 0.7)
            return
        if n.data.get("boss") == "auditor" and self.quality() < 75.0:
            q = self.quality()
            dmg *= max(0.2, 1.0 - (75.0 - q) * 0.04)
            self.fx.add_text(n.x, n.y - n.r - 14, "SHIELD", AMBER, 14, 0.6)
        if n.alias:
            pool = n.alias
            pool.hp -= dmg
            pool.sync()
            n.hit_flash = 1.0
            self.fx.add_text(n.x, n.y - n.r, f"-{int(dmg)}", color, 15, 0.6)
            if pool.hp <= 0:
                self.kill_pool(pool)
            return
        n.hp -= dmg
        n.hit_flash = 1.0
        self.stats["dmg"] += dmg
        self.run.stats["dmg"] += dmg
        self.fx.add_text(n.x, n.y - n.r, f"-{int(dmg)}", color, 15, 0.6)
        self.fx.add_parts(n.x, n.y, color, 5, 110, 0.3, 1.6)
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
        self.fx.add_flash(0.35, MAGENTA, 3)
        self.fx.add_glitch(0.5)
        audio.play("death")

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
        self.fx.add_parts(x, y, NODE_COLOR.get(kind, WHITE), 12, 160, 0.5, 2.0)
        self.fx.add_ring(x, y, 6, 46, NODE_COLOR.get(kind, WHITE), 0.35, 2)
        self.fx.add_flash(0.03, NODE_COLOR.get(kind, WHITE), 12)
        self.fx.add_hitstop(0.015)
        self.fx.add_shake(2.0, 8)
        if n.data.get("boss"):
            self.fx.slow(0.28, 0.9)
            self.fx.add_flash(0.28, WHITE, 3)
            self.fx.add_shake(16, 2.5)
        self.note_erase(n, source)
        if source in ("write", "lossy") and not self.run.has("inline") and \
                (n.data.get("boss") or n.max_hp >= 100 or self.run.rng.random() < 0.15):
            if self.run.add_dead_cells(1):
                self.fx.add_text(x, y - 20, "LEAK", DIM, 14, 1.0)
        self.gc_dirty = True
        self.resolve_gc()

    def note_erase(self, n, source=None):
        self.erase_streak += 1
        self.streak_t = 3.0 if self.run.has_rule("window") else 2.0
        self.run.stats["gc"] += 1
        self.stats["gc"] += 1
        score = 60 * self.erase_streak
        self.run.score += score
        self.fx.add_text(n.x + 18, n.y, f"+{score}", GREEN, 13, 0.7)
        if self.erase_streak >= 3 and 3 not in self.cascade_marks:
            self.cascade_marks.add(3)
            self.work_used = max(0.0, self.work_used - 1)
            self.run.shards += 1
            self.fx.add_text(self.player_node.x, self.player_node.y - 44,
                             "CASCADE x3  工作内存 +1", GREEN, 18, 1.2)
            audio.play("clear")
        if self.erase_streak >= 5 and 5 not in self.cascade_marks:
            self.cascade_marks.add(5)
            self.work_used = max(0.0, self.work_used - 2)
            self.draw_one()
            self.fx.add_text(self.player_node.x, self.player_node.y - 44,
                             "CASCADE x5  抽 1 张", GREEN, 19, 1.3)
            audio.play("clear")
        if self.erase_streak >= 8 and 8 not in self.cascade_marks:
            self.cascade_marks.add(8)
            self.run.shards += 2
            self.gc_dirty = True
            self.extra_gc = True
            self.fx.add_flash(0.3, GREEN, 4)
            self.fx.add_glitch(0.8)
            self.fx.slow(0.35, 0.55)
            self.fx.add_text(self.player_node.x, self.player_node.y - 50,
                             "CASCADE x8  免费 GC", GREEN, 22, 1.5)
            audio.play("hijack")

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
        self.fx.add_ring(x, y, 10, rad, color, 0.55, 5)
        self.fx.add_parts(x, y, color, 28, 280, 0.7, 2.6)
        self.fx.add_flash(0.25, color, 3)
        self.fx.add_shake(8, 4)

    def flush_explosions(self):
        while self.pending_explosions:
            x, y, rad, dmg, kind = self.pending_explosions.pop(0)
            if dmg > 0:
                self.explode(x, y, rad, dmg, GOLD)
            else:
                self.fx.add_ring(x, y, 10, rad, GREEN, 0.4, 3)
                audio.play("weak")

    def shock_radius(self, n, depth):
        """越靠近根，GC 冲击波越大；叶子约为原半径的 4–7 倍。"""
        if depth <= 1:
            return 780.0
        if depth == 2:
            return max(130.0, n.r * 6.0)
        if depth == 3:
            return max(100.0, n.r * 5.0)
        return max(72.0, n.r * 4.5)

    def shock_damage(self, depth, dist, radius):
        base = 16.0 if depth <= 1 else (7.0 if depth == 2 else 4.0)
        falloff = max(0.35, 1.0 - 0.65 * dist / max(1.0, radius))
        return base * falloff

    def apply_shockwave(self, n, depth):
        radius = self.shock_radius(n, depth)
        dist = vdist(n.x, n.y, self.player_node.x, self.player_node.y)
        color = WHITE if depth <= 1 else CYAN
        # GC 环本身就是冲击波：从节点半径扩到冲击半径
        self.fx.add_ring(n.x, n.y, max(6.0, n.r * 0.5), radius,
                         color, 0.55, 4)
        self.fx.add_ring(n.x, n.y, max(4.0, n.r * 0.35), radius * 0.72,
                         color, 0.40, 2)
        if radius > 360:
            self.fx.add_flash(0.06, color, 5)
            self.fx.add_shake(7, 4)
        if self.state != "playing" or dist > radius:
            return
        dmg = self.shock_damage(depth, dist, radius)
        self.damage_player(dmg, force=True)
        added = self.run.add_dead_cells(1)
        if added:
            self.fx.add_text(self.player_node.x, self.player_node.y - 48,
                             "CORRUPT", MAGENTA, 14, 1.0)
        self.fx.add_text(self.player_node.x, self.player_node.y - 34,
                         f"SHOCK -{int(dmg)}", color, 15, 0.7)

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
        depth = n.data.get("root_depth", 99)
        dtor = (n.data.get("destructor") and
                not n.data.get("cast_stripped")) or kind == "BOMB"
        if dtor:
            self.pending_explosions.append((x, y, 160, 26, "dtor"))
        self.graph.remove_node(n)
        self.apply_shockwave(n, depth)
        self.fx.add_parts(x, y, CYAN, 10, 130, 0.5, 1.8)
        self.fx.add_text(x, y - n.r - 14, "GC", CYAN, 14, 0.8)
        self.fx.add_flash(0.025, CYAN, 14)
        self.fx.add_hitstop(0.012)
        self.fx.add_shake(3, 6)
        audio.play("gc")
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
        self.fx.add_flash(0.35, GREEN, 2.4)
        self.fx.add_glitch(0.25)
        self.fx.add_text(self.player_node.x, self.player_node.y - 70,
                         "ROOM CLEARED", GREEN, 30, 2.0)
        audio.play("clear")

    # ================================================================ 战斗更新
