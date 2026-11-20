# -*- coding: utf-8 -*-
from .deps import *

class PlayerMixin:
    def update_player(self, dt, inp):
        if self.iframe > 0:
            self.iframe -= dt
        if self.hurt_flash > 0:
            self.hurt_flash -= dt
        if self.spawn_flash > 0:
            self.spawn_flash -= dt
        if self.compress_t > 0:
            self.compress_t -= dt
        if self.slow_t > 0:
            self.slow_t -= dt
        if self.write_cd > 0:
            self.write_cd -= dt
        if self.dash_t > 0:
            self.dash_t -= dt
            self.iframe = max(self.iframe, 0.12)
        if self.dash_cd > 0:
            self.dash_cd -= dt
        mvx = inp.get("mvx", 0)
        mvy = inp.get("mvy", 0)
        l = math.hypot(mvx, mvy)
        if l > 1e-6:
            mvx /= l
            mvy /= l
        sp = self.speed
        self.player_node.vx = approach(getattr(self.player_node, "vx", 0.0),
                                       mvx * sp, 2600 * dt)
        self.player_node.vy = approach(getattr(self.player_node, "vy", 0.0),
                                       mvy * sp, 2600 * dt)
        self.player_node.x += self.player_node.vx * dt
        self.player_node.y += self.player_node.vy * dt
        if inp.get("dash") and self.dash_cd <= 0:
            self.dash_cd = 1.8
            self.dash_t = 0.16
            dx = self.mouse[0] - self.player_node.x
            dy = self.mouse[1] - self.player_node.y
            d = math.hypot(dx, dy) or 1
            self.player_node.x += dx / d * 150
            self.player_node.y += dy / d * 150
            self.fx.add_spark((self.player_node.x - dx / d * 140,
                               self.player_node.y - dy / d * 140),
                              (self.player_node.x, self.player_node.y), CYAN, 0.3, 4)
            self.fx.add_ring(self.player_node.x, self.player_node.y, 8, 40, CYAN, 0.3, 2)
            audio.play("dash")
        self.player_node.x = clamp(self.player_node.x, PLAY.x + 16, PLAY.right - 16)
        self.player_node.y = clamp(self.player_node.y, PLAY.y + 16, PLAY.bottom - 16)
        # 玩家不能穿过敌人
        for n in self.graph.hostiles():
            d = vdist(self.player_node.x, self.player_node.y, n.x, n.y)
            rr = PLAYER_R + n.r
            if 0.01 < d < rr:
                push = (rr - d)
                self.player_node.x += (self.player_node.x - n.x) / d * push
                self.player_node.y += (self.player_node.y - n.y) / d * push

    def update_work(self, dt):
        if self.work_used > 0:
            self.work_used = max(0.0, self.work_used - dt / self.work_regen)

    def update_status(self, dt):
        if self.banner_t > 0:
            self.banner_t -= dt
        if self.toast_t > 0:
            self.toast_t -= dt
        self.quality_drain = 0.0
        for n in self.graph.nodes:
            if n.alive and n.kind == "QUANTIZER":
                self.quality_drain += 10.0
            if n.alive:
                n.data["weak_mark"] = any(
                    e.alive and e.dst is n and e.kind == WEAK
                    for e in self.graph.edges)
                if n.data.get("shield_t", 0) > 0:
                    n.data["shield_t"] = max(0.0, n.data["shield_t"] - dt)
            if n.stun > 0:
                n.stun -= dt
            if n.hit_flash > 0:
                n.hit_flash -= dt
            n.spin += dt
            if n.born_anim > 0:
                n.born_anim = max(0.0, n.born_anim - dt)
            if n.data.get("cast_disable", 0) > 0:
                n.data["cast_disable"] -= dt

    def update_cascade(self, dt):
        if self.streak_t > 0:
            self.streak_t -= dt
        else:
            self.erase_streak = 0

    def update_quality(self, dt):
        if self.redundancy_t > 0:
            self.redundancy_t -= dt
        q = self.quality()
        self.run.note_quality(q)
        if q <= 0.05:
            self.crash_t += dt
            if self.crash_t > 1.2:
                self.die("render")
        else:
            self.crash_t = max(0.0, self.crash_t - dt)
        total = self.deck.grid.w * self.deck.grid.h
        if len(self.deck.grid.dead) >= total * 0.5:
            self.die("necro")
        if self.run.has("redundancy") and q < 25 and not self.run._redundancy_used_room():
            self.run.mark_redundancy()
            self.redundancy_t = 2.0
            self.work_used = max(0.0, self.work_used - 1)
            self.fx.add_flash(0.2, GREEN, 4)
            self.toast("冗余校验：画质从崩溃边缘被拉回 50%")

    def update_pending(self, dt):
        for item in list(self.pending_cuts):
            item["t"] -= dt
            if item["t"] <= 0:
                self.pending_cuts.remove(item)
                if item["edge"].alive:
                    self.cut_edge(item["edge"])

    def update_aliases(self, dt):
        for pool in list(self.aliases):
            pool.t -= dt
            if pool.t <= 0:
                pool.clear()
                self.aliases.remove(pool)
                if pool is self.alias_pool:
                    self.alias_pool = None
                self.fx.add_text(self.player_node.x, self.player_node.y - 30,
                                 "ALIAS EXPIRED", MAGENTA, 13, 0.8)

    # ================================================================ 玩家受伤

    def damage_player(self, amount, force=False):
        if amount <= 0:
            return
        if self.iframe > 0 and not force:
            return
        linked = [n for n in self.graph.hostiles()
                  if n.alive and self.graph.between(self.player_node, n, STRONG)]
        share = min(0.45, 0.15 * len(linked))
        taken = amount * (1.0 - share)
        if linked and share > 0:
            each = amount * share / len(linked)
            for n in linked:
                self.apply_damage(n, each, CYAN)
        if self.alias_pool and any(m is self.player_node for m in self.alias_pool.members):
            self.alias_pool.hp -= taken
            self.alias_pool.sync()
            self.hp = max(0.0, self.alias_pool.hp)
            self.fx.add_text(self.player_node.x, self.player_node.y - 30,
                             f"-{int(taken)}", RED, 17, 0.7)
            if self.alias_pool.hp <= 0:
                self.kill_pool(self.alias_pool)
            return
        self.hp -= taken
        self.run.hp = max(0.0, self.hp)
        self.run.note_damage()
        self.iframe = 0.7
        self.hurt_flash = 1.0
        self.fx.add_flash(0.10, RED, 6)
        self.fx.add_shake(5, 6)
        self.fx.add_text(self.player_node.x, self.player_node.y - 34,
                         f"-{int(taken)}", RED, 17, 0.8)
        if linked:
            self.fx.add_text(self.player_node.x, self.player_node.y - 52,
                             f"HOLD -{int(share * 100)}%", CYAN, 11, 0.6)
        audio.play("hurt")
        if self.hp <= 0:
            self.die("hp")

    def die(self, reason="hp"):
        if self.state in ("dead", "clear"):
            return
        self.state = "dead"
        self.ending = reason
        self.end_t = 1.6
        self.hp = 0
        self.run.hp = 0
        self.fx.add_flash(0.55, (255, 40, 50), 2.2)
        self.fx.add_glitch(1.2)
        self.fx.add_shake(20, 2.2)
        self.fx.add_hitstop(0.16)
        self.fx.add_text(self.player_node.x, self.player_node.y - 60,
                         "SEGFAULT" if reason == "hp" else "RENDER CRASH",
                         RED, 34, 2.0)
        audio.play("death")

    # ================================================================ WRITE

    def write_attack(self):
        if self.write_cd > 0:
            return
        self.write_cd = 0.38
        px, py = self.player_node.x, self.player_node.y
        mx, my = self.mouse
        ang = math.atan2(my - py, mx - px)
        best = None
        bestd = 1e9
        for n in self.graph.hostiles():
            if not n.alive:
                continue
            d = vdist(px, py, n.x, n.y)
            if d > WRITE_RANGE or d < 1:
                continue
            a = math.atan2(n.y - py, n.x - px)
            diff = abs((a - ang + math.pi) % math.tau - math.pi)
            if diff < 0.55 and d < bestd:
                best = n
                bestd = d
        tx, ty = (best.x, best.y) if best else (mx, my)
        self.fx.add_spark((px, py), (tx, ty), CYAN, 0.18, 3)
        self.fx.add_parts((px + tx) / 2, (py + ty) / 2, CYAN, 4, 90, 0.25, 1.5)
        if best:
            dmg = 16.0 * self.damage_mult()
            if self.run.has("inline"):
                dmg *= 1.5
            if self.run.has("lossless") and self.quality() >= 75:
                dmg *= 1.2
            if self.run.has("wreck"):
                dmg *= 1.0 + min(0.30, len(self.deck.grid.dead) * 0.03)
            self.apply_damage(best, dmg, CYAN, source="inline" if self.run.has("inline") else "write")
            self.fx.add_flash(0.018, CYAN, 16)
            self.fx.add_hitstop(0.012)
            self.fx.add_shake(1.8, 10)
        audio.play("write")

    # ================================================================ 敌人
