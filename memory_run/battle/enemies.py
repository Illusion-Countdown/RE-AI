# -*- coding: utf-8 -*-
from .deps import *

class EnemiesMixin:
    def add_reinforcements(self, by_id):
        """提高压力但不堆小怪：给编队补 WARD/PYLON 支援，而不是塞 MINION。"""
        if self.room.get("tutorial") or self.room.get("boss"):
            self.wave_left = 1 if int(self.room.get("danger", 1)) >= 8 else 0
            return
        danger = int(self.room.get("danger", 1))
        parent = by_id.get("scope")
        for n in self.graph.nodes:
            if n.kind in ("SENTINEL", "ALLOCATOR"):
                parent = n
                break
        if parent is None:
            return
        has_ward = any(n.kind == "WARD" for n in self.graph.nodes)
        if danger >= 5 and not has_ward:
            x = PLAY.centerx + PLAY.w * 0.22
            y = PLAY.y + PLAY.h * 0.28
            w = Node("WARD", x, y, "SUPPORT.WARD",
                     hp=45 + danger * 6, r=18)
            w.data["barrier"] = True
            w.timers["atk"] = self.run.rng.uniform(0.8, 2.0)
            w.timers["special"] = 2.0
            w.hostile = True
            w.targetable = True
            w.spawn_t = 0.0
            w.born_anim = 0.45
            self.graph.add_node(w)
            self.graph.add_edge(parent, w, STRONG, unique=False)
            by_id["support_ward"] = w
        if danger >= 8:
            x = PLAY.centerx - PLAY.w * 0.24
            y = PLAY.y + PLAY.h * 0.30
            p = Node("PYLON", x, y, "SUPPORT.PYLON",
                     hp=35 + danger * 4, r=17)
            p.hostile = True
            p.targetable = True
            p.timers["atk"] = self.run.rng.uniform(0.8, 2.2)
            p.spawn_t = 0.0
            p.born_anim = 0.45
            self.graph.add_node(p)
            self.graph.add_edge(parent, p, STRONG, unique=False)
            by_id["support_pylon"] = p
        self.wave_left = 1 if danger >= 8 else 0
        self.wave_t = 8.0

    def spawn_wave(self):
        if self.wave_left <= 0 or self.room.get("tutorial"):
            return
        hubs = [n for n in self.graph.nodes if n.alive and
                n.kind in ("SENTINEL", "ALLOCATOR", "GC_CORE",
                           "AUDITOR", "KERNEL")]
        parent = hubs[0] if hubs else self.root
        if parent is None:
            return
        danger = int(self.room.get("danger", 1))
        # 协同增援：一个带辐条的 SENTINEL，而不是两隻小怪
        x = clamp(parent.x + self.run.rng.uniform(-90, 90),
                  PLAY.x + 30, PLAY.right - 30)
        y = clamp(parent.y + self.run.rng.uniform(60, 120),
                  PLAY.y + 30, PLAY.bottom - 30)
        e = Node("SENTINEL", x, y, "REINFORCE.ELITE",
                 hp=50 + danger * 6, r=20)
        e.hostile = True
        e.targetable = True
        e.timers["atk"] = self.run.rng.uniform(0.8, 2.0)
        e.spawn_t = 0.0
        e.born_anim = 0.45
        self.graph.add_node(e)
        self.graph.add_edge(parent, e, STRONG, unique=False)
        self.by_id[f"wave{self.wave_left}"] = e
        self.wave_left -= 1
        self.toast("敌方支援到位：SENTINEL 加入编队", 1.6)
        self.fx.add_shake(2.0, 8)
        self.fx.add_ring(x, y, 6, 50, AMBER, 0.45, 2)

    def update_waves(self, dt):
        if self.state != "playing" or self.wave_left <= 0:
            return
        self.wave_t -= dt
        if self.wave_t <= 0:
            self.spawn_wave()

    def update_enemies(self, dt):
        for n in list(self.graph.nodes):
            if not n.alive or not n.hostile or n.kind == "ROOT":
                continue
            if n.stun > 0:
                continue
            held = self.graph.between(self.player_node, n, STRONG)
            if held:
                n.data["held"] = True
                continue
            n.data["held"] = False
            if n.data.get("cast_disable", 0) > 0:
                continue
            if n.data.get("boss"):
                self.update_boss(n, dt)
                continue
            if n.kind in ("LUNGER", "SLASHER", "EXECUTOR"):
                self.update_melee(n, dt)
                continue
            if n.kind == "MINION":
                self.enemy_move(n, dt, 72.0, 175.0)
                self.enemy_attack(n, dt, 2.2, 180, 4.0, RED)
            elif n.kind == "SENTINEL":
                self.enemy_attack(n, dt, 2.6, 210, 5.0, AMBER)
            elif n.kind == "PYLON":
                self.enemy_attack(n, dt, 3.2, 190, 4.0, MAGENTA)
            elif n.kind == "CYCLER":
                self.cycler_tick(n, dt)
                self.enemy_attack(n, dt, 2.8, 220, 5.0, PURPLE)
            elif n.kind == "ALLOCATOR":
                self.enemy_attack(n, dt, 3.4, 160, 3.0, TEAL)
                n.timers["special"] -= dt
                if n.timers["special"] <= 0:
                    n.timers["special"] = 5.0
                    self.spawn_minion(n)
            elif n.kind == "WARD":
                # 支援位：周期性给最近友军套盾，而不是自己站桩
                n.timers["special"] = n.timers.get("special", 0.0) - dt
                if n.timers["special"] <= 0:
                    n.timers["special"] = 4.0
                    allies = [x for x in self.graph.hostiles()
                              if x.alive and x is not n and x.kind != "ROOT"]
                    if allies:
                        allies.sort(key=lambda x: vdist(n.x, n.y, x.x, x.y))
                        t = allies[0]
                        t.data["shield_t"] = 4.0
                        self.fx.add_ring(t.x, t.y, t.r + 4, t.r + 26,
                                         BLUE, 0.4, 2)
                        self.fx.add_text(t.x, t.y - t.r - 12, "WARD",
                                         BLUE, 10, 0.5)
            elif n.kind == "KERNEL":
                self.enemy_attack(n, dt, 2.0, 230, 6.0, CYAN)
            elif n.kind == "BOMB":
                self.enemy_move(n, dt, 60.0, 90.0)
            elif n.kind == "QUANTIZER":
                self.enemy_attack(n, dt, 3.0, 170, 4.0, GREEN)
            elif n.kind == "GLITCH":
                self.enemy_move(n, dt, 90.0, 140.0)
                self.enemy_attack(n, dt, 2.4, 180, 4.0, PURPLE)
            elif n.kind == "TEAR":
                self.enemy_attack(n, dt, 2.8, 200, 5.0, RED)
            elif n.kind == "CRAWLER":
                self.enemy_move(n, dt, 110.0, 120.0)
                self.enemy_attack(n, dt, 2.8, 180, 5.0, AMBER, necro=True)
            elif n.kind == "ERASER":
                self.enemy_attack(n, dt, 2.2, 240, 6.0, WHITE)

    def update_melee(self, n, dt):
        cfg = {
            "LUNGER":   (150.0, 62.0, 0.45, 150.0, 10.0, 2.6),
            "SLASHER":  (110.0, 74.0, 0.65, 175.0, 16.0, 3.0),
            "EXECUTOR": (85.0, 90.0, 0.85, 205.0, 24.0, 3.6),
        }[n.kind]
        speed, keep, windup, reach, dmg, period = cfg
        edge = n.data.get("attack_edge")
        if edge is not None and edge.alive:
            n.data["attack_t"] = n.data.get("attack_t", 0.5) - dt
            if n.data["attack_t"] <= 0:
                self.graph.remove_edge(edge)
                n.data["attack_edge"] = None
                if self.state == "playing":
                    self.damage_player(n.data.get("melee_dmg", dmg), force=True)
                    self.fx.add_spark((n.x, n.y),
                                      (self.player_node.x, self.player_node.y),
                                      RED, 0.28, 4)
                    self.fx.add_flash(0.05, RED, 8)
                    self.fx.add_shake(5, 6)
                    audio.play("hurt")
            return
        n.data["attack_edge"] = None
        if n.data.get("windup", 0.0) > 0:
            n.data["windup"] -= dt
            if n.data["windup"] <= 0:
                e = self.graph.add_edge(n, self.player_node, PARRY,
                                        unique=False)
                if e is not None:
                    n.data["attack_edge"] = e
                    n.data["attack_t"] = 0.5
                    n.data["melee_dmg"] = dmg
                    self.fx.add_ring(n.x, n.y, n.r * 0.6, n.r * 3.2,
                                     GOLD, 0.35, 3)
                    self.fx.add_text(n.x, n.y - n.r - 14, "CUT!", GOLD,
                                     16, 0.7)
                    audio.play("weak")
            return
        self.enemy_move(n, dt, speed, keep)
        n.timers["atk"] = n.timers.get("atk", 0.0) - dt
        d = vdist(n.x, n.y, self.player_node.x, self.player_node.y)
        if n.timers["atk"] <= 0 and d <= reach:
            n.data["windup"] = windup
            n.timers["atk"] = period * self.run.rng.uniform(0.9, 1.15)
            self.fx.add_text(n.x, n.y - n.r - 12, "WINDUP", RED, 12, 0.5)
            audio.play("ui")

    def enemy_move(self, n, dt, speed, keep):
        dx = self.player_node.x - n.x
        dy = self.player_node.y - n.y
        d = math.hypot(dx, dy) or 1
        if d > keep:
            n.x += dx / d * speed * dt
            n.y += dy / d * speed * dt
        elif d < keep * 0.65:
            n.x -= dx / d * speed * 0.5 * dt
            n.y -= dy / d * speed * 0.5 * dt
        n.x = clamp(n.x, PLAY.x + n.r, PLAY.right - n.r)
        n.y = clamp(n.y, PLAY.y + n.r, PLAY.bottom - n.r)

    def enemy_attack(self, n, dt, period, speed, dmg, color, necro=False):
        n.timers["atk"] = n.timers.get("atk", 0.0) - dt
        if n.timers["atk"] > 0:
            return
        n.timers["atk"] = period * self.run.rng.uniform(0.85, 1.15)
        rank = int(self.room.get("danger", 1))
        shots = 1 + (1 if rank >= 3 else 0) + (1 if rank >= 6 else 0)
        if rank >= 9:
            shots += 1
        if self.room.get("boss"):
            shots = max(shots, 2)
        n.timers["atk"] *= max(0.62, 1.0 - 0.045 * rank)
        if n.data.get("weak_mark"):
            dmg *= 0.65
        dmg *= 1.0 + max(0, rank - 3) * 0.04
        ang0 = math.atan2(self.player_node.y - n.y, self.player_node.x - n.x)
        sp = speed * (0.65 if self.slow_t > 0 else 1.0) * 1.06
        for i in range(shots):
            ang = ang0 + (i - (shots - 1) / 2) * 0.14
            p = Projectile(n.x, n.y, math.cos(ang) * sp,
                           math.sin(ang) * sp,
                           5 if dmg < 5 else 7, dmg, color, necro=necro)
            self.projectiles.append(p)
        audio.play("write", 0.35)

    def cycler_tick(self, n, dt):
        partner_id = n.data.get("partner")
        if not partner_id:
            return
        other = self.by_id.get(partner_id)
        if other is None or not other.alive:
            return
        if self.graph.between(n, other, WEAK):
            return
        if self.graph.between(n, other, STRONG):
            return
        n.timers["special"] -= dt
        if n.timers["special"] <= 0:
            n.timers["special"] = 1.6
            self.graph.add_edge(n, other, STRONG, unique=False)
            self.fx.add_spark((n.x, n.y), (other.x, other.y), PURPLE, 0.3, 2)
            self.toast("CYCLER 重建了强引用环")

    def spawn_minion(self, parent):
        if not parent.alive:
            return
        alive = [n for n in self.graph.nodes if n.alive and n.kind == "MINION"]
        if len(alive) > 8:
            return
        ang = self.run.rng.uniform(0, math.tau)
        x = clamp(parent.x + math.cos(ang) * 80, PLAY.x + 24, PLAY.right - 24)
        y = clamp(parent.y + math.sin(ang) * 80, PLAY.y + 24, PLAY.bottom - 24)
        m = Node("MINION", x, y, "SPAWN.{}".format(len(alive) + 1))
        m.hp = m.max_hp = 22.0 + self.run.bosses_cleared * 8
        m.r = 20
        m.timers["atk"] = 1.8
        self.graph.add_node(m)
        self.graph.add_edge(parent, m, STRONG, unique=False)
        self.fx.add_ring(x, y, 4, 34, TEAL, 0.4, 2)
        self.fx.add_text(x, y - 24, "ALLOC", TEAL, 12, 0.8)
        audio.play("link", 0.5)

    def update_boss(self, n, dt):
        boss = n.data.get("boss")
        if boss == "gc":
            alive_pylons = [p for p in self.graph.nodes if p.alive and p.kind == "PYLON"]
            if alive_pylons:
                n.data["invuln"] = True
                return
            n.data["invuln"] = False
            if not n.data.get("exposed_announced"):
                n.data["exposed_announced"] = True
                self.fx.add_flash(0.22, MAGENTA, 4)
                self.fx.add_shake(12, 3.5)
                self.fx.add_ring(n.x, n.y, 20, 220, MAGENTA, 0.7, 5)
                self.fx.slow(0.5, 0.5)
                self.fx.add_text(n.x, n.y - 70, "CORE EXPOSED", MAGENTA, 24, 1.6)
                audio.play("gcstart")
                self.toast("三根塔架已断：核心失去免疫")
            n.timers["special"] -= dt
            if n.timers["special"] <= 0:
                n.timers["special"] = 4.0
                for i in range(10):
                    ang = i * math.tau / 10 + self.time * 0.2
                    self.projectiles.append(Projectile(
                        n.x, n.y, math.cos(ang) * 150, math.sin(ang) * 150,
                        7, 5.0, MAGENTA))
                self.fx.add_ring(n.x, n.y, 20, 120, MAGENTA, 0.5, 4)
            n.timers["phase"] -= dt
            if n.timers["phase"] <= 0:
                n.timers["phase"] = 8.0
                self.spawn_minion(n)
            self.enemy_attack(n, dt, 2.4, 220, 6.0, MAGENTA)
        elif boss == "auditor":
            self.enemy_attack(n, dt, 2.4, 210, 6.0, AMBER)
            n.timers["special"] -= dt
            if n.timers["special"] <= 0:
                n.timers["special"] = 6.5
                if len(self.deck.grid.dead) - self.start_dead < 3:
                    if self.run.add_dead_cells(1):
                        self.fx.add_glitch(0.4)
                        self.toast("审计员烧坏了 1 个空闲格｜用 ECC 修回来")
                self.fx.add_text(n.x, n.y - n.r - 16, "AUDIT", AMBER, 15, 0.9)
        elif boss == "kernel":
            self.enemy_attack(n, dt, 2.6, 230, 6.0, CYAN)
            n.timers["special"] -= dt
            if n.timers["special"] <= 0:
                n.timers["special"] = 3.5
                ang = math.atan2(self.player_node.y - n.y, self.player_node.x - n.x)
                for off in (-0.25, 0, 0.25):
                    self.projectiles.append(Projectile(
                        n.x, n.y, math.cos(ang + off) * 210,
                        math.sin(ang + off) * 210, 6, 5.0, CYAN))

    def update_projectiles(self, dt):
        slow = 0.7 if self.slow_t > 0 else 1.0
        for p in list(self.projectiles):
            p.x += p.vx * dt * slow
            p.y += p.vy * dt * slow
            p.life -= dt
            if p.life <= 0 or not PLAY.collidepoint(p.x, p.y):
                self.projectiles.remove(p)
                continue
            if vdist(p.x, p.y, self.player_node.x, self.player_node.y) < p.r + PLAYER_R:
                self.projectiles.remove(p)
                self.damage_player(p.dmg, force=True)
                if p.necro:
                    if len(self.deck.grid.dead) - self.start_dead < 3:
                        if self.run.add_dead_cells(1):
                            self.fx.add_text(self.player_node.x,
                                             self.player_node.y - 40,
                                             "BAD ACCESS", RED, 14, 1.0)

    # ================================================================ 结算
