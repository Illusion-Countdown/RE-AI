# -*- coding: utf-8 -*-
"""Independent battle prototype: 2 auto units, 6 enemy types, initial hand, no assembly link."""

from __future__ import annotations

import math
import os
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pygame

from audio import UIAudio

W, H = 1280, 720
ARENA = pygame.Rect(190, 52, 810, 480)
SPRITE_W, SPRITE_H = 160, 90
ASSET = Path(__file__).resolve().parent / "assets" / "chars"
CUTIN_TIME = 0.9
SLASH_MAX_LEN = 300.0

INK = (7, 11, 17)
PANEL = (13, 20, 29)
PANEL2 = (18, 28, 40)
LINE = (38, 56, 72)
TEXT = (222, 238, 248)
MUTED = (119, 143, 160)
DIM = (71, 91, 108)
CYAN = (80, 214, 255)
AMBER = (255, 200, 87)
GREEN = (114, 230, 160)
RED = (255, 92, 105)
PURPLE = (185, 140, 255)
WHITE = (238, 250, 255)
DARK = (4, 8, 13)

# local arena patrol anchors; all are inside DS attack range
DS_PATROL = [(300, 350), (460, 320), (500, 420), (330, 440)]

# start, end, step, fps, loop, trim lead-in / tail
SPECS = {
    ("ds", "idle"): ("待机呼吸休闲", 0, 120, 1, 24, True),
    ("ds", "move"): ("原地漂浮踏步", 8, 112, 1, 24, True),
    ("ds", "attack"): ("鲸鱼吐泡泡特效", 36, 86, 2, 30, False),
    ("ds", "skill"): ("原地跳跃抓碎头顶物品", 8, 96, 2, 30, False),
    ("ds", "ult"): ("蓝鲸现世", 24, 104, 2, 40, False),
    ("ds", "hurt"): ("玩游戏气急败坏", 30, 82, 2, 30, False),
    ("ds", "death"): ("被鼠标拖拽悬空反馈", 24, 112, 2, 30, False),
    ("claude", "idle"): ("待机呼吸休闲", 0, 120, 1, 24, True),
    ("claude", "move"): ("原地漂浮踏步", 8, 112, 1, 24, True),
    ("claude", "attack"): ("工作状态-清点归档", 28, 70, 2, 30, False),
    ("claude", "skill"): ("蝴蝶蜜蜂环绕头顶开花", 20, 96, 2, 30, False),
    ("claude", "ult"): ("书灵现世", 24, 100, 2, 40, False),
    ("claude", "hurt"): ("点击回应-傲娇生气", 34, 94, 2, 30, False),
    ("claude", "death"): ("原地小憩沉眠", 44, 116, 2, 30, False),
}

CLIPS: dict[tuple[str, str], list[pygame.Surface]] = {}


def load_assets():
    for (who, action), (name, start, end, step, fps, loop) in SPECS.items():
        path = ASSET / who / f"{name}.webp"
        sheet = pygame.image.load(str(path)).convert_alpha()
        frames = []
        for i in range(start, end, step):
            c, r = i % 8, i // 8
            frame = sheet.subsurface(pygame.Rect(c * 640, r * 360, 640, 360))
            frame = pygame.transform.scale(frame, (SPRITE_W, SPRITE_H))
            frames.append(frame)
        CLIPS[(who, action)] = frames
        del sheet


class Anim:
    def __init__(self, who, key):
        self.who = who
        self.key = key
        self.frames = CLIPS[(who, key)]
        self.frame = 0.0
        self.fps = SPECS[(who, key)][4]
        self.loop = SPECS[(who, key)][5]
        self.done = False
        self.prev = None
        self.prev_t = 0.0
        self.fade = 0.0

    def play(self, key, fade=0.08):
        if self.key == key:
            return
        self.prev = self.frames[min(len(self.frames) - 1, int(self.frame))]
        self.prev_t = fade
        self.fade = fade
        self.who = self.who
        self.key = key
        self.frames = CLIPS[(self.who, key)]
        self.fps = SPECS[(self.who, key)][4]
        self.loop = SPECS[(self.who, key)][5]
        self.frame = 0.0
        self.done = False

    def update(self, dt):
        self.fade = max(0.0, self.fade - dt)
        self.frame += dt * self.fps
        n = len(self.frames)
        if self.frame >= n:
            if self.loop:
                self.frame %= n
            else:
                self.frame = n - 1
                self.done = True

    def draw(self, s, pos, alpha=255, flip=False):
        cur = self.frames[min(len(self.frames) - 1, int(self.frame))]
        if flip:
            cur = pygame.transform.flip(cur, True, False)
        if self.prev is not None and self.fade > 0:
            old = self.prev
            if flip:
                old = pygame.transform.flip(old, True, False)
            old = old.copy()
            old.set_alpha(int(255 * (self.fade / max(0.001, self.prev_t))))
            s.blit(old, old.get_rect(midbottom=pos))
        if alpha < 255:
            cur = cur.copy()
            cur.set_alpha(alpha)
        s.blit(cur, cur.get_rect(midbottom=pos))

    def duration(self):
        return len(self.frames) / self.fps


@dataclass
class Effect:
    kind: str
    x: float
    y: float
    t: float
    life: float
    color: tuple
    size: float = 1.0
    vx: float = 0.0
    vy: float = 0.0
    text: str = ""


@dataclass
class Ball:
    x: float
    y: float
    vx: float
    vy: float
    damage: float
    target: "Character"
    color: tuple
    radius: int = 7
    life: float = 4.0
    trail: float = 0.0
    necro: float = 0.03


@dataclass
class Projectile:
    x: float
    y: float
    target_x: float
    target_y: float
    damage: float
    color: tuple
    kind: str = "ds"
    speed: float = 260.0
    radius: int = 6
    life: float = 2.0
    trail: float = 0.0
    target: object = None


class Character:
    def __init__(self, cid, name, en, role, color, portrait, x, y):
        self.cid = cid
        self.name = name
        self.en = en
        self.role = role
        self.color = color
        self.portrait = portrait
        self.x, self.y = float(x), float(y)
        self.max_hp = 1000 if cid == "ds" else 1150
        self.hp = self.max_hp
        self.atk = 60 if cid == "ds" else 35
        self.defense = 35 if cid == "ds" else 55
        self.range = 430 if cid == "ds" else 470
        self.attack_interval = 1.15 if cid == "ds" else 1.45
        self.move_speed = 110 if cid == "ds" else 100
        self.attack_cd = 0.4
        self.skill_cd = 0.0
        self.ult_cd = 0.0
        self.ult_energy = 0.0
        self.ult_used = False
        self.state = "idle"
        self.anim = Anim(cid, "idle")
        self.cast = None
        self.shield = 0.0
        self.shield_t = 0.0
        self.share_t = 0.0
        self.guard_t = 0.0
        self.hurt_t = 0.0
        self.dead = False
        self.removed = False
        self.hit_flash = 0.0
        self.stats_damage = 0.0
        self.stats_heal = 0.0

        # combat movement / evasion
        self.move_cd_max = 0.7 if cid == "ds" else 0.85
        self.move_cd = 0.0
        self.burst_t = 0.0
        self.burst_dx = 0.0
        self.burst_dy = 0.0
        self.evade_cd_max = 1.4 if cid == "ds" else 1.6
        self.evade_cd = 0.0
        self.evade_t = 0.0
        self.evade_dy = 0.0
        self.dodge_rate = 0.15 if cid == "ds" else 0.12
        self.dodge_cd_max = 6.0 if cid == "ds" else 8.0
        self.dodge_cd = 0.0
        self.dodge_t = 0.0
        self.hit_tint_t = 0.0
        self.death_t = 0.0
        self.roam_i = 0
        self.roam_wait = 4.5
        self.facing_right = False

    @property
    def alive(self):
        return not self.dead

    def start_attack(self, battle):
        if self.dead or self.state not in ("idle", "move"):
            return
        target = battle.nearest_enemy(self.x, self.y)
        if target is None:
            return
        self.state = "attack"
        self.anim.play("attack")
        self.cast = {"kind": "attack", "t": 0.0, "impact": self.anim.duration() * 0.42,
                     "fired": False, "target": target}
        self.attack_cd = self.attack_interval

    def start_skill(self, battle, target=None):
        if self.dead or self.skill_cd > 0 or self.state in ("skill", "ult"):
            battle.error("技能冷却中" if self.skill_cd > 0 else "当前无法释放")
            return False
        if self.state == "attack":
            self.cast = None
        self.burst_t = 0.0
        self.evade_t = 0.0
        self.state = "skill"
        self.anim.play("skill")
        self.skill_cd = 8.0 if self.cid == "ds" else 9.0
        self.cast = {"kind": "skill", "t": 0.0, "impact": self.anim.duration() * 0.48,
                     "fired": False, "target": target}
        battle.on_cast(self, "skill")
        return True

    def start_ult(self, battle):
        if self.dead or self.ult_used or self.ult_energy < 100 or self.state in ("skill", "ult"):
            if self.ult_used:
                battle.error("本场大招已使用")
            elif self.ult_energy < 100:
                battle.error(f"大招能量 {int(self.ult_energy)}/100")
            else:
                battle.error("当前无法释放")
            return False
        if self.state == "attack":
            self.cast = None
        self.ult_used = True
        self.ult_energy = 0.0
        self.burst_t = 0.0
        self.evade_t = 0.0
        self.state = "ult"
        self.anim.play("ult")
        self.ult_cd = 0.0
        self.cast = {"kind": "ult", "t": 0.0, "impact": self.anim.duration() * 0.43, "fired": False}
        battle.on_cast(self, "ult")
        battle.begin_cutin(self)
        return True

    def gain_ult(self, amount):
        if self.ult_used or self.dead:
            return
        self.ult_energy = min(100.0, self.ult_energy + amount)

    def die(self, battle):
        if self.dead:
            return
        self.hp = 0
        self.dead = True
        self.state = "death"
        self.cast = None
        self.evade_t = 0
        self.burst_t = 0
        self.anim.play("death", fade=0.06)
        battle.on_death(self)

    def take_damage(self, amount, battle):
        if self.dead or self.removed:
            return
        # ultimate animation grants invincibility frames
        if self.state == "ult":
            return
        # chance dodge happens before shields and shared damage
        if self.dodge_cd <= 0 and random.random() < self.dodge_rate:
            self.dodge_cd = self.dodge_cd_max
            self.dodge_t = 0.38
            battle.dodge_text(self)
            return
        amount = max(1.0, amount)
        if self.guard_t > 0:
            amount *= 0.7
        absorbed = min(self.shield, amount)
        self.shield -= absorbed
        amount -= absorbed
        if self.share_t > 0:
            other = battle.other(self)
            if other and other.alive:
                half = amount * 0.5
                self.hp -= half
                other.hp -= half
                battle.damage_number(other.x, other.y - 70, half, RED)
                battle.spawn_particles(other.x, other.y - 65, GREEN, 5)
                if other.hp <= 0:
                    other.die(battle)
            else:
                self.hp -= amount
        else:
            self.hp -= amount
        self.hit_tint_t = 0.26
        battle.damage_number(self.x, self.y - 70, amount, RED)
        battle.spawn_particles(self.x, self.y - 55, RED, 7)
        battle.shake(0.1, 2)
        if self.hp <= 0:
            self.die(battle)

    def incoming_threat(self, battle):
        for b in battle.balls:
            if b.target is self and math.hypot(b.x - self.x, b.y - (self.y - 35)) < 230:
                return True
        return False

    def start_evade(self, battle):
        self.cast = None
        self.state = "move"
        self.evade_t = 0.28
        # mostly vertical sidestep away from the incoming projectile
        if self.y >= 380:
            self.evade_dy = -1
        else:
            self.evade_dy = 1
        if self.y < 310:
            self.evade_dy = 1
        if self.y > 455:
            self.evade_dy = -1
        self.evade_cd = self.evade_cd_max
        self.anim.play("move", fade=0.04)
        battle.spawn_particles(self.x, self.y - 35, self.color, 5, 45)
        battle.audio.play("tab")

    def start_burst(self, dx, dy):
        self.state = "move"
        self.burst_t = 0.45
        self.burst_dx = dx
        self.burst_dy = dy
        if self.cid == "ds" and abs(dx) > 0.01:
            self.facing_right = dx > 0
        self.move_cd = self.move_cd_max
        self.anim.play("move", fade=0.05)

    def update(self, dt, battle):
        if self.dead:
            self.anim.update(dt)
            if self.anim.done:
                self.death_t += dt
                if self.death_t > 0.22:
                    self.removed = True
            return
        self.attack_cd = max(0.0, self.attack_cd - dt)
        self.skill_cd = max(0.0, self.skill_cd - dt)
        self.ult_cd = max(0.0, self.ult_cd - dt)
        self.move_cd = max(0.0, self.move_cd - dt)
        self.evade_cd = max(0.0, self.evade_cd - dt)
        self.dodge_cd = max(0.0, self.dodge_cd - dt)
        self.dodge_t = max(0.0, self.dodge_t - dt)
        self.hit_tint_t = max(0.0, self.hit_tint_t - dt)
        self.shield_t = max(0.0, self.shield_t - dt)
        if self.cid == "ds":
            # patrol timing continues even during attack/skill animations
            self.roam_wait -= dt
            if self.roam_wait <= 0:
                self.roam_i = (self.roam_i + 1) % len(DS_PATROL)
                self.roam_wait = 4.5
        if self.shield_t <= 0:
            self.shield = 0.0
        self.share_t = max(0.0, self.share_t - dt)
        self.guard_t = max(0.0, self.guard_t - dt)
        self.anim.update(dt)

        # skills/ults own the body until the clip ends
        if self.cast and self.state in ("skill", "ult"):
            self.cast["t"] += dt
            if not self.cast["fired"] and self.cast["t"] >= self.cast["impact"]:
                self.cast["fired"] = True
                battle.resolve_cast(self, self.cast["kind"])
            if self.anim.done:
                self.cast = None
                self.state = "idle"
                self.anim.play("idle")
            return

        # a telegraph or a nearby ball can interrupt a normal attack
        if self.state != "dead" and self.incoming_threat(battle) and self.evade_cd <= 0:
            self.start_evade(battle)
            return

        if self.evade_t > 0:
            self.evade_t -= dt
            self.state = "move"
            self.anim.play("move")
            self.y += self.evade_dy * 220 * dt
            self.y = max(300, min(455, self.y))
            if self.evade_t <= 0:
                self.evade_t = 0
                self.state = "idle"
                self.anim.play("idle")
            return

        if self.cast:  # attack wind-up / projectile
            self.cast["t"] += dt
            if not self.cast["fired"] and self.cast["t"] >= self.cast["impact"]:
                self.cast["fired"] = True
                battle.resolve_cast(self, "attack")
            if self.anim.done:
                self.cast = None
                self.state = "idle"
                self.anim.play("idle")
            return

        if self.state == "attack":
            if self.anim.done:
                self.state = "idle"
                self.anim.play("idle")
            return

        # movement burst: move for a short window, then stand and attack
        if self.burst_t > 0:
            self.burst_t = max(0.0, self.burst_t - dt)
            self.state = "move"
            self.anim.play("move")
            self.x += self.burst_dx * self.move_speed * dt
            self.y += self.burst_dy * self.move_speed * dt
            self.x = max(80, min(735, self.x))
            self.y = max(300, min(455, self.y))
            if self.burst_t <= 0:
                self.state = "idle"
                self.anim.play("idle")
            return

        # patrol: DS cycles between four tactical anchors; Claude trails behind
        if self.cid == "ds":
            tx, ty = DS_PATROL[self.roam_i]
            dx, dy = tx - self.x, ty - self.y
            d = math.hypot(dx, dy)
            if d <= 8:
                pass
            elif self.move_cd <= 0:
                self.start_burst(dx / d, dy / d)
                return
        else:
            tx, ty = battle.ds.x - 60, battle.ds.y + 30
            dx, dy = tx - self.x, ty - self.y
            d = math.hypot(dx, dy)
            if d > 18 and self.move_cd <= 0:
                self.start_burst(dx / d, dy / d)
                return

        self.state = "idle"
        self.anim.play("idle")
        target = battle.nearest_enemy(self.x, self.y)
        if target is not None:
            bd = math.hypot(target.x - self.x, target.y - self.y)
            if self.attack_cd <= 0 and bd <= self.range:
                self.start_attack(battle)

    def draw(self, s):
        if self.removed:
            return
        pos = (self.x, self.y + 10)
        flip = self.cid == "ds" and self.facing_right
        alpha = 255
        if self.dodge_t > 0:
            k = 1.0 - max(0.0, min(1.0, self.dodge_t / 0.38))
            alpha = int(255 * (1.0 - 0.62 * math.sin(k * math.pi)))
        self.anim.draw(s, pos, alpha, flip)
        if self.hit_tint_t > 0:
            frame = self.anim.frames[min(len(self.anim.frames) - 1, int(self.anim.frame))].copy()
            if flip:
                frame = pygame.transform.flip(frame, True, False)
            frame.fill((255, 70, 70, 255), special_flags=pygame.BLEND_RGBA_MULT)
            frame.set_alpha(int(190 * min(1.0, self.hit_tint_t / 0.26)))
            s.blit(frame, frame.get_rect(midbottom=pos))


class Boss:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.r = 62
        self.fire_cd = 2.0
        self.spin = 0.0
        self.hit_flash = 0.0
        self.total_damage = 0.0
        self.pulse = 0.0
        self.telegraph = None
        try:
            self.f10 = pygame.font.Font(r"C:\Windows\Fonts\consola.ttf", 10)
            self.f12 = pygame.font.Font(r"C:\Windows\Fonts\consola.ttf", 12)
        except Exception:
            self.f10 = pygame.font.Font(None, 10)
            self.f12 = pygame.font.Font(None, 12)

    def fire_at(self, target, battle, tx=None, ty=None):
        if tx is None:
            tx, ty = target.x, target.y - 35
        dx, dy = tx - self.x, ty - self.y
        l = math.hypot(dx, dy) or 1
        speed = 165
        battle.balls.append(Ball(
            self.x + dx / l * 42, self.y + dy / l * 42,
            dx / l * speed, dy / l * speed,
            62, target, (255, 92, 120), 8, 5.0,
        ))
        battle.audio.play("drop")

    def update(self, dt, battle):
        self.spin += dt * 0.55
        self.pulse += dt
        self.hit_flash = max(0.0, self.hit_flash - dt)
        if battle.state != "fight":
            return
        if self.telegraph:
            self.telegraph["t"] -= dt
            if self.telegraph["t"] <= 0:
                target = self.telegraph.get("target")
                if target and target.alive:
                    self.fire_at(target, battle, self.telegraph.get("x", target.x),
                                 self.telegraph.get("y", target.y - 35))
                self.telegraph = None
                self.fire_cd = 1.55
            return
        self.fire_cd -= dt
        if self.fire_cd <= 0:
            alive = [c for c in battle.chars if c.alive and not c.removed]
            if alive:
                target = random.choice(alive)
                self.telegraph = {"target": target, "t": 0.32, "x": target.x, "y": target.y - 35}
            self.fire_cd = 1.55

    def hit(self, amount, battle, color=CYAN):
        self.hit_flash = 0.14
        self.total_damage += amount
        battle.damage_number(self.x, self.y - 82, amount, color)

    def draw(self, s, t):
        x, y, r = int(self.x), int(self.y), self.r
        # outer hazard ring
        pygame.draw.circle(s, (34, 13, 22), (x, y), r + 17)
        pygame.draw.circle(s, (94, 30, 42), (x, y), r + 14, 2)
        pygame.draw.circle(s, (23, 12, 22), (x, y), r + 5)
        # segmented ring
        for i in range(12):
            a = self.spin + i * math.tau / 12
            ex = x + math.cos(a) * (r + 9)
            ey = y + math.sin(a) * (r + 9)
            pygame.draw.rect(s, (255, 120, 130) if i % 3 == 0 else (150, 55, 75), (ex - 2, ey - 2, 4, 4))
        # core
        body = (110, 26, 48) if self.hit_flash <= 0 else (255, 220, 220)
        pygame.draw.circle(s, body, (x, y), r)
        pygame.draw.circle(s, (45, 10, 25), (x, y), r, 3)
        pygame.draw.circle(s, (20, 8, 17), (x, y), r - 15)
        # eye
        pulse = int(5 + 3 * (0.5 + 0.5 * math.sin(self.pulse * 4)))
        pygame.draw.circle(s, (255, 80, 112), (x, y), r - 25)
        pygame.draw.circle(s, (255, 220, 230), (x, y), max(3, r - 36))
        pygame.draw.circle(s, (20, 4, 12), (x, y), max(2, r - 43))
        # orbit dots
        for i in range(3):
            a = -self.spin * 1.5 + i * math.tau / 3
            ex = x + math.cos(a) * (r - 5)
            ey = y + math.sin(a) * (r - 5)
            pygame.draw.circle(s, (255, 190, 100), (int(ex), int(ey)), 3)
        # hp bar
        br = pygame.Rect(x - 92, y - r - 44, 184, 10)
        pygame.draw.rect(s, (25, 14, 22), br)
        pygame.draw.rect(s, (255, 90, 118), br, 1)
        pygame.draw.rect(s, (150, 45, 66), (br.x + 2, br.y + 2, br.w - 4, br.h - 4))
        s.blit(self.f12.render("∞", False, (255, 210, 220)), (x - 5, y - r - 45))
        s.blit(self.f10.render("AUDITOR", False, (255, 210, 220)), (x - 32, y - r - 31))

    def draw_telegraph(self, s):
        if not self.telegraph:
            return
        t = self.telegraph.get("target")
        if not t or not t.alive:
            return
        px, py = int(self.telegraph.get("x", t.x)), int(self.telegraph.get("y", t.y - 35))
        k = 1.0 - max(0.0, min(1.0, self.telegraph["t"] / 0.32))
        rad = int(24 + 14 * k)
        pygame.draw.circle(s, (255, 80, 105), (px, py), rad, 2)
        pygame.draw.line(s, (255, 130, 145), (px - rad - 5, py), (px - rad + 4, py), 1)
        pygame.draw.line(s, (255, 130, 145), (px + rad - 4, py), (px + rad + 5, py), 1)
        pygame.draw.line(s, (255, 130, 145), (px, py - rad - 5), (px, py - rad + 4), 1)
        pygame.draw.line(s, (255, 130, 145), (px, py + rad - 4), (px, py + rad + 5), 1)

    @staticmethod
    def _font(text, size):
        f = pygame.font.Font(r"C:\Windows\Fonts\consola.ttf", size)
        return f.render(text, False, (255, 210, 220))


CARD_INFO = {
    "CUT": {"cn": "断链剪", "en": "CUT", "color": (80, 214, 255), "desc": "剪 1 条引用"},
    "CLIP": {"cn": "尽剪", "en": "CLIP", "color": (90, 220, 245), "desc": "清空首个命中敌人"},
    "SWEEP": {"cn": "扫链", "en": "SWEEP", "color": (90, 230, 210), "desc": "全体各剪 1 层"},
    "WEAK": {"cn": "窥弱印", "en": "WEAK", "color": (185, 140, 255), "desc": "受伤 +35% / 6s"},
    "WEAKEN": {"cn": "降级刻", "en": "WEAKEN", "color": (160, 150, 255), "desc": "剪 1 层并弱化"},
    "LINK": {"cn": "锚链", "en": "LINK", "color": (100, 170, 255), "desc": "锁住敌人 4s"},
    "VOID": {"cn": "空型抹除", "en": "VOID", "color": (230, 235, 245), "desc": "眩晕 2s / 破析构"},
    "TRUNC": {"cn": "截断", "en": "TRUNC", "color": (255, 200, 87), "desc": "80 伤害 + 眩晕"},
    "DELAY": {"cn": "延时断点", "en": "DELAY", "color": (100, 220, 255), "desc": "3s 后剪 1 层"},
    "REFLECT": {"cn": "折返断链", "en": "REFLECT", "color": (255, 200, 230), "desc": "6s 攻击反伤"},
    "ALIAS": {"cn": "别名绑定", "en": "ALIAS", "color": (200, 150, 255), "desc": "6s 伤害扩散"},
    "STEAL": {"cn": "引用窃取", "en": "STEAL", "color": (100, 240, 200), "desc": "剪 1 层 + 保真度"},
    "COMPRESS": {"cn": "压缩", "en": "COMPRESS", "color": (255, 180, 100), "desc": "伤害 +30% / 8s"},
    "ECC": {"cn": "纠错补块", "en": "ECC", "color": (114, 230, 160), "desc": "修复 30 保真度"},
    "LOSSY": {"cn": "有损爆发", "en": "LOSSY", "color": (255, 160, 80), "desc": "全体70 / 保真-10"},
    "DOWN": {"cn": "降采样", "en": "DOWN", "color": (114, 230, 160), "desc": "减速 5s"},
    "PATCH": {"cn": "热补丁", "en": "PATCH", "color": (120, 245, 170), "desc": "回复 18% 生命"},
    "STITCH": {"cn": "缝合", "en": "STITCH", "color": (140, 240, 190), "desc": "回复 12% + 减伤"},
    "EDGE": {"cn": "锐化", "en": "EDGE", "color": (80, 214, 255), "desc": "滑剪判定 +8", "passive": True},
    "RECLAIM": {"cn": "回收协议", "en": "RECLAIM", "color": (114, 230, 160), "desc": "GC 回复 6 保真", "passive": True},
    "OVERCLOCK": {"cn": "超频", "en": "OVERCLOCK", "color": (255, 200, 87), "desc": "我方伤害 +12%", "passive": True},
}
CARD_POOL = list(CARD_INFO.keys())
SLASH_CARDS = {"CUT", "CLIP", "SWEEP", "WEAK", "TRUNC", "DOWN"}

MEMORY_CD = {
    "CUT": 5.0, "CLIP": 12.0, "SWEEP": 14.0, "WEAK": 9.0,
    "WEAKEN": 10.0, "LINK": 10.0, "VOID": 12.0, "TRUNC": 9.0,
    "DELAY": 10.0, "REFLECT": 12.0, "ALIAS": 12.0, "STEAL": 10.0,
    "COMPRESS": 14.0, "ECC": 12.0, "LOSSY": 12.0, "DOWN": 8.0,
    "PATCH": 9.0, "STITCH": 11.0,
}

# 8x8 内存版，8 张已装载技能，存在 2 处重叠。
MEMORY_LAYOUT = [
    ("CUT", (0, 0), [(0, 0), (1, 0), (1, 1)]),
    ("CLIP", (3, 0), [(0, 0), (1, 0), (2, 0)]),
    ("SWEEP", (0, 2), [(0, 0), (1, 0), (0, 1), (1, 1)]),
    ("WEAK", (1, 2), [(0, 0), (1, 0), (0, 1)]),
    ("TRUNC", (3, 2), [(0, 0), (1, 0), (2, 0), (2, 1)]),
    ("DOWN", (6, 2), [(0, 0), (0, 1), (1, 1)]),
    ("ECC", (5, 5), [(0, 0), (1, 0), (0, 1)]),
    ("LOSSY", (6, 5), [(0, 0), (1, 0), (0, 1), (1, 1)]),
]


class MemoryCard:
    def __init__(self, key, origin=(0, 0), shape=None, cells=None, uid=None, damaged=False,
                 kind="active", plus=0):
        self.key = key
        self.info = CARD_INFO[key]
        self.kind = kind
        self.plus = plus
        if cells is not None:
            self.cells = {(int(r), int(c)) for r, c in cells}
        else:
            self.cells = {(origin[0] + dx, origin[1] + dy) for dx, dy in (shape or ())}
        xs = [c[0] for c in self.cells]
        ys = [c[1] for c in self.cells]
        self.rect = pygame.Rect(min(xs), min(ys), max(xs) - min(xs) + 1, max(ys) - min(ys) + 1)
        self.cdmax = MEMORY_CD.get(key, 6.0)
        self.cd = 0.0
        self.damaged = damaged
        self.break_t = 0.0
        self.uid = uid


ENEMY_DEFS = {    "MINION": {"cn": "游标", "hp": 150, "dmg": 36, "period": 2.2, "speed": 82, "keep": 150,
               "r": 18, "color": (230, 120, 90)},
    "SENTINEL": {"cn": "哨兵", "hp": 320, "dmg": 46, "period": 2.6, "speed": 0, "keep": 0,
                 "r": 24, "color": (255, 190, 90)},
    "WARD": {"cn": "护盾守卫", "hp": 260, "dmg": 0, "period": 4.0, "speed": 0, "keep": 0,
             "r": 20, "color": (110, 190, 255)},
    "BOMB": {"cn": "析构炸弹", "hp": 110, "dmg": 0, "period": 99.0, "speed": 58, "keep": 90,
             "r": 19, "color": (245, 90, 100)},
    "CYCLER": {"cn": "循环体", "hp": 250, "dmg": 44, "period": 2.8, "speed": 42, "keep": 245,
               "r": 21, "color": (185, 140, 255)},
    "QUANTIZER": {"cn": "量化者", "hp": 520, "dmg": 34, "period": 3.0, "speed": 0, "keep": 0,
                  "r": 26, "color": (114, 230, 160)},
    "ALLOCATOR": {"cn": "分配器", "hp": 300, "dmg": 32, "period": 3.4, "speed": 0, "keep": 0,
                  "r": 22, "color": (80, 220, 210)},
    "PYLON": {"cn": "塔架", "hp": 220, "dmg": 38, "period": 3.2, "speed": 0, "keep": 0,
              "r": 20, "color": (235, 100, 220)},
    "GC_CORE": {"cn": "回收核心", "hp": 1800, "dmg": 0, "period": 99.0, "speed": 0, "keep": 0,
                "r": 48, "color": (255, 90, 210)},
    "AUDITOR": {"cn": "审计官", "hp": 2600, "dmg": 52, "period": 2.0, "speed": 0, "keep": 0,
                "r": 40, "color": (255, 170, 80)},
}


ENEMY_VALUE = {
    "MINION": 2, "SENTINEL": 4, "WARD": 4, "BOMB": 3,
    "CYCLER": 5, "QUANTIZER": 7, "ALLOCATOR": 5,
    "PYLON": 4, "GC_CORE": 30, "AUDITOR": 25,
}


class RefLink:
    COLORS = {
        "strong": (80, 214, 255),
        "cycle": (190, 140, 255),
        "support": (255, 205, 100),
    }

    def __init__(self, source, target, kind="strong"):
        self.source = source
        self.target = target
        self.kind = kind
        self.alive = True

    @property
    def color(self):
        return self.COLORS.get(self.kind, (150, 180, 200))


class Enemy:
    def __init__(self, kind, x, y, summoned=False):
        self.kind = kind
        self.d = ENEMY_DEFS[kind]
        self.summoned = summoned
        self.name = self.d["cn"]
        self.x, self.y = float(x), float(y)
        self.max_hp = float(self.d["hp"])
        self.hp = self.max_hp
        self.r = self.d["r"]
        self.color = self.d["color"]
        self.dead = False
        self.refs = []
        self.attack_cd = random.uniform(0.8, 2.0)
        self.special_cd = 1.0
        self.quant_tick = random.uniform(1.4, 2.2)
        self.shield = 0.0
        self.shield_t = 0.0
        self.weak_t = 0.0
        self.slow_t = 0.0
        self.stun_t = 0.0
        self.held_t = 0.0
        self.alias_t = 0.0
        self.reflect_t = 0.0
        self.no_destructor = False
        self.hit_flash = 0.0
        self.pair = None
        self.cycle_t = 1.6
        self.spawn_t = 0.0
        self.pulse = random.random() * 6

    @property
    def alive(self):
        return not self.dead

    @property
    def refcount(self):
        return sum(1 for l in self.refs if l.alive and l.kind in ("strong", "cycle"))

    def nearest_char(self, battle):
        alive = [c for c in battle.chars if c.alive and not c.removed]
        if not alive:
            return None
        return min(alive, key=lambda c: math.hypot(c.x - self.x, c.y - self.y))

    def shoot(self, battle):
        c = self.nearest_char(battle)
        if not c:
            return
        dx, dy = c.x - self.x, (c.y - 35) - self.y
        l = math.hypot(dx, dy) or 1
        dmg = self.d["dmg"]
        if self.weak_t > 0:
            dmg *= 0.65
        battle.balls.append(Ball(self.x, self.y, dx / l * 160, dy / l * 160,
                                 dmg, c, self.color, 7, 5.0, 0.0, 0.03))
        if self.reflect_t > 0:
            self.take_damage(16, battle, (255, 190, 220))
        battle.audio.play("drop")

    def take_damage(self, amount, battle, color=None):
        if self.dead:
            return
        if self.kind == "GC_CORE":
            shields = [l for l in battle.links
                       if l.alive and l.target is self and l.kind == "support"
                       and isinstance(l.source, Enemy) and l.source.kind == "PYLON"]
            if shields:
                battle.numbers.append({"x": self.x, "y": self.y - self.r - 20,
                                       "text": "IMMUNE", "color": (255, 220, 120),
                                       "t": 0.0, "life": 0.6, "vy": -18})
                return
        if self.weak_t > 0:
            amount *= 1.35
        if battle.compress_t > 0:
            amount *= 1.3
        absorbed = min(self.shield, amount)
        self.shield -= absorbed
        amount -= absorbed
        self.hp -= amount
        self.hit_flash = 0.12
        battle.damage_number(self.x, self.y - self.r - 18, amount, color or WHITE)
        battle.spawn_particles(self.x, self.y, color or self.color, 6)
        if self.alias_t > 0 and not battle.alias_splash:
            other = next((e for e in battle.enemies if e.alive and e is not self), None)
            if other:
                battle.alias_splash = True
                other.take_damage(amount * 0.35, battle, (200, 150, 255))
                battle.alias_splash = False
        if self.hp <= 0:
            self.die(battle, "hp")

    def cut_ref(self, battle, count=1):
        if self.dead:
            return
        if self.kind == "GC_CORE":
            battle.numbers.append({"x": self.x, "y": self.y - self.r - 30, "text": "NO REF / IMMUNE",
                                   "color": (255, 220, 120), "t": 0.0, "life": 0.7, "vy": -20})
            return
        links = [l for l in self.refs if l.alive and l.kind in ("strong", "cycle")]
        for link in links[:count]:
            battle.cut_link(link)

    def die(self, battle, cause="hp"):
        if self.dead:
            return
        self.dead = True
        self.hp = 0
        if not self.summoned:
            battle.kills_value += ENEMY_VALUE.get(self.kind, 0)
        battle.spawn_particles(self.x, self.y, self.color, 22 if cause == "gc" else 14, 140)
        battle.rings.append({"x": self.x, "y": self.y, "r": 8, "max": 70,
                             "t": 0.0, "life": 0.45, "color": self.color})
        battle.numbers.append({"x": self.x, "y": self.y - self.r - 10,
                               "text": "GC" if cause == "gc" else self.name,
                               "color": CYAN if cause == "gc" else RED,
                               "t": 0.0, "life": 0.8, "vy": -26})
        if self.kind == "BOMB":
            battle.flash(0.14, (255, 90, 70), 0.4)
            battle.shake(0.35, 9)
            if not self.no_destructor:
                for c in battle.chars:
                    if c.alive and math.hypot(c.x - self.x, c.y - self.y) < 150:
                        c.take_damage(48, battle)
                if random.random() < 0.55:
                    battle.necro_cell("bomb")
                battle.spawn_particles(self.x, self.y, (255, 90, 70), 28, 180)
                battle.rings.append({"x": self.x, "y": self.y, "r": 10, "max": 150,
                                     "t": 0.0, "life": 0.5, "color": (255, 110, 80)})
        for link in battle.links:
            if link.alive and (link.source is self or link.target is self):
                link.alive = False
        battle.on_enemy_death()

    def update(self, dt, battle):
        if self.dead:
            return
        self.spawn_t += dt
        self.hit_flash = max(0.0, self.hit_flash - dt)
        self.weak_t = max(0.0, self.weak_t - dt)
        self.slow_t = max(0.0, self.slow_t - dt)
        self.stun_t = max(0.0, self.stun_t - dt)
        self.held_t = max(0.0, self.held_t - dt)
        self.alias_t = max(0.0, self.alias_t - dt)
        self.reflect_t = max(0.0, self.reflect_t - dt)
        self.shield_t = max(0.0, self.shield_t - dt)
        if self.shield_t <= 0:
            self.shield = 0.0
        if self.stun_t > 0 or self.held_t > 0:
            return
        slow = 0.55 if self.slow_t > 0 else 1.0

        if self.kind == "GC_CORE":
            shields = [l for l in battle.links
                       if l.alive and l.target is self and l.kind == "support"
                       and isinstance(l.source, Enemy) and l.source.kind == "PYLON"]
            if shields:
                return
            self.special_cd -= dt
            if self.special_cd <= 0:
                self.special_cd = 4.0
                for i in range(10):
                    a = i * math.tau / 10 + battle.time * 0.2
                    battle.balls.append(Ball(self.x, self.y, math.cos(a) * 135, math.sin(a) * 135,
                                             40, None, (255, 90, 210), 7, 5.0, 0.0, 0.30))
                battle.spawn_particles(self.x, self.y, (255, 90, 210), 20, 150)
                battle.flash(0.12, (255, 80, 200), 0.25)
                if random.random() < 0.5:
                    battle.spawn_enemy("MINION", self.x - 80, self.y + 65, summoned=True)
            return

        if self.kind in ("MINION", "BOMB", "CYCLER"):
            c = self.nearest_char(battle)
            if c:
                dx, dy = c.x - self.x, (c.y - 35) - self.y
                dist = math.hypot(dx, dy) or 1
                if dist > self.d["keep"]:
                    self.x += dx / dist * self.d["speed"] * slow * dt
                    self.y += dy / dist * self.d["speed"] * slow * dt
                self.x = max(80, min(760, self.x))
                self.y = max(120, min(450, self.y))

        if self.kind == "ALLOCATOR":
            self.special_cd -= dt
            if self.special_cd <= 0:
                self.special_cd = 5.0
                battle.spawn_enemy("MINION", self.x + random.uniform(-55, 55), self.y + 70,
                                   summoned=True)
                battle.rings.append({"x": self.x, "y": self.y, "r": 8, "max": 42,
                                     "t": 0.0, "life": 0.4, "color": (80, 220, 210)})

        if self.kind == "WARD":
            self.special_cd -= dt
            if self.special_cd <= 0:
                self.special_cd = 4.0
                linked = [l.target for l in battle.links
                          if l.alive and l.source is self and l.kind == "support" and l.target.alive]
                if linked:
                    t = min(linked, key=lambda e: e.hp / e.max_hp)
                    t.shield = max(t.shield, 90)
                    t.shield_t = max(t.shield_t, 4.0)
                    battle.rings.append({"x": t.x, "y": t.y, "r": 6, "max": 32,
                                         "t": 0.0, "life": 0.4, "color": (110, 200, 255)})
            return

        if self.kind == "CYCLER":
            if self.pair and self.pair.alive:
                self.cycle_t -= dt
                if self.cycle_t <= 0:
                    self.cycle_t = 1.6
                    has_cycle = any(l.alive and l.kind == "cycle" and l.target is self
                                    for l in self.refs)
                    if not has_cycle:
                        battle.add_link(self.pair, self, "cycle")
                    has_back = any(l.alive and l.kind == "cycle" and l.target is self.pair
                                   for l in self.pair.refs)
                    if not has_back:
                        battle.add_link(self, self.pair, "cycle")
                    battle.spawn_particles((self.x + self.pair.x) / 2, (self.y + self.pair.y) / 2,
                                           PURPLE, 5)

        if self.kind == "QUANTIZER":
            self.quant_tick -= dt
            if self.quant_tick <= 0:
                self.quant_tick = 3.0
                battle.quantizer_tick(self)

        if self.d["dmg"] > 0:
            self.attack_cd -= dt
            if self.attack_cd <= 0:
                self.attack_cd = self.d["period"] * (1.55 if self.slow_t > 0 else 1.0)
                self.shoot(battle)

    def draw(self, s, t):
        if self.dead:
            return
        x, y, r = int(self.x), int(self.y), self.r
        col = (255, 240, 240) if self.hit_flash > 0 else self.color
        if self.kind == "MINION":
            pygame.draw.polygon(s, (40, 20, 20), [(x, y - r), (x + r, y), (x, y + r), (x - r, y)])
            pygame.draw.polygon(s, col, [(x, y - r), (x + r, y), (x, y + r), (x - r, y)], 2)
            pygame.draw.circle(s, col, (x, y), 4)
        elif self.kind == "SENTINEL":
            pts = [(x + math.cos(a) * r, y + math.sin(a) * r) for a in
                   [i * math.tau / 6 for i in range(6)]]
            pygame.draw.polygon(s, (35, 30, 20), pts)
            pygame.draw.polygon(s, col, pts, 2)
            pygame.draw.circle(s, col, (x, y), 7, 2)
        elif self.kind == "WARD":
            pygame.draw.rect(s, (18, 34, 48), (x - r, y - r, r * 2, r * 2))
            pygame.draw.rect(s, col, (x - r, y - r, r * 2, r * 2), 2)
            pygame.draw.line(s, col, (x - r + 5, y), (x + r - 5, y), 2)
            pygame.draw.line(s, col, (x, y - r + 5), (x, y + r - 5), 2)
        elif self.kind == "BOMB":
            pygame.draw.circle(s, (40, 18, 20), (x, y), r)
            pygame.draw.circle(s, col, (x, y), r, 2)
            pygame.draw.circle(s, (255, 210, 100), (x, y - r - 5), 4)
            pygame.draw.line(s, (255, 210, 100), (x, y - r), (x + 5, y - r - 6), 2)
        elif self.kind == "CYCLER":
            pygame.draw.circle(s, (28, 20, 40), (x, y), r)
            pygame.draw.circle(s, col, (x, y), r, 2)
            a = t * 2.0
            pygame.draw.circle(s, col, (int(x + math.cos(a) * (r - 5)),
                                        int(y + math.sin(a) * (r - 5))), 4)
        elif self.kind == "ALLOCATOR":
            pygame.draw.rect(s, (14, 35, 34), (x - r, y - r, r * 2, r * 2))
            pygame.draw.rect(s, col, (x - r, y - r, r * 2, r * 2), 2)
            for i in range(3):
                pygame.draw.circle(s, col, (x - 9 + i * 9, y), 3)
        elif self.kind == "PYLON":
            pygame.draw.polygon(s, (35, 18, 32), [(x, y - r), (x + r, y + r), (x - r, y + r)])
            pygame.draw.polygon(s, col, [(x, y - r), (x + r, y + r), (x - r, y + r)], 2)
            pygame.draw.circle(s, (255, 220, 250), (x, y), 4)
        elif self.kind == "GC_CORE":
            pygame.draw.circle(s, (45, 16, 38), (x, y), r + 8)
            pygame.draw.circle(s, col, (x, y), r + 8, 2)
            pygame.draw.circle(s, (25, 10, 24), (x, y), r - 8)
            pygame.draw.circle(s, (255, 90, 210), (x, y), r - 18, 2)
            pulse = int(6 + 3 * (0.5 + 0.5 * math.sin(t * 4)))
            pygame.draw.circle(s, (255, 230, 250), (x, y), pulse)
        elif self.kind == "AUDITOR":
            pygame.draw.circle(s, (40, 24, 18), (x, y), r)
            pygame.draw.circle(s, col, (x, y), r, 3)
            for i in range(8):
                a = i * math.tau / 8 + t * 0.5
                pygame.draw.line(s, col, (x + math.cos(a) * (r - 8), y + math.sin(a) * (r - 8)),
                                 (x + math.cos(a) * (r + 8), y + math.sin(a) * (r + 8)), 2)
            pygame.draw.circle(s, (255, 235, 175), (x, y), 6)
        else:
            pygame.draw.rect(s, (18, 34, 28), (x - r, y - r, r * 2, r * 2))
            pygame.draw.rect(s, col, (x - r, y - r, r * 2, r * 2), 2)
            for i in range(3):
                pygame.draw.line(s, col, (x - r + 5, y - 5 + i * 5), (x + r - 5, y - 5 + i * 5), 1)
        # hp/refs
        br = pygame.Rect(x - 32, y - r - 18, 64, 4)
        pygame.draw.rect(s, (28, 18, 24), br)
        pygame.draw.rect(s, self.color, (br.x, br.y, int(br.w * max(0, self.hp) / self.max_hp), br.h))
        if self.shield > 0:
            pygame.draw.circle(s, (100, 190, 255), (x, y), r + 5, 1)


def draw_root(s, root):
    x, y = root
    pygame.draw.circle(s, (15, 30, 42), (x, y), 16)
    pygame.draw.circle(s, CYAN, (x, y), 16, 2)
    pygame.draw.circle(s, (120, 230, 255), (x, y), 5)
    pygame.draw.line(s, CYAN, (x - 22, y), (x - 30, y), 1)
    pygame.draw.line(s, CYAN, (x + 22, y), (x + 30, y), 1)


class Battle:
    def __init__(self, windowed=False, shot=None, size=None, loadout=None, embedded=False,
                 party_hp=None, recruited=True, encounter=None, root_count=3):
        pygame.init()
        self.embedded = embedded
        self.loadout = loadout
        self.party_hp = party_hp or {}
        self.recruited = recruited
        self.encounter = encounter
        self.root_count = root_count
        self.result = None
        self.exit_to_assembly = False
        self.audio = UIAudio()
        self.windowed = windowed
        self.shot = shot
        self.size = size
        self.window = None
        self.view_rect = pygame.Rect(0, 0, W, H)
        self._set_window()
        load_assets()
        self.canvas = pygame.Surface((W, H)).convert()
        self.world = pygame.Surface(ARENA.size).convert()
        self.clock = pygame.time.Clock()
        self.font20 = self._font(20)
        self.font18 = self._font(18)
        self.font16 = self._font(16)
        self.font14 = self._font(14)
        self.font12 = self._font(12)
        self.font11 = self._font(11)
        self.font24 = self._font(24, True)
        self.font28 = self._font(28, True)
        self.font48 = self._font(48, True)
        self.font64 = self._font(64, True)
        self.mono12 = self._mono(12)
        self.mono10 = self._mono(10)

        self.p_ds = pygame.transform.scale(pygame.image.load(str(ASSET / "portraits/dsh.webp")).convert_alpha(), (58, 58))
        self.p_cl = pygame.transform.scale(pygame.image.load(str(ASSET / "portraits/claude.webp")).convert_alpha(), (58, 58))
        self.reset()

        self.mouse = (0, 0)
        self.paused = False
        self.speed = 1.0
        self.shake_t = 0.0
        self.shake_power = 0.0
        self.flash_t = 0.0
        self.flash_color = WHITE
        self.flash_alpha = 0.0
        self.hitstop = 0.0
        self.world_offset = (0, 0)
        self.hitstop_count = 0
        self.targeting = None
        self.mouse = (W // 2, H // 2)
        self.cutin = None

        self.skill_hits = []
        self.ult_hits = []
        self.pause_rect = pygame.Rect(W - 106, 12, 34, 22)
        self.speed_rect = pygame.Rect(W - 66, 12, 46, 22)
        self.party_hits = []
        self.char_hits = []
        self.command_hits = []
        self.hand_hits = []
        self.hover_skill = None
        self.frames = 0

    def reset(self):
        self.ds = Character("ds", "小忆", "DEEPSEEK", "伤害 · 远程", CYAN, self.p_ds, 330, 390)
        self.claude = Character("claude", "克劳", "CLAUDE", "辅助 · 治疗", AMBER, self.p_cl, 250, 420)
        self.ds.max_hp = 420.0
        self.claude.max_hp = 480.0
        self.ds.hp = min(self.ds.max_hp, float(self.party_hp.get("ds", self.ds.max_hp)))
        self.claude.hp = min(self.claude.max_hp, float(self.party_hp.get("claude", self.claude.max_hp)))
        if not self.recruited:
            self.claude.dead = True
            self.claude.removed = True
            self.claude.hp = 0
        self.chars = [self.ds, self.claude] if self.recruited else [self.ds]
        if self.root_count >= 5:
            self.roots = [(300, 28), (405, 28), (510, 28), (120, 250), (690, 250)]
        elif self.root_count >= 4:
            self.roots = [(300, 28), (405, 28), (510, 28), (405, 460)]
        else:
            self.roots = [(330, 28), (405, 28), (480, 28)]
        self.root = self.roots[0]
        self.root_cursor = 0
        self.enemies = []
        self.wave = 1
        self.wave_max = 1 if self.encounter else 3
        self.kills_value = 0
        self.wave_t = 0.0
        self.wave_banner = 0.0
        self.fidelity = 100.0
        self.fidelity_max = 100.0
        self.fidelity_cap = 100.0
        self.fidelity_flash_t = 0.0
        self.fidelity_pop_t = 0.0
        self.fidelity_pop_value = 0.0
        self.fidelity_drain_acc = 0.0
        self.fidelity_warn_t = 0.0
        self.fidelity_warn_value = 0
        self.fidelity_heal_t = 0.0
        self.fidelity_threats = []
        self.fidelity_alert_t = 0.0
        self.compress_t = 0.0
        self.alias_splash = False
        if self.loadout is not None:
            self.memory_cards = [
                MemoryCard(c.get("key"), cells=c.get("cells") or [],
                           uid=c.get("uid"), damaged=bool(c.get("damaged")),
                           kind=c.get("kind", "active"), plus=int(c.get("plus", 0)))
                for c in self.loadout.get("cards", [])
                if c.get("key") in CARD_INFO
            ]
            self.necro_cells = {(int(r), int(c)) for r, c in self.loadout.get("necro", [])}
            self.damaged_uids = {c.uid for c in self.memory_cards if c.damaged and c.uid is not None}
        else:
            self.memory_cards = [MemoryCard(*row) for row in MEMORY_LAYOUT]
            self.necro_cells = set()
            self.damaged_uids = set()
        self.fidelity_cap = 100.0
        self.recompute_fidelity_cap()
        self.fidelity = self.fidelity_cap
        self.hand = [None] * 5
        self.links = []
        self.fill_hand()
        self.list_scroll = 0.0
        self.list_scroll_max = 0.0
        self.active_scroll = 0.0
        self.passive_scroll = 0.0
        self.active_max = 0.0
        self.passive_max = 0.0
        self.list_rect = pygame.Rect(1018, 268, 244, 250)
        self.active_rect = pygame.Rect(1018, 284, 244, 138)
        self.passive_rect = pygame.Rect(1018, 440, 244, 76)
        self.card_throws = []
        self.delayed_cuts = []
        self.balls = []
        self.projectiles = []
        self.effects = []
        self.numbers = []
        self.rings = []
        self.selected = 0
        self.time = 0.0
        self.state = "fight"
        self.end_t = 0.0
        self.death_count = 0
        self.selected_key = "ds"
        self.targeting = None
        self.card_target = None
        self.slash_armed = None
        self.slash = None
        self.slash_links = []
        self.cutin = None
        self.spawn_wave(1)
        self.audio.play("open")

    def recompute_fidelity_cap(self):
        if self.loadout is None:
            self.fidelity_cap = 100.0
            return
        occupied = set()
        for card in self.memory_cards:
            occupied |= card.cells
        load = len(occupied | self.necro_cells)
        self.fidelity_cap = max(0.0, min(100.0, 100.0 - 50.0 * load / 64.0))
        self.fidelity = min(self.fidelity, self.fidelity_cap)

    def quantizer_tick(self, enemy):
        self.change_fidelity(-8.0, "quantizer")
        self.rings.append({"x": enemy.x, "y": enemy.y, "r": 10, "max": 88,
                           "t": 0.0, "life": 0.5, "color": (255, 70, 150)})
        self.spawn_particles(enemy.x, enemy.y, (255, 70, 150), 16, 120)
        self.flash(0.06, (255, 60, 140), 0.20)
        self.shake(0.12, 2)
        self.audio.play("invalid")

    def passive_active(self, key):
        return any(c.kind == "passive" and c.key == key and not c.damaged
                   for c in self.memory_cards)

    def fidelity_color(self):
        if self.fidelity >= 75:
            return (80, 230, 160)
        if self.fidelity >= 50:
            return (180, 230, 80)
        if self.fidelity >= 25:
            return (255, 210, 70)
        return (255, 70, 85)

    def fidelity_damage_mult(self):
        if self.fidelity >= 75:
            base = 1.00
        elif self.fidelity >= 50:
            base = 1.15
        elif self.fidelity >= 25:
            base = 1.30
        else:
            base = 1.50
        if self.passive_active("OVERCLOCK"):
            base *= 1.12
        return base

    def fidelity_resolution_factor(self):
        if self.fidelity >= 50:
            return 1.0
        if self.fidelity >= 25:
            return 0.66
        return 0.50

    def change_fidelity(self, delta, reason=""):
        old = self.fidelity
        self.fidelity = max(0.0, min(self.fidelity_cap, self.fidelity + delta))
        actual = self.fidelity - old
        if actual < 0:
            self.fidelity_flash_t = max(self.fidelity_flash_t, 0.2 if reason == "drain" else 0.55)
            if reason == "drain":
                self.fidelity_drain_acc += -actual
                if self.fidelity_drain_acc >= 4.0:
                    self.fidelity_pop_t = 1.0
                    self.fidelity_pop_value = -int(self.fidelity_drain_acc)
                    self.fidelity_drain_acc = 0.0
            else:
                self.fidelity_pop_t = 1.0
                self.fidelity_pop_value = -abs(actual)
                self.shake(0.12, 2)
            for th in (75, 50, 25):
                if old > th >= self.fidelity:
                    self.fidelity_warn_t = 2.2
                    self.fidelity_warn_value = th
        elif actual > 0:
            self.fidelity_heal_t = 0.55
            self.fidelity_pop_t = 1.0
            self.fidelity_pop_value = int(actual)
        if self.fidelity <= 0 and self.state == "fight":
            self.state = "defeat"
            self.end_t = 0

    def draw_card(self):
        cand = [c for c in self.memory_cards
                if c.kind == "active" and not c.damaged and c.cd <= 0 and c not in self.hand]
        return cand[0] if cand else None

    def fill_hand(self):
        for i in range(len(self.hand)):
            if self.hand[i] is None or self.hand[i].damaged:
                self.hand[i] = self.draw_card()

    def update_memory_cd(self, dt):
        changed = False
        for card in self.memory_cards:
            if card.break_t > 0:
                card.break_t = max(0.0, card.break_t - dt)
            if not card.damaged and card.cd > 0:
                card.cd = max(0.0, card.cd - dt)
                if card.cd <= 0:
                    changed = True
        if changed:
            self.fill_hand()
        for throw in list(self.card_throws):
            throw["age"] += dt
            if throw["age"] < 0:
                continue
            throw["x"] += throw["vx"] * dt
            throw["y"] += throw["vy"] * dt
            throw["vy"] += 1050.0 * dt
            throw["rot"] += throw["vr"] * dt
            if throw["age"] >= throw["life"]:
                self.card_throws.remove(throw)

    def _card_throw_pos(self, card):
        rect = self.active_rect if card.kind == "active" else self.passive_rect
        scroll = self.active_scroll if card.kind == "active" else self.passive_scroll
        cards = [c for c in self.memory_cards
                 if c.kind == card.kind and (not c.damaged or c is card)]
        cards = self._card_order(cards)
        try:
            idx = cards.index(card)
        except ValueError:
            idx = 0
        y = rect.y + idx * 23 - int(scroll)
        if y < rect.y or y > rect.bottom - 16:
            y = rect.centery
        return rect.x + 18, y

    def _spawn_card_throw(self, card):
        x, y = self._card_throw_pos(card)
        self.card_throws.append({
            "key": card.key,
            "name": card.info["cn"] + ("+" * card.plus),
            "color": (255, 82, 98),
            "x": float(x),
            "y": float(y),
            "vx": random.choice((-280.0, -220.0, 230.0, 290.0)),
            "vy": random.uniform(-330.0, -250.0),
            "rot": random.uniform(-18.0, 18.0),
            "vr": random.choice((-420.0, 420.0)),
            "age": -0.28,
            "life": 1.12,
        })

    def damage_card(self, card, battle=None):
        if card.damaged:
            return False
        card.damaged = True
        card.break_t = 1.0
        if card.uid is not None:
            self.damaged_uids.add(card.uid)
        self._spawn_card_throw(card)
        for i, hc in enumerate(self.hand):
            if hc is card:
                self.hand[i] = None
        if self.card_target is not None and self.hand[self.card_target] is None:
            self.card_target = None
        return True

    def necro_cell(self, cause="small"):
        free = [(x, y) for y in range(8) for x in range(8) if (x, y) not in self.necro_cells]
        if not free:
            return
        cell = random.choice(free)
        self.necro_cells.add(cell)
        self.recompute_fidelity_cap()
        hit_cards = [c for c in self.memory_cards if not c.damaged and cell in c.cells]
        for c in hit_cards:
            self.damage_card(c)
        if hit_cards:
            self.audio.play("necro_card")
        else:
            self.audio.play("necro_cell")
        self.numbers.append({"x": self.ds.x, "y": self.ds.y - 110,
                             "text": "SKILL NECROSIS" if hit_cards else "CELL NECROSIS",
                             "color": (255, 70, 90), "t": 0.0, "life": 1.0, "vy": -20})
        self.flash(0.08, RED, 0.2)

    def add_link(self, source, target, kind="strong"):
        link = RefLink(source, target, kind)
        target.refs.append(link)
        self.links.append(link)
        return link

    def cut_link(self, link, impact=True):
        if not link.alive:
            return
        link.alive = False
        target = link.target
        if link.kind == "support":
            target.shield = 0.0
            target.shield_t = 0.0
        if impact:
            if isinstance(link.source, tuple):
                sx, sy = link.source[0], link.source[1] + 16
            else:
                sx, sy = link.source.x, link.source.y
            mx, my = (sx + target.x) / 2, (sy + target.y) / 2
            self.spawn_particles(mx, my, link.color, 10, 100)
            self.numbers.append({"x": mx, "y": my, "text": "CUT",
                                 "color": link.color, "t": 0.0, "life": 0.65, "vy": -20})
            self.ds.gain_ult(15 if link.kind in ("strong", "cycle") else 5)
            if self.recruited:
                self.claude.gain_ult(12 if link.kind in ("strong", "cycle") else 4)
        if link.kind in ("strong", "cycle") and target.kind != "GC_CORE" and target.alive and target.refcount == 0:
            target.die(self, "gc")
            if self.passive_active("RECLAIM"):
                self.change_fidelity(6, "reclaim")
                self.numbers.append({"x": target.x, "y": target.y - target.r - 52,
                                     "text": "RECLAIM +6", "color": (114, 230, 160),
                                     "t": 0.0, "life": 0.8, "vy": -20})

    def separate_enemies(self, dt):
        movable = {"MINION", "BOMB", "CYCLER"}
        # Two small passes are enough for the 9-enemy prototype and avoid
        # the visible "one stack of cursors" that happened around the player.
        for _ in range(2):
            for i, a in enumerate(self.enemies):
                if not a.alive:
                    continue
                for b in self.enemies[i + 1:]:
                    if not b.alive:
                        continue
                    dx, dy = b.x - a.x, b.y - a.y
                    dist = math.hypot(dx, dy)
                    min_dist = a.r + b.r + 14
                    if dist >= min_dist:
                        continue
                    if dist < 0.001:
                        ang = ((id(a) * 37 + id(b) * 71) % 628) / 100.0
                        nx, ny = math.cos(ang), math.sin(ang)
                    else:
                        nx, ny = dx / dist, dy / dist
                    overlap = (min_dist - dist) * 0.6
                    am, bm = a.kind in movable, b.kind in movable
                    if not am and not bm:
                        continue
                    wa = 0.5 if am and bm else (1.0 if am else 0.0)
                    wb = 1.0 - wa
                    a.x -= nx * overlap * wa
                    a.y -= ny * overlap * wa
                    b.x += nx * overlap * wb
                    b.y += ny * overlap * wb
                    if am:
                        a.x = max(80, min(760, a.x))
                        a.y = max(120, min(450, a.y))
                    if bm:
                        b.x = max(80, min(760, b.x))
                        b.y = max(120, min(450, b.y))

    def spawn_enemy(self, kind, x, y, summoned=False):
        e = Enemy(kind, x, y, summoned=summoned)
        self.enemies.append(e)
        if kind != "GC_CORE":
            root = self.roots[self.root_cursor % len(self.roots)]
            self.root_cursor += 1
            self.add_link(root, e, "strong")
        # Avoid the first frame of a summon overlapping another enemy.
        self.separate_enemies(0.0)
        return e

    def spawn_wave(self, wave):
        self.wave = wave
        self.enemies = []
        self.links = []
        self.root_cursor = 0
        self.balls = []
        self.projectiles = []
        self.delayed_cuts = []
        self.wave_banner = 1.6
        self.fidelity_threats = []
        self.fidelity_alert_t = 0.0
        root_counts = {
            "MINION": 1, "SENTINEL": 3, "WARD": 2,
            "BOMB": 1, "CYCLER": 1, "QUANTIZER": 3,
            "ALLOCATOR": 2, "PYLON": 1, "GC_CORE": 0, "AUDITOR": 3,
        }
        if self.encounter == "boss_a":
            self.spawn_enemy("AUDITOR", 650, 190)
            self.spawn_enemy("WARD", 520, 120)
            self.spawn_enemy("WARD", 790, 120)
            boss, w1, w2 = self.enemies
            self.add_link(w1, boss, "support")
            self.add_link(w2, boss, "support")
        elif self.encounter == "boss_b":
            self.spawn_enemy("GC_CORE", 650, 205)
            self.spawn_enemy("PYLON", 520, 120)
            self.spawn_enemy("PYLON", 650, 95)
            self.spawn_enemy("PYLON", 780, 120)
            core, p1, p2, p3 = self.enemies
            for pylon in (p1, p2, p3):
                self.add_link(pylon, core, "support")
        elif wave == 1:
            self.spawn_enemy("SENTINEL", 600, 150)
            self.spawn_enemy("WARD", 690, 110)
            self.spawn_enemy("MINION", 680, 405)
            self.spawn_enemy("BOMB", 600, 400)
            sentinel, ward, _minion, bomb = self.enemies
            self.add_link(ward, sentinel, "support")
            self.add_link(ward, bomb, "support")
        elif wave == 2:
            self.spawn_enemy("CYCLER", 470, 250)
            self.spawn_enemy("CYCLER", 555, 315)
            self.enemies[0].pair = self.enemies[1]
            self.enemies[1].pair = self.enemies[0]
            self.spawn_enemy("QUANTIZER", 700, 225)
            self.spawn_enemy("ALLOCATOR", 700, 125)
            self.spawn_enemy("MINION", 650, 405)
            cyc_a, cyc_b, _quant, alloc, minion = self.enemies
            self.add_link(cyc_a, cyc_b, "cycle")
            self.add_link(cyc_b, cyc_a, "cycle")
            self.add_link(alloc, minion, "support")
        else:
            self.spawn_enemy("GC_CORE", 650, 205)
            self.spawn_enemy("PYLON", 520, 120)
            self.spawn_enemy("PYLON", 650, 95)
            self.spawn_enemy("PYLON", 780, 120)
            core, p1, p2, p3 = self.enemies
            for pylon in (p1, p2, p3):
                self.add_link(pylon, core, "support")
        for e in self.enemies:
            for _ in range(max(0, root_counts.get(e.kind, 1) - 1)):
                root = self.roots[self.root_cursor % len(self.roots)]
                self.root_cursor += 1
                self.add_link(root, e, "strong")
        self.ds.x, self.ds.y = 330, 390
        self.claude.x, self.claude.y = 250, 420
        for e in self.enemies:
            if e.kind == "QUANTIZER":
                self.fidelity_threats.append({"enemy": e, "t": 3.2})
                self.fidelity_alert_t = 3.2
                self.audio.play("invalid")

    def on_enemy_death(self):
        if any(e.alive for e in self.enemies):
            return
        self.targeting = None
        self.card_target = None
        self.cancel_slash()
        if self.wave < self.wave_max:
            self.state = "between"
            self.wave_t = 1.6
            self.wave_banner = 1.6
            self.audio.play("clear")
        else:
            self.state = "victory"
            self.end_t = 0


    def nearest_enemy(self, x, y):
        alive = [e for e in self.enemies if e.alive]
        if not alive:
            return None
        return min(alive, key=lambda e: math.hypot(e.x - x, e.y - y))

    def enemy_at(self, pos):
        wx = pos[0] - ARENA.x
        wy = pos[1] - ARENA.y
        for e in self.enemies:
            if e.alive and math.hypot(e.x - wx, e.y - wy) <= e.r + 18:
                return e
        return None

    # ------------------------------------------------------------ window
    def _set_window(self):
        if self.windowed:
            self.window = pygame.display.set_mode(self.size or (W, H))
        else:
            self.window = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        pygame.display.set_caption("内存远征 · 战斗原型")
        self._update_view()

    def _update_view(self):
        ww, wh = self.window.get_size()
        scale = min(ww / W, wh / H)
        dw, dh = int(W * scale), int(H * scale)
        self.view_rect = pygame.Rect((ww - dw) // 2, (wh - dh) // 2, dw, dh)

    def to_logical(self, pos):
        return (int((pos[0] - self.view_rect.x) / max(0.001, self.view_rect.w / W)),
                int((pos[1] - self.view_rect.y) / max(0.001, self.view_rect.h / H)))

    def present(self):
        self.canvas.fill(INK)
        self.draw()
        frame = pygame.transform.scale(self.canvas, self.view_rect.size) if self.view_rect.size != (W, H) else self.canvas
        self.window.fill((0, 0, 0))
        self.window.blit(frame, self.view_rect.topleft)
        pygame.display.flip()

    # ------------------------------------------------------------ font/helper
    def _font(self, size, bold=False):
        try:
            p = r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc"
            return pygame.font.Font(p, size)
        except Exception:
            return pygame.font.Font(None, size)

    def _mono(self, size):
        try:
            return pygame.font.Font(r"C:\Windows\Fonts\consola.ttf", size)
        except Exception:
            return pygame.font.Font(None, size)

    def text(self, s, text, pos, col=TEXT, font=None, center=False):
        f = font or self.font14
        img = f.render(str(text), False, col)
        r = img.get_rect()
        if center:
            r.center = pos
        else:
            r.topleft = pos
        s.blit(img, r)
        return r

    def px(self, s, rect, fill=None, border=None, width=1):
        if fill:
            pygame.draw.rect(s, fill, rect)
        if border:
            pygame.draw.rect(s, border, rect, width)

    def other(self, char):
        return self.claude if char is self.ds else self.ds

    def error(self, msg):
        self.numbers.append({"x": self.selected_char().x, "y": self.selected_char().y - 80,
                             "text": msg, "color": RED, "t": 0.0, "life": 0.7, "vy": -24})

    # ------------------------------------------------------------ effects
    def shake(self, t, power):
        self.shake_t = max(self.shake_t, t)
        self.shake_power = max(self.shake_power, power)

    def flash(self, t, color=WHITE, alpha=0.65):
        self.flash_t = max(self.flash_t, t)
        self.flash_color = color
        self.flash_alpha = max(self.flash_alpha, alpha)

    def hit_stop(self, t):
        self.hitstop = max(self.hitstop, t)
        self.hitstop_count += 1

    def damage_number(self, x, y, amount, color):
        self.numbers.append({"x": x + random.randint(-8, 8), "y": y, "text": f"-{int(amount)}",
                             "color": color, "t": 0.0, "life": 0.8, "vy": -34})

    def heal_number(self, x, y, amount):
        self.numbers.append({"x": x, "y": y, "text": f"+{int(amount)}", "color": GREEN,
                             "t": 0.0, "life": 0.9, "vy": -26})

    def spawn_particles(self, x, y, color, n=8, speed=90):
        for _ in range(n):
            a = random.random() * math.tau
            sp = random.uniform(30, speed)
            self.effects.append(Effect("p", x, y, 0, random.uniform(0.25, 0.6), color,
                                       random.uniform(1, 3), math.cos(a) * sp, math.sin(a) * sp))
        self.rings.append({"x": x, "y": y, "r": 4, "max": random.uniform(22, 50),
                           "t": 0.0, "life": 0.35, "color": color})

    def on_cast(self, char, kind):
        self.audio.play("repair" if char.cid == "claude" else "place")
        self.spawn_particles(char.x, char.y - 50, char.color, 10)
        self.rings.append({"x": char.x, "y": char.y - 40, "r": 8, "max": 70, "t": 0.0,
                           "life": 0.35, "color": char.color})
        if kind == "ult":
            self.flash(0.14, char.color, 0.18)
            self.shake(0.25, 5)
            self.hit_stop(0.04)

    def on_death(self, char):
        self.death_count += 1
        self.flash(0.18, RED, 0.35)
        self.shake(0.3, 8)
        self.hit_stop(0.08)
        self.effects.append(Effect("p", char.x, char.y - 35, 0, 0.8, char.color,
                                   4, 0, -80))

    def dodge_text(self, char):
        self.numbers.append({
            "x": char.x + 20, "y": char.y - 108, "text": "闪避",
            "color": (225, 252, 255), "t": 0.0, "life": 0.62, "vy": -26,
        })
        self.spawn_particles(char.x, char.y - 35, (210, 245, 255), 8, 55)
        self.audio.play("repair")

    # ------------------------------------------------------------ cast resolution
    def resolve_cast(self, char, kind):
        if kind == "attack":
            target = char.cast.get("target") if char.cast else None
            if target is None or not target.alive:
                target = self.nearest_enemy(char.x, char.y)
            if target is None:
                return
            if char.cid == "ds":
                self.projectiles.append(Projectile(char.x + 30, char.y - 48, target.x, target.y,
                                                   char.atk * self.fidelity_damage_mult(), CYAN, "ds", 300, 7, 2.0, target=target))
            else:
                self.projectiles.append(Projectile(char.x + 25, char.y - 52, target.x, target.y,
                                                   char.atk * 0.65 * self.fidelity_damage_mult(), AMBER, "claude", 280, 6, 2.0, target=target))
            self.audio.play("pick" if char.cid == "ds" else "tab")
            return
        if char.cid == "ds":
            target = char.cast.get("target") if char.cast else None
            if kind == "skill":
                targets = [target] if target and target.alive else [self.nearest_enemy(char.x, char.y)]
            else:
                targets = [e for e in self.enemies if e.alive]
            targets = [e for e in targets if e is not None]
            if not targets:
                return
            amount = char.atk * (1.8 if kind == "skill" else 2.2) * self.fidelity_damage_mult()
            for e in targets:
                e.take_damage(amount, self, CYAN if kind == "skill" else (180, 240, 255))
                e.cut_ref(self, 1)
                self.spawn_particles(e.x, e.y, CYAN if kind == "skill" else WHITE,
                                     14 if kind == "ult" else 10, 130)
            self.flash(0.08 if kind == "skill" else 0.2, CYAN, 0.25 if kind == "skill" else 0.5)
            self.shake(0.25 if kind == "skill" else 0.55, 7 if kind == "skill" else 12)
            self.hit_stop(0.055 if kind == "skill" else 0.13)
            self.numbers.append({"x": char.x, "y": char.y - 100, "text": "裂空跃击" if kind == "skill" else "蓝鲸现世",
                                 "color": CYAN, "t": 0.0, "life": 1.1, "vy": -20})
        else:
            if kind == "skill":
                target = char.cast.get("target") if char.cast else None
                if target is None or not target.alive:
                    target = min((c for c in self.chars if c.alive),
                                 key=lambda c: c.hp / c.max_hp, default=char)
                heal = 260
                target.hp = min(target.max_hp, target.hp + heal)
                target.stats_heal += heal
                target.shield = max(target.shield, 100)
                target.shield_t = max(target.shield_t, 4.0)
                self.heal_number(target.x, target.y - 70, heal)
                self.spawn_particles(target.x, target.y - 45, GREEN, 18, 110)
                self.flash(0.06, GREEN, 0.18)
            else:
                heal = 0
                for c in self.chars:
                    if c.alive:
                        h = c.max_hp * 0.25
                        c.hp = min(c.max_hp, c.hp + h)
                        c.stats_heal += h
                        heal += h
                        c.share_t = 8.0
                        self.heal_number(c.x, c.y - 70, h)
                self.flash(0.18, GREEN, 0.30)
                self.shake(0.25, 4)
                self.hit_stop(0.05)
                self.numbers.append({"x": char.x, "y": char.y - 100, "text": "同体校订", "color": AMBER,
                                     "t": 0.0, "life": 1.2, "vy": -20})
            self.audio.play("repair")

    # ------------------------------------------------------------ update
    def selected_char(self):
        return self.chars[self.selected]

    def begin_targeting(self, char):
        if char.dead or char.removed:
            return
        if char.skill_cd > 0:
            self.error("技能冷却中")
            return
        if char.state in ("skill", "ult"):
            self.error("当前无法选择目标")
            return
        self.card_target = None
        self.targeting = {"char": char}
        self.audio.play("tab")

    def cancel_targeting(self):
        if self.targeting:
            self.targeting = None
            self.audio.play("close")

    def begin_cutin(self, char):
        name = "蓝鲸现世" if char.cid == "ds" else "同体校订"
        self.cutin = {"char": char, "t": CUTIN_TIME, "name": name}
        self.flash(0.2, char.color, 0.28)
        self.shake(0.55, 10)
        self.hit_stop(0.06)
        self.audio.play("open")

    def pick_target(self, pos):
        if not self.targeting:
            return None
        char = self.targeting["char"]
        wx = pos[0] - ARENA.x
        wy = pos[1] - ARENA.y
        if char.cid == "ds":
            for e in self.enemies:
                if e.alive and math.hypot(wx - e.x, wy - e.y) <= e.r + 24:
                    return e
            return None
        for c in self.chars:
            if c.alive and not c.removed:
                if abs(wx - c.x) <= 42 and (c.y - 82) <= wy <= (c.y + 12):
                    return c
        return None

    def hover_target(self):
        if self.targeting:
            return self.pick_target(self.mouse)
        if self.card_target is not None:
            return self.enemy_at(self.mouse)
        return None

    def cast_selected(self, kind):
        c = self.selected_char()
        if kind == "skill":
            self.begin_targeting(c)
        else:
            if self.targeting:
                self.cancel_targeting()
            self.card_target = None
            c.start_ult(self)

    @staticmethod
    def _seg_dist(p, q, a, b):
        px, py = p
        ax, ay = a
        bx, by = b
        dx, dy = bx - ax, by - ay
        l2 = dx * dx + dy * dy or 1
        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / l2))
        cx, cy = ax + t * dx, ay + t * dy
        return math.hypot(px - cx, py - cy)

    @staticmethod
    def _segments_cross(a, b, c, d):
        def cross(p, q, r):
            return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
        d1, d2 = cross(c, d, a), cross(c, d, b)
        d3, d4 = cross(a, b, c), cross(a, b, d)
        return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))

    def slash_hits(self, start, end):
        hits = []
        tol = 8.0 + (8.0 if self.passive_active("EDGE") else 0.0)
        for link in self.links:
            if not link.alive:
                continue
            pts = self.link_points(link)
            hit = False
            for p, q in zip(pts, pts[1:]):
                if self._segments_cross(start, end, p, q) or self._seg_dist(start, p, q, p) < tol or self._seg_dist(end, p, q, p) < tol:
                    hit = True
                    break
            if not hit:
                for p in pts:
                    if self._seg_dist(p, p, start, end) < tol:
                        hit = True
                        break
            if hit:
                hits.append(link)
        return hits

    def start_slash(self, pos):
        if self.slash_armed is None or not ARENA.collidepoint(pos):
            return
        wx, wy = pos[0] - ARENA.x, pos[1] - ARENA.y
        self.slash = {"card": self.slash_armed, "start": (wx, wy), "pos": (wx, wy),
                      "links": [], "capped": False}
        self.slash_armed = None
        self.targeting = None
        self.card_target = None
        self.audio.play("tab")

    def update_slash(self, pos):
        if not self.slash:
            return
        sx, sy = self.slash["start"]
        wx = max(0, min(ARENA.w, pos[0] - ARENA.x))
        wy = max(0, min(ARENA.h, pos[1] - ARENA.y))
        dx, dy = wx - sx, wy - sy
        dist = math.hypot(dx, dy)
        capped = dist > SLASH_MAX_LEN
        if capped and dist > 0:
            k = SLASH_MAX_LEN / dist
            wx, wy = sx + dx * k, sy + dy * k
        self.slash["capped"] = capped
        self.slash["pos"] = (wx, wy)
        self.slash["links"] = self.slash_hits((sx, sy), (wx, wy))

    def cancel_slash(self):
        self.slash = None
        self.slash_armed = None
        self.slash_links = []

    def end_slash(self, pos):
        if not self.slash:
            return
        self.update_slash(pos)
        start = self.slash["start"]
        end = self.slash["pos"]
        idx = self.slash["card"]
        links = list(self.slash["links"])
        if math.hypot(end[0] - start[0], end[1] - start[1]) < 18 or not links:
            self.cancel_slash()
            self.audio.play("invalid")
            return
        card = self.hand[idx] if 0 <= idx < len(self.hand) else None
        if card is None:
            self.cancel_slash()
            return
        key = card.key
        plus = card.plus
        if key == "WEAK":
            targets = {l.target for l in links}
            for t in targets:
                t.weak_t = 6.0 + 2.0 * plus
                self.numbers.append({"x": t.x, "y": t.y - t.r - 34, "text": "WEAK",
                                     "color": PURPLE, "t": 0.0, "life": 0.7, "vy": -20})
            cut_links = []
            valid_effect = bool(targets)
        elif key == "TRUNC":
            targets = {l.target for l in links}
            for t in targets:
                t.take_damage((80 + 40 * plus) * self.fidelity_damage_mult(), self, AMBER)
                t.stun_t = max(t.stun_t, 1.0 + 0.5 * plus)
                t.no_destructor = True
            cut_links = []
            valid_effect = bool(targets)
        elif key == "DOWN":
            targets = {l.target for l in links}
            for t in targets:
                t.slow_t = 5.0 + 2.0 * plus
                self.numbers.append({"x": t.x, "y": t.y - t.r - 34, "text": "SLOW",
                                     "color": GREEN, "t": 0.0, "life": 0.7, "vy": -20})
            cut_links = []
            valid_effect = bool(targets)
        elif key == "CLIP":
            # CLIP is a single-target finisher: clear every incoming link of
            # the first enemy hit, not every enemy touched by the swipe.
            def first_dist(l):
                return min(math.hypot(px - start[0], py - start[1])
                           for px, py in self.link_points(l))
            first = min(links, key=first_dist)
            target = first.target
            cut_links = [l for l in target.refs if l.alive]
            valid_effect = bool(cut_links)
            if valid_effect:
                self.numbers.append({"x": target.x, "y": target.y - target.r - 42,
                                     "text": "CLIP" + ("+" * plus), "color": CYAN,
                                     "t": 0.0, "life": 0.7, "vy": -20})
        else:
            strong = [l for l in links if l.kind in ("strong", "cycle")]
            if key == "CUT":
                cut_links = strong[:1 + plus]
            elif key == "SWEEP":
                by_target = {}
                for l in strong:
                    by_target.setdefault(id(l.target), []).append(l)
                cut_links = []
                for group in by_target.values():
                    cut_links.extend(group[:1 + plus])
            else:
                cut_links = strong
            valid_effect = bool(cut_links)
        if cut_links:
            for link in cut_links:
                self.cut_link(link)
        elif not valid_effect:
            self.cancel_slash()
            self.audio.play("invalid")
            return
        self.hand[idx] = None
        card.cd = card.cdmax
        self.flash(0.05, CYAN, 0.2)
        self.shake(0.15, 2)
        self.slash = None
        self.slash_links = []
        self.audio.play("repair")

    def begin_card(self, index):
        if index < 0 or index >= len(self.hand) or self.hand[index] is None:
            return
        card = self.hand[index]
        if card.damaged:
            return
        key = card.key
        self.targeting = None
        self.card_target = None
        self.slash_armed = None
        if key in SLASH_CARDS:
            self.slash_armed = index
            self.audio.play("pick")
            return
        if key in ("ECC", "LOSSY", "PATCH", "STITCH"):
            self.use_card(index, None)
            return
        self.card_target = index
        self.audio.play("pick")

    def use_card(self, index, enemy):
        card = self.hand[index]
        if card is None or card.damaged:
            return
        key = card.key
        plus = card.plus
        targetless = key in ("ECC", "LOSSY", "SWEEP", "PATCH", "STITCH")
        if not targetless and (enemy is None or not enemy.alive):
            return
        if key == "CUT":
            if enemy.refcount > 0:
                enemy.cut_ref(self, 1)
            else:
                enemy.take_damage(110 * self.fidelity_damage_mult(), self, CYAN)
        elif key == "CLIP":
            if enemy.refcount > 0:
                enemy.cut_ref(self, enemy.refcount)
            else:
                enemy.take_damage(150 * self.fidelity_damage_mult(), self, CYAN)
        elif key == "SWEEP":
            for e in self.enemies:
                if e.alive and e.refcount > 0:
                    e.cut_ref(self, 1)
        elif key == "WEAK":
            enemy.weak_t = 6.0
            self.numbers.append({"x": enemy.x, "y": enemy.y - enemy.r - 32, "text": "WEAK 6s",
                                 "color": PURPLE, "t": 0.0, "life": 0.8, "vy": -20})
        elif key == "WEAKEN":
            if enemy.refcount > 0:
                enemy.cut_ref(self, 1)
            enemy.weak_t = 6.0
        elif key == "LINK":
            enemy.held_t = 4.0
            self.numbers.append({"x": enemy.x, "y": enemy.y - enemy.r - 32, "text": "HOLD 4s",
                                 "color": (100, 170, 255), "t": 0.0, "life": 0.8, "vy": -20})
        elif key == "VOID":
            enemy.stun_t = 2.0
            enemy.no_destructor = True
            self.numbers.append({"x": enemy.x, "y": enemy.y - enemy.r - 32, "text": "STUN 2s",
                                 "color": WHITE, "t": 0.0, "life": 0.8, "vy": -20})
        elif key == "TRUNC":
            enemy.take_damage(80 * self.fidelity_damage_mult(), self, AMBER)
            enemy.stun_t = 1.0
            enemy.no_destructor = True
        elif key == "DELAY":
            self.delayed_cuts.append({"enemy": enemy, "t": 3.0})
            self.numbers.append({"x": enemy.x, "y": enemy.y - enemy.r - 32, "text": "DELAY 3s",
                                 "color": CYAN, "t": 0.0, "life": 0.8, "vy": -20})
        elif key == "REFLECT":
            enemy.reflect_t = 6.0
            self.numbers.append({"x": enemy.x, "y": enemy.y - enemy.r - 32, "text": "REFLECT 6s",
                                 "color": (255, 190, 220), "t": 0.0, "life": 0.8, "vy": -20})
        elif key == "ALIAS":
            enemy.alias_t = 6.0
            self.numbers.append({"x": enemy.x, "y": enemy.y - enemy.r - 32, "text": "ALIAS 6s",
                                 "color": (200, 150, 255), "t": 0.0, "life": 0.8, "vy": -20})
        elif key == "STEAL":
            if enemy.refcount > 0:
                enemy.cut_ref(self, 1)
            self.change_fidelity(10.0, "steal")
        elif key == "COMPRESS":
            self.compress_t = 8.0
            self.change_fidelity(-10.0, "compress")
            self.numbers.append({"x": self.ds.x, "y": self.ds.y - 90, "text": "COMPRESS +30%",
                                 "color": (255, 180, 100), "t": 0.0, "life": 1.0, "vy": -20})
        elif key == "ECC":
            self.change_fidelity(30.0 + 10.0 * plus, "ecc")
            self.rings.append({"x": self.ds.x, "y": self.ds.y - 40, "r": 8, "max": 70,
                               "t": 0.0, "life": 0.5, "color": GREEN})
        elif key in ("PATCH", "STITCH"):
            living = [c for c in self.chars if c.alive and not c.removed]
            if living:
                target = min(living, key=lambda c: c.hp / max(1, c.max_hp))
                ratio = (0.18 if key == "PATCH" else 0.12) + (0.06 if key == "PATCH" else 0.04) * plus
                heal = target.max_hp * ratio
                target.hp = min(target.max_hp, target.hp + heal)
                self.heal_number(target.x, target.y - 70, heal)
                if key == "STITCH":
                    target.guard_t = max(target.guard_t, 2.0)
                    self.rings.append({"x": target.x, "y": target.y - 30, "r": 8, "max": 48,
                                       "t": 0.0, "life": 0.45, "color": GREEN})
        elif key == "LOSSY":
            for e in self.enemies:
                if e.alive:
                    e.take_damage(70 * self.fidelity_damage_mult(), self, (255, 150, 80))
            self.change_fidelity(-10.0, "lossy")
        elif key == "DOWN":
            enemy.slow_t = 5.0
            self.numbers.append({"x": enemy.x, "y": enemy.y - enemy.r - 32, "text": "SLOW 5s",
                                 "color": GREEN, "t": 0.0, "life": 0.8, "vy": -20})
        if enemy is not None:
            self.spawn_particles(enemy.x, enemy.y, CARD_INFO[key]["color"], 12)
        self.hand[index] = None
        card.cd = card.cdmax
        self.card_target = None
        self.audio.play("repair")

    def update(self, dt):
        if self.paused:
            return
        if self.cutin:
            self.cutin["t"] -= dt
            if self.cutin["t"] <= 0:
                self.cutin = None
            return
        if self.state == "between":
            self.update_memory_cd(dt)
            self.wave_t -= dt
            self.wave_banner = max(0.0, self.wave_banner - dt)
            if self.wave_t <= 0:
                self.wave += 1
                for c in self.chars:
                    if c.alive:
                        c.hp = min(c.max_hp, c.hp + c.max_hp * 0.22)
                        c.shield = 0
                self.spawn_wave(self.wave)
                self.state = "fight"
            return
        if self.targeting and self.targeting["char"].dead:
            self.targeting = None
        slow = 0.22 if (self.targeting or self.card_target is not None or self.slash is not None) else 1.0
        step = dt * self.speed * slow
        self.time += step
        self.update_memory_cd(step)
        self.wave_banner = max(0.0, self.wave_banner - step)
        self.compress_t = max(0.0, self.compress_t - step)
        self.fidelity_flash_t = max(0.0, self.fidelity_flash_t - step)
        self.fidelity_pop_t = max(0.0, self.fidelity_pop_t - step)
        self.fidelity_warn_t = max(0.0, self.fidelity_warn_t - step)
        self.fidelity_heal_t = max(0.0, self.fidelity_heal_t - step)
        self.fidelity_alert_t = max(0.0, self.fidelity_alert_t - step)
        for threat in list(self.fidelity_threats):
            threat["t"] -= step
            if threat["t"] <= 0:
                self.fidelity_threats.remove(threat)
        if self.state == "defeat":
            self.end_t += dt
            return
        if self.state == "victory":
            self.end_t += dt
            return
        if self.state == "intro":
            self.state = "fight"
        if self.hitstop > 0:
            self.hitstop = max(0.0, self.hitstop - dt)
            return
        for c in self.chars:
            c.update(step, self)
        for e in self.enemies:
            e.update(step, self)
        self.separate_enemies(step)
        # player projectiles
        for p in list(self.projectiles):
            target = p.target
            if target is None or not target.alive:
                self.projectiles.remove(p)
                continue
            dx, dy = target.x - p.x, target.y - p.y
            dist = math.hypot(dx, dy) or 1
            if dist < target.r + p.radius:
                target.take_damage(p.damage, self, p.color)
                if p.kind == "ds":
                    self.ds.gain_ult(8)
                elif self.recruited:
                    self.claude.gain_ult(8)
                self.spawn_particles(p.x, p.y, p.color, 7)
                self.flash(0.025, p.color, 0.12)
                self.hit_stop(0.018)
                self.projectiles.remove(p)
                continue
            p.x += dx / dist * p.speed * step
            p.y += dy / dist * p.speed * step
            p.life -= step
            if p.life <= 0:
                self.projectiles.remove(p)
        # boss balls
        for b in list(self.balls):
            b.x += b.vx * step
            b.y += b.vy * step
            b.life -= step
            if random.random() < 0.4:
                self.effects.append(Effect("p", b.x, b.y, 0, 0.25, b.color, 2, 0, 0))
            hit = False
            for c in self.chars:
                if c.alive and math.hypot(c.x - b.x, (c.y - 35) - b.y) < 30:
                    c.take_damage(b.damage, self)
                    if random.random() < b.necro:
                        self.necro_cell("ball")
                    hit = True
                    break
            if hit or b.life <= 0 or not (ARENA.x - 40 < b.x < ARENA.right + 40):
                if hit:
                    self.spawn_particles(b.x, b.y, b.color, 10, 120)
                    self.flash(0.04, RED, 0.2)
                self.balls.remove(b)
        # effects
        for d in list(self.delayed_cuts):
            d["t"] -= step
            if d["t"] <= 0:
                e = d["enemy"]
                if e.alive:
                    e.cut_ref(self, 1)
                self.delayed_cuts.remove(d)
        for e in list(self.effects):
            e.t += step
            e.x += e.vx * step
            e.y += e.vy * step
            e.vy += 150 * step
            if e.t >= e.life:
                self.effects.remove(e)
        for r in list(self.rings):
            r["t"] += step
            if r["t"] >= r["life"]:
                self.rings.remove(r)
        for n in list(self.numbers):
            n["t"] += step
            n["y"] += n["vy"] * step
            if n["t"] >= n["life"]:
                self.numbers.remove(n)
        self.shake_t = max(0.0, self.shake_t - step)
        self.flash_t = max(0.0, self.flash_t - step)
        if self.shake_t <= 0:
            self.shake_power = 0
        if self.flash_t <= 0:
            self.flash_alpha = 0
        if self.selected_char().dead:
            for i, c in enumerate(self.chars):
                if c.alive and not c.removed:
                    self.selected = i
                    break
        if all(c.removed for c in self.chars):
            self.state = "defeat"
        if self.fidelity <= 0 and self.state == "fight":
            self.state = "defeat"
            self.end_t = 0
        self.selected = min(self.selected, len(self.chars) - 1)

    # ------------------------------------------------------------ UI draw
    def draw(self):
        s = self.canvas
        s.fill(INK)
        for x in range(0, W, 16):
            pygame.draw.line(s, (10, 16, 23), (x, 0), (x, H))
        for y in range(0, H, 16):
            pygame.draw.line(s, (10, 16, 23), (0, y), (W, y))
        self.draw_top(s)
        self.draw_party(s)
        self.draw_arena(s)
        self.draw_arena_flash(s)
        self.draw_right(s)
        self.draw_bottom(s)
        self.draw_card_throws(s)
        self.draw_tooltip(s)
        self.draw_fidelity_fx(s)
        self.draw_fidelity_debuff(s)
        if self.cutin:
            self.draw_cutin(s)
        if self.state == "defeat":
            self.draw_defeat(s)
        elif self.state == "victory":
            self.draw_victory(s)
        elif self.state == "between":
            box = pygame.Rect(W // 2 - 180, ARENA.centery - 36, 360, 72)
            pygame.draw.rect(s, (10, 20, 24), box)
            pygame.draw.rect(s, GREEN, box, 2)
            self.text(s, "WAVE CLEAR", (box.centerx, box.y + 14), GREEN, self.font24, center=True)
            self.text(s, f"NEXT WAVE {self.wave + 1} INCOMING", (box.centerx, box.y + 46),
                      MUTED, self.mono10, center=True)

    def draw_arena_flash(self, s):
        if self.flash_alpha <= 0 or self.flash_t <= 0:
            return
        alpha = int(48 * self.flash_alpha * min(1.0, self.flash_t * 14))
        if alpha <= 0:
            return
        overlay = pygame.Surface(ARENA.size, pygame.SRCALPHA)
        overlay.fill((*self.flash_color, alpha))
        s.blit(overlay, ARENA.topleft)

    def _ensure_fidelity_fx(self):
        if hasattr(self, "fid_scan"):
            return
        self.fid_scan = pygame.Surface((W, H), pygame.SRCALPHA)
        for y in range(0, H, 4):
            pygame.draw.line(self.fid_scan, (0, 0, 0, 48), (0, y), (W, y), 1)
        self.fid_noise = []
        for k in range(4):
            rng = random.Random(70 + k)
            ns = pygame.Surface((W // 4, H // 4), pygame.SRCALPHA)
            for _ in range(360):
                x = rng.randrange(ns.get_width())
                y = rng.randrange(ns.get_height())
                col = rng.choice(((220, 245, 255, 80), (255, 100, 120, 60),
                                  (150, 255, 220, 55), (255, 255, 255, 70)))
                ns.set_at((x, y), col)
                if rng.random() < 0.22:
                    ns.set_at((min(ns.get_width() - 1, x + 1), y), col)
            self.fid_noise.append(ns)

    def draw_fidelity_debuff(self, s):
        if self.fidelity >= 50:
            # Above 50 the battlefield keeps full resolution. Only a very
            # faint scanline/noise shimmer remains, never tint or tearing.
            self._ensure_fidelity_fx()
            if self.fidelity >= 75:
                scan_alpha, noise_alpha = 3, 0
            else:
                level = max(0.0, min(1.0, (75.0 - self.fidelity) / 25.0))
                scan_alpha, noise_alpha = int(6 + 10 * level), int(4 + 6 * level)
            self.fid_scan.set_alpha(scan_alpha)
            s.blit(self.fid_scan, (0, 0))
            if noise_alpha:
                noise = pygame.transform.scale(self.fid_noise[int(self.time * 7) % 4], (W, H))
                noise.set_alpha(noise_alpha)
                s.blit(noise, (0, 0))
            # one slow, low-contrast sweep line: atmosphere without blocking
            sy = int((self.time * 17) % H)
            sweep = pygame.Surface((W, 1), pygame.SRCALPHA)
            sweep.fill((170, 230, 245, 7 if self.fidelity >= 75 else 12))
            s.blit(sweep, (0, sy))
            return
        self._ensure_fidelity_fx()
        level = max(0.0, min(1.0, (75.0 - self.fidelity) / 75.0))
        self.fid_scan.set_alpha(int(18 + 42 * level))
        s.blit(self.fid_scan, (0, 0))
        noise = pygame.transform.scale(self.fid_noise[int(self.time * 9) % 4], (W, H))
        noise.set_alpha(int(10 + 42 * level))
        s.blit(noise, (0, 0))
        if level > 0.45:
            tint = pygame.Surface((W, H), pygame.SRCALPHA)
            tint.fill((40, 120, 140, int(10 + 18 * level)))
            s.blit(tint, (0, 0))
            edge = pygame.Surface((W, H), pygame.SRCALPHA)
            pygame.draw.rect(edge, (8, 18, 22, int(20 + 50 * level)), (0, 0, W, H), 5)
            s.blit(edge, (0, 0))
        if self.fidelity < 50:
            rng = random.Random(int(self.time * 12) + int(self.fidelity * 10))
            snap = s.copy()
            bars = 1 + int((50 - self.fidelity) / 14)
            for _ in range(bars):
                y = rng.randrange(44, H - 60)
                h = rng.randrange(2, 9)
                dx = rng.randint(-14, 14)
                s.blit(snap, (dx, y), (0, y, W, h))
                bar = pygame.Surface((W, h), pygame.SRCALPHA)
                col = rng.choice(((255, 40, 80, 65), (60, 220, 255, 55), (8, 12, 18, 95)))
                bar.fill(col)
                s.blit(bar, (0, y))
        if self.fidelity < 25 and int(self.time * 3) % 5 == 0:
            self.text(s, "SIGNAL LOSS", (W - 146, 48), (255, 80, 95), self.mono10)

    def draw_fidelity_fx(self, s):
        if self.fidelity_flash_t > 0 or self.fidelity_heal_t > 0:
            edge = pygame.Surface((W, H), pygame.SRCALPHA)
            if self.fidelity_flash_t > 0:
                a = int(100 * min(1.0, self.fidelity_flash_t / 0.35))
                pygame.draw.rect(edge, (255, 35, 55, a), (0, 0, W, H), 7)
                pygame.draw.line(edge, (255, 110, 110, a), (0, 3), (W, 3), 2)
            if self.fidelity_heal_t > 0:
                a = int(80 * min(1.0, self.fidelity_heal_t / 0.55))
                pygame.draw.rect(edge, (80, 230, 160, a), (0, 0, W, H), 4)
            s.blit(edge, (0, 0))
        if self.fidelity_pop_t > 0:
            k = min(1.0, self.fidelity_pop_t / 1.0)
            v = self.fidelity_pop_value
            col = (255, 100, 100) if v < 0 else (120, 255, 180)
            text = f"{v:+.0f} FIDELITY" if v else "FIDELITY"
            y = 46 + int((1.0 - k) * 16)
            self.text(s, text, (205, y), col, self.font12)
        if self.fidelity_warn_t > 0:
            pulse = 0.5 + 0.5 * math.sin(self.time * 10)
            col = (255, 220, 100) if self.fidelity_warn_value >= 50 else (255, 115, 95)
            box = pygame.Rect(ARENA.centerx - 118, ARENA.bottom - 54, 236, 26)
            pygame.draw.rect(s, (30, 16, 18), box)
            pygame.draw.rect(s, col, box, 1 + int(pulse * 2))
            self.text(s, f"FIDELITY 低于 {self.fidelity_warn_value}%", box.center,
                      col, self.font11, center=True)

    def draw_top(self, s):
        pygame.draw.rect(s, (9, 14, 21), (0, 0, W, 44))
        pygame.draw.line(s, LINE, (0, 44), (W, 44), 1)
        self.text(s, f"WAVE {self.wave}/{self.wave_max}", (16, 8), TEXT, self.font14)
        self.text(s, "TIME", (126, 8), DIM, self.font11)
        self.text(s, self.clock_text(), (126, 23), MUTED, self.mono12)
        # fidelity bar
        fcol = self.fidelity_color()
        self.text(s, "FIDELITY / 保真度", (205, 3), fcol, self.font11)
        bar = pygame.Rect(205, 20, 150, 15)
        pygame.draw.rect(s, (28, 20, 27), bar)
        fill = max(0, int((bar.w - 4) * self.fidelity / self.fidelity_max))
        pygame.draw.rect(s, fcol, (bar.x + 2, bar.y + 2, fill, bar.h - 4))
        for th in (25, 50, 75):
            x = bar.x + 2 + int((bar.w - 4) * th / 100.0)
            pygame.draw.line(s, (10, 16, 20), (x, bar.y + 2), (x, bar.bottom - 3), 1)
        if self.fidelity_cap < self.fidelity_max:
            capx = bar.x + 2 + int((bar.w - 4) * self.fidelity_cap / self.fidelity_max)
            pygame.draw.line(s, (255, 225, 150), (capx, bar.y - 2), (capx, bar.bottom), 2)
        border = (255, 240, 180) if self.fidelity_flash_t > 0 else (83, 106, 122)
        pygame.draw.rect(s, border, bar, 2 if self.fidelity_flash_t > 0 else 1)
        self.text(s, f"{int(round(self.fidelity))}", (362, 16), fcol, self.font16)
        self.text(s, f"CAP {self.fidelity_cap:.0f}", (398, 3), (255, 225, 150), self.mono10)
        self.text(s, f"DMG×{self.fidelity_damage_mult():.2f}", (398, 20), fcol, self.mono10)
        self.text(s, "WORK", (468, 8), DIM, self.font11)
        self.text(s, "∞", (468, 23), CYAN, self.mono12)
        self.text(s, "ENEMY", (525, 8), DIM, self.font11)
        alive = sum(1 for e in self.enemies if e.alive)
        self.text(s, f"{alive} / {len(self.enemies)}", (525, 23), RED if alive else GREEN, self.mono12)
        self.text(s, "内存远征 / BATTLE PROTOTYPE", (W // 2 - 50, 8), MUTED, self.font11)
        # pause / speed
        pygame.draw.rect(s, (22, 34, 47), self.pause_rect)
        pygame.draw.rect(s, (55, 78, 95), self.pause_rect, 1)
        self.text(s, "Ⅱ" if not self.paused else "▶", self.pause_rect.center, TEXT, self.font12, center=True)
        pygame.draw.rect(s, (22, 34, 47), self.speed_rect)
        pygame.draw.rect(s, (55, 78, 95), self.speed_rect, 1)
        self.text(s, f"{self.speed:g}x", self.speed_rect.center, TEXT, self.font11, center=True)

    def clock_text(self):
        sec = int(self.time)
        return f"{sec // 60:02d}:{sec % 60:02d}"

    def draw_party(self, s):
        x, y = 8, 52
        self.party_hits = []
        for i, c in enumerate(self.chars + [None]):
            r = pygame.Rect(x, y + i * 158, 170, 150)
            on = i == self.selected and c is not None
            pygame.draw.rect(s, (18, 34, 50) if on else PANEL, r)
            pygame.draw.rect(s, c.color if on else (42, 58, 73) if c else (30, 42, 54), r, 2 if on else 1)
            if c is None:
                self.text(s, "空位", (r.centerx, r.y + 46), (55, 74, 90), self.font14, center=True)
                self.text(s, "WAITING", (r.centerx, r.y + 68), (48, 64, 78), self.mono10, center=True)
                pygame.draw.line(s, (35, 48, 61), (r.x + 24, r.y + 92), (r.right - 24, r.y + 92), 1)
                self.party_hits.append((i, r))
                continue
            s.blit(c.portrait, (r.x + 10, r.y + 10))
            self.text(s, c.name, (r.x + 76, r.y + 10), c.color, self.font16)
            self.text(s, c.role, (r.x + 76, r.y + 31), MUTED, self.font11)
            bar = pygame.Rect(r.x + 10, r.y + 78, 150, 8)
            pygame.draw.rect(s, (28, 20, 27), bar)
            pygame.draw.rect(s, c.color, (bar.x, bar.y, int(bar.w * c.hp / c.max_hp), bar.h))
            pygame.draw.rect(s, (78, 97, 112), bar, 1)
            self.text(s, f"{int(c.hp)}/{int(c.max_hp)}", (r.x + 10, r.y + 90), MUTED, self.mono10)
            ult_txt = "USED" if c.ult_used else f"ULT {int(c.ult_energy)}/100"
            self.text(s, ult_txt, (r.x + 10, r.y + 108),
                      AMBER if c.ult_energy >= 100 or c.ult_used else CYAN, self.mono10)
            if c.ult_energy >= 100 and not c.ult_used and not c.dead:
                flow = (150 + int(60 * (0.5 + 0.5 * math.sin(self.time * 7))),
                        225, 255)
                pygame.draw.rect(s, flow, r, 2)
                for j in range(4):
                    px = r.x + int((self.time * 70 + j * r.w / 4) % r.w)
                    pygame.draw.circle(s, (255, 245, 170), (px, r.y), 2)
                    pygame.draw.circle(s, (255, 210, 100), (px, r.bottom - 1), 2)
            if c.dead:
                self.text(s, "OFFLINE" if c.removed else "DEAD", (r.x + 96, r.y + 108), RED, self.mono10)
            elif c.shield > 0:
                self.text(s, f"SHIELD {int(c.shield)}", (r.x + 90, r.y + 108), (120, 200, 255), self.mono10)
            if not c.dead:
                ready = c.dodge_cd <= 0
                self.text(s, f"DODGE {int(c.dodge_rate * 100)}%", (r.x + 10, r.y + 126),
                          CYAN if ready else (73, 105, 126), self.mono10)
                self.text(s, "READY" if ready else f"CD {c.dodge_cd:.1f}", (r.x + 96, r.y + 126),
                          GREEN if ready else (105, 80, 80), self.mono10)
            self.party_hits.append((i, r))

    def link_points(self, link):
        if isinstance(link.source, tuple):
            sx, sy = link.source[0], link.source[1] + 16
        else:
            sx, sy = link.source.x, link.source.y - link.source.r
        tx, ty = link.target.x, link.target.y - link.target.r
        siblings = [l for l in self.links
                    if l.alive and l.source is link.source and l.target is link.target]
        try:
            idx = siblings.index(link)
        except ValueError:
            idx = 0
        n = max(1, len(siblings))
        vx, vy = tx - sx, ty - sy
        length = math.hypot(vx, vy) or 1
        ux, uy = vx / length, vy / length
        nx, ny = -uy, ux
        bend = (idx - (n - 1) / 2.0) * 14.0
        # Cubic bezier: control points are pulled along the tangent and
        # offset perpendicular, so even a single edge reads as a curve.
        c1x, c1y = sx + vx * 0.24 + nx * bend, sy + vy * 0.24 + ny * bend
        c2x, c2y = tx - vx * 0.24 + nx * bend * 1.25, ty - vy * 0.24 + ny * bend * 1.25
        pts = []
        for i in range(25):
            k = i / 24.0
            x = ((1 - k) ** 3) * sx + 3 * ((1 - k) ** 2) * k * c1x + 3 * (1 - k) * (k ** 2) * c2x + (k ** 3) * tx
            y = ((1 - k) ** 3) * sy + 3 * ((1 - k) ** 2) * k * c1y + 3 * (1 - k) * (k ** 2) * c2y + (k ** 3) * ty
            pts.append((x, y))
        return pts

    def draw_links(self, s):
        hot = set()
        if getattr(self, "slash", None):
            hot = {id(l) for l in self.slash.get("links", [])}
        for link in self.links:
            if not link.alive:
                continue
            pts = self.link_points(link)
            is_hot = id(link) in hot
            col = (255, 245, 170) if is_hot else link.color
            # soft dark halo, colored body, bright center
            pygame.draw.lines(s, (4, 9, 14), False,
                              [(int(x), int(y)) for x, y in pts], 7 if is_hot else 5)
            pygame.draw.lines(s, (int(col[0] * 0.42), int(col[1] * 0.42), int(col[2] * 0.42)),
                              False, [(int(x), int(y)) for x, y in pts], 4 if is_hot else 3)
            if link.kind == "support":
                # gold link: broken dashes make support distinct from STRONG
                for i in range(0, len(pts) - 3, 4):
                    seg = [(int(x), int(y)) for x, y in pts[i:i + 3]]
                    pygame.draw.lines(s, col, False, seg, 3 if is_hot else 2)
            else:
                pygame.draw.lines(s, col, False,
                                  [(int(x), int(y)) for x, y in pts], 3 if is_hot else 2)
                pygame.draw.lines(s, (min(255, col[0] + 55), min(255, col[1] + 55), min(255, col[2] + 55)),
                                  False, [(int(x), int(y)) for x, y in pts[2:-2]], 1)
            # moving data packets along the reference
            for k in range(2):
                phase = (self.time * 0.34 + k * 0.5 + (abs(hash(id(link))) % 97) / 97.0) % 1.0
                pi = min(len(pts) - 2, int(phase * (len(pts) - 1)))
                px, py = pts[pi]
                pygame.draw.circle(s, (235, 250, 255) if not is_hot else (255, 245, 170),
                                   (int(px), int(py)), 2 if not is_hot else 3)
            # arrow head at the target
            ex, ey = pts[-1]
            px, py = pts[-3]
            ang = math.atan2(ey - py, ex - px)
            for da in (-0.55, 0.55):
                ax = ex - math.cos(ang + da) * 10
                ay = ey - math.sin(ang + da) * 10
                pygame.draw.line(s, col, (ex, ey), (ax, ay), 2)
            pygame.draw.circle(s, (8, 14, 20), (int(ex), int(ey)), 4)
            pygame.draw.circle(s, col, (int(ex), int(ey)), 3, 1)

    def draw_arena(self, s):
        w, h = ARENA.size
        self.world.fill((10, 15, 23))
        # circuit floor
        for x in range(0, w, 36):
            pygame.draw.line(self.world, (18, 29, 40), (x, 0), (x, h))
        for y in range(0, h, 36):
            pygame.draw.line(self.world, (18, 29, 40), (0, y), (w, y))
        pygame.draw.rect(self.world, (25, 38, 52), (0, 0, w, h), 2)
        # arena glyph
        pygame.draw.circle(self.world, (25, 39, 53), (w // 2, h // 2), 190, 1)
        pygame.draw.circle(self.world, (24, 37, 50), (w // 2, h // 2), 130, 1)
        # all reference edges, one curve per edge
        self.draw_links(self.world)
        for root in self.roots:
            draw_root(self.world, root)
        for e in self.enemies:
            if not e.alive:
                continue
            self.text(self.world, e.name, (int(e.x), int(e.y - e.r - 30)),
                      e.color, self.font11, center=True)
            e.draw(self.world, self.time)
        # fidelity-threat spotlight
        for threat in self.fidelity_threats:
            e = threat["enemy"]
            if not e.alive:
                continue
            pulse = 1 + int(2 * (0.5 + 0.5 * math.sin(self.time * 8)))
            pygame.draw.circle(self.world, (255, 215, 90), (int(e.x), int(e.y)), e.r + 12 + pulse, 2)
            self.text(self.world, "保真度 -8 / 3s", (int(e.x), int(e.y - e.r - 52)),
                      (255, 220, 100), self.font11, center=True)
        # selection ring
        sel = self.selected_char()
        if sel.alive:
            pygame.draw.ellipse(self.world, (*sel.color, 90), (sel.x - 46, sel.y + 4, 92, 20), 1)
        # characters
        for c in self.chars:
            if c.removed:
                continue
            c.draw(self.world)
            if c is sel and c.alive:
                pygame.draw.ellipse(self.world, c.color, (c.x - 28, c.y + 4, 56, 10), 2)
            # hp above
            if c.alive:
                br = pygame.Rect(c.x - 32, c.y - 86, 64, 4)
                pygame.draw.rect(self.world, (28, 20, 27), br)
                pygame.draw.rect(self.world, c.color, (br.x, br.y, int(br.w * c.hp / c.max_hp), br.h))
                if c.shield > 0:
                    pygame.draw.rect(self.world, (100, 190, 255), br, 1)
            if c.share_t > 0 and c is self.ds and self.claude.alive:
                pygame.draw.line(self.world, (170, 240, 255), (self.ds.x, self.ds.y - 55),
                                 (self.claude.x, self.claude.y - 55), 2)
        if self.slash:
            sx, sy = self.slash["start"]
            ex, ey = self.slash["pos"]
            hot = bool(self.slash.get("links"))
            capped = self.slash.get("capped")
            col = (255, 170, 95) if capped else ((255, 240, 150) if hot else (130, 190, 210))
            pygame.draw.line(self.world, (20, 30, 38), (sx, sy), (ex, ey), 7)
            pygame.draw.line(self.world, col, (sx, sy), (ex, ey), 3)
            pygame.draw.circle(self.world, col, (int(sx), int(sy)), 4, 1)
            pygame.draw.circle(self.world, col, (int(ex), int(ey)), 5, 1)
            if capped:
                pygame.draw.circle(self.world, (255, 190, 100), (int(ex), int(ey)), 10, 1)
                self.text(self.world, "MAX", (int(ex) + 12, int(ey) - 14), (255, 190, 100),
                          self.font11)
        # low-fidelity rendering: degrade the battlefield before target UI
        factor = self.fidelity_resolution_factor()
        if factor < 1.0:
            low = pygame.transform.scale(
                self.world, (max(1, int(ARENA.w * factor)), max(1, int(ARENA.h * factor))))
            self.world = pygame.transform.scale(low, ARENA.size)
        if self.targeting or self.card_target is not None:
            # Only the object actually under the cursor is a valid target and
            # gets a highlight; everything else stays dimmed.
            hover = self.hover_target()
            dim = pygame.Surface(ARENA.size, pygame.SRCALPHA)
            dim.fill((0, 0, 0, 104))
            if hover is not None:
                if isinstance(hover, Enemy):
                    pygame.draw.circle(dim, (0, 0, 0, 0),
                                       (int(hover.x), int(hover.y)), hover.r + 22)
                else:
                    pygame.draw.ellipse(dim, (0, 0, 0, 0),
                                        (hover.x - 42, hover.y - 98, 84, 112))
            self.world.blit(dim, (0, 0))
            pulse = 2 + int(2 * (0.5 + 0.5 * math.sin(self.time * 7)))
            if isinstance(hover, Enemy):
                pygame.draw.circle(self.world, (255, 220, 100),
                                   (int(hover.x), int(hover.y)), hover.r + 15 + pulse, 2)
                self.text(self.world, "目标", (int(hover.x), int(hover.y - hover.r - 46)),
                          (255, 225, 120), self.font11, center=True)
            elif hover is not None:
                pygame.draw.ellipse(self.world, (130, 255, 190),
                                    (hover.x - 38, hover.y - 3, 76, 16), 2 + pulse // 2)
                self.text(self.world, "友方目标", (hover.x, hover.y - 104),
                          (150, 255, 195), self.font11, center=True)
        # projectiles
        for p in self.projectiles:
            pygame.draw.circle(self.world, p.color, (int(p.x), int(p.y)), p.radius)
            pygame.draw.circle(self.world, (230, 250, 255), (int(p.x), int(p.y)), 2)
        for b in self.balls:
            pygame.draw.circle(self.world, (22, 8, 15), (int(b.x), int(b.y)), b.radius + 3)
            pygame.draw.circle(self.world, b.color, (int(b.x), int(b.y)), b.radius)
            pygame.draw.circle(self.world, (255, 210, 220), (int(b.x), int(b.y)), 2)
        # effects
        for e in self.effects:
            if e.kind == "p":
                a = max(0, 1 - e.t / e.life)
                pygame.draw.rect(self.world, e.color, (int(e.x), int(e.y), max(1, int(e.size)), max(1, int(e.size))))
        for r in self.rings:
            k = min(1.0, r["t"] / max(0.001, r["life"]))
            rad = int(r["r"] + (r["max"] - r["r"]) * k)
            pygame.draw.circle(self.world, r["color"], (int(r["x"]), int(r["y"])), rad, 1)
        for n in self.numbers:
            self.text(self.world, n["text"], (n["x"], n["y"]), n["color"], self.font14, center=True)
        # shake offset
        sx = random.randint(-int(self.shake_power), int(self.shake_power)) if self.shake_t > 0 else 0
        sy = random.randint(-int(self.shake_power), int(self.shake_power)) if self.shake_t > 0 else 0
        self.world_offset = (sx, sy)
        s.blit(self.world, (ARENA.x + sx, ARENA.y + sy))
        pygame.draw.rect(s, (52, 74, 93), ARENA, 2)
        core = next((e for e in self.enemies if e.alive and e.kind == "GC_CORE"), None)
        if core:
            br = pygame.Rect(ARENA.centerx - 180, ARENA.y + 10, 360, 12)
            pygame.draw.rect(s, (30, 12, 28), br)
            pygame.draw.rect(s, (255, 90, 210), br, 1)
            ratio = max(0, core.hp / core.max_hp)
            pygame.draw.rect(s, (190, 55, 150), (br.x + 2, br.y + 2, int((br.w - 4) * ratio), br.h - 4))
            self.text(s, "GC_CORE", (br.x, br.y - 14), (255, 170, 230), self.font11)
            pylons = sum(1 for e in self.enemies if e.alive and e.kind == "PYLON")
            status = f"IMMUNE · PYLON {pylons}" if pylons else "EXPOSED"
            self.text(s, status, (br.right, br.y - 14), (255, 210, 120) if pylons else GREEN,
                      self.mono10)
        # root title
        self.text(s, "SCOPE // ROOT", (ARENA.x + 12, ARENA.y + 10), (120, 220, 245), self.font11)
        self.text(s, "REFERENCE GRAPH · ALIVE " + str(sum(1 for e in self.enemies if e.alive)),
                  (ARENA.x + 12, ARENA.y + 25), (90, 130, 150), self.mono10)
        quant = next((e for e in self.enemies if e.alive and e.kind == "QUANTIZER"), None)
        if quant is not None:
            pulse = 0.6 + 0.4 * (0.5 + 0.5 * math.sin(self.time * 7))
            self.text(s, f"QUANTIZER // FIDELITY -8 / {max(0.0, quant.quant_tick):.1f}s",
                      (ARENA.x + 12, ARENA.y + 42),
                      (255, int(180 * pulse + 40), 105), self.font12)
        if self.targeting:
            self.text(s, "SLOW MOTION · 选择目标 · 右键取消", (ARENA.centerx, ARENA.bottom - 24),
                      (190, 245, 255), self.font12, center=True)
        elif self.card_target is not None:
            self.text(s, "SLOW MOTION · 目标高亮", (ARENA.centerx, ARENA.bottom - 24),
                      (255, 220, 130), self.font12, center=True)

    def _card_order(self, cards):
        return sorted(
            cards,
            key=lambda c: (0 if c.break_t > 0 else 1, 0 if c.cd > 0 else 1, -c.cd, c.uid or 0),
        )

    def _draw_skill_section(self, s, rect, cards, scroll, empty_text):
        if not cards:
            self.text(s, empty_text, rect.center, (55, 72, 86), self.font11, center=True)
            return 0.0, 0.0
        row_h = 23
        content_h = len(cards) * row_h
        max_scroll = max(0.0, content_h - rect.h)
        scroll = max(0.0, min(max_scroll, scroll))
        old_clip = s.get_clip()
        s.set_clip(rect)
        for i, card in enumerate(cards):
            y = rect.y + i * row_h - int(scroll)
            if y + row_h < rect.y or y > rect.bottom:
                continue
            dropping = card.break_t > 0
            x = 0
            if dropping:
                x += int(math.sin(self.time * 48) * 3)
            row = pygame.Rect(rect.x + x, y, rect.w - 4, row_h - 2)
            if row.bottom < rect.y or row.y > rect.bottom:
                continue
            red = dropping or card.damaged
            col = (255, 82, 98) if red else card.info["color"]
            pygame.draw.rect(s, (58, 16, 24) if red else (14, 23, 31), row)
            pygame.draw.rect(s, col, row, 1)
            pygame.draw.rect(s, col, (row.x, row.y, 3, row.h))
            if card.cd > 0 and not card.damaged:
                ratio = max(0.0, min(1.0, card.cd / card.cdmax))
                ow = max(1, int(row.w * ratio))
                ov = pygame.Surface((ow, row.h), pygame.SRCALPHA)
                ov.fill((125, 136, 148, 105))
                s.blit(ov, row.topleft)
            name = card.info["cn"] + ("+" * card.plus) + (" BROKEN" if red else "")
            self.text(s, name, (row.x + 8, row.y + 4), (255, 210, 215) if red else TEXT, self.font11)
            self.text(s, card.info["en"][:9], (row.right - 88, row.y + 5),
                      (255, 145, 155) if red else card.info["color"], self.mono10)
            if card.cd > 0 and not card.damaged:
                self.text(s, f"{card.cd:.1f}", (row.right - 22, row.y + 5), (245, 248, 255),
                          self.mono10, center=True)
        s.set_clip(old_clip)
        if content_h > rect.h:
            track = pygame.Rect(rect.right - 2, rect.y, 2, rect.h)
            pygame.draw.rect(s, (26, 38, 50), track)
            thumb_h = max(12, int(rect.h * rect.h / content_h))
            thumb_y = rect.y + int((rect.h - thumb_h) * (scroll / max_scroll)) if max_scroll else rect.y
            pygame.draw.rect(s, (95, 135, 155), (track.x, thumb_y, 2, thumb_h))
        return max_scroll, scroll

    def draw_card_throws(self, s):
        for throw in self.card_throws:
            if throw["age"] < 0:
                continue
            fade = min(1.0, throw["age"] / 0.10) * max(0.0, 1.0 - throw["age"] / throw["life"])
            if fade <= 0:
                continue
            surf = pygame.Surface((158, 24), pygame.SRCALPHA)
            pygame.draw.rect(surf, (52, 14, 22, 235), (0, 0, 158, 24))
            pygame.draw.rect(surf, (255, 82, 98, 255), (0, 0, 158, 24), 2)
            pygame.draw.line(surf, (255, 170, 175), (8, 6), (30, 18), 1)
            pygame.draw.line(surf, (255, 170, 175), (12, 4), (34, 12), 1)
            self.text(surf, throw["name"], (8, 5), (255, 225, 228), self.font11)
            self.text(surf, "BROKEN", (105, 6), (255, 120, 132), self.mono10)
            img = pygame.transform.rotate(surf, throw["rot"])
            img.set_alpha(int(255 * fade))
            rect = img.get_rect(center=(int(throw["x"]), int(throw["y"])))
            s.blit(img, rect)
            # trailing sparks
            for i in range(1, 4):
                px = throw["x"] - throw["vx"] * i * 0.035
                py = throw["y"] - throw["vy"] * i * 0.035 + i * i * 2.5
                pygame.draw.circle(s, (255, 90, 105), (int(px), int(py)), max(1, 3 - i // 2))

    def draw_right(self, s):
        r = pygame.Rect(1008, 52, 264, 480)
        pygame.draw.rect(s, PANEL, r)
        pygame.draw.rect(s, LINE, r, 1)
        self.text(s, "内存版", (r.x + 12, r.y + 8), TEXT, self.font16)
        loaded = len(self.memory_cards)
        damaged = sum(1 for c in self.memory_cards if c.damaged)
        self.text(s, f"LOADED {loaded} · DMG {damaged}", (r.x + 110, r.y + 10),
                  RED if damaged else MUTED, self.mono10)
        gx, gy, cell = r.x + 44, r.y + 32, 22
        for rr in range(8):
            for cc in range(8):
                q = pygame.Rect(gx + cc * cell, gy + rr * cell, cell - 1, cell - 1)
                necro = (cc, rr) in self.necro_cells
                pygame.draw.rect(s, (70, 18, 30) if necro else (12, 19, 27), q)
                pygame.draw.rect(s, (95, 34, 44) if necro else (28, 41, 54), q, 1)
        for card in self.memory_cards:
            col = (120, 32, 44) if card.damaged else card.info["color"]
            for cx, cy in card.cells:
                q = pygame.Rect(gx + cx * cell, gy + cy * cell, cell - 1, cell - 1)
                pygame.draw.rect(s, col, q, 1 if card.damaged else 0)
            brd = pygame.Rect(gx + card.rect.x * cell, gy + card.rect.y * cell,
                              card.rect.w * cell - 1, card.rect.h * cell - 1)
            pygame.draw.rect(s, RED if card.damaged else col, brd, 1)
            self.text(s, card.info["en"][:4], (brd.x + 1, brd.y + 1),
                      (255, 195, 205) if card.damaged else (10, 18, 24), self.mono10)
        for cx, cy in self.necro_cells:
            q = pygame.Rect(gx + cx * cell, gy + cy * cell, cell - 1, cell - 1)
            pygame.draw.line(s, (255, 65, 90), q.topleft, q.bottomright, 2)
            pygame.draw.line(s, (255, 65, 90), q.topright, q.bottomleft, 2)
        # list
        self.list_rect = pygame.Rect(r.x + 10, r.y + 216, r.w - 20, 254)
        self.active_rect = pygame.Rect(r.x + 10, r.y + 232, r.w - 24, 138)
        self.passive_rect = pygame.Rect(r.x + 10, r.y + 388, r.w - 24, 76)
        active = [c for c in self.memory_cards if c.kind == "active" and (not c.damaged or c.break_t > 0.72)]
        passive = [c for c in self.memory_cards if c.kind != "active" and (not c.damaged or c.break_t > 0.72)]
        active = self._card_order(active)
        passive = self._card_order(passive)
        hand_n = sum(1 for c in self.hand if c is not None)
        self.text(s, f"主动 / ACTIVE   HAND {hand_n}/5", (r.x + 12, r.y + 218),
                  (100, 220, 245), self.font11)
        self.active_max, self.active_scroll = self._draw_skill_section(
            s, self.active_rect, active, self.active_scroll, "无主动技能")
        self.text(s, "被动 / PASSIVE", (r.x + 12, r.y + 374), (190, 150, 255), self.font11)
        self.passive_max, self.passive_scroll = self._draw_skill_section(
            s, self.passive_rect, passive, self.passive_scroll, "未装载被动")


    def draw_bottom(self, s):
        pygame.draw.rect(s, (9, 14, 21), (0, 540, W, H - 540))
        pygame.draw.line(s, LINE, (0, 540), (W, 540), 1)
        # selected command panel
        panel = pygame.Rect(12, 550, 438, 152)
        pygame.draw.rect(s, PANEL, panel)
        pygame.draw.rect(s, LINE, panel, 1)
        c = self.selected_char()
        s.blit(c.portrait, (panel.x + 12, panel.y + 12))
        self.text(s, c.name, (panel.x + 82, panel.y + 10), c.color, self.font18)
        self.text(s, f"{c.en} · {c.role}", (panel.x + 82, panel.y + 32), MUTED, self.font11)
        hpbar = pygame.Rect(panel.x + 82, panel.y + 52, 230, 8)
        pygame.draw.rect(s, (28, 20, 27), hpbar)
        pygame.draw.rect(s, c.color, (hpbar.x, hpbar.y, int(hpbar.w * c.hp / c.max_hp), hpbar.h))
        self.text(s, f"HP {int(c.hp)}/{int(c.max_hp)}", (panel.x + 82, panel.y + 64), MUTED, self.mono10)
        ult_txt = "USED" if c.ult_used else f"{int(c.ult_energy)}/100"
        self.text(s, f"ULT {ult_txt}", (panel.x + 248, panel.y + 64),
                  AMBER if c.ult_energy >= 100 or c.ult_used else CYAN, self.mono10)
        # buttons
        self.command_hits = []
        specs = [
            ("skill", "Q", "裂空跃击" if c.cid == "ds" else "书灵修补", c.skill_cd,
             8.0 if c.cid == "ds" else 9.0, c.color),
            ("ult", "W", "蓝鲸现世" if c.cid == "ds" else "同体校订", 0.0, 1.0, AMBER),
        ]
        for i, (kind, key, label, cd, cdmax, col) in enumerate(specs):
            br = pygame.Rect(panel.x + 12 + i * 208, panel.y + 88, 200, 54)
            if kind == "ult":
                ready = c.alive and not c.ult_used and c.ult_energy >= 100
                if c.ult_used:
                    status = "USED"
                elif c.ult_energy >= 100:
                    status = "ENERGY FULL"
                else:
                    status = f"ENERGY {int(c.ult_energy)}/100"
                cd = 1.0 - c.ult_energy / 100.0 if not c.ult_used else 1.0
            else:
                ready = cd <= 0 and c.alive
                status = "READY" if ready else f"CD {cd:.1f}"
            targeting_this = (self.targeting is not None and self.targeting["char"] is c
                              and kind == "skill")
            pygame.draw.rect(s, (19, 37, 50) if ready else (18, 22, 28), br)
            border = (180, 245, 255) if targeting_this else (col if ready else (60, 72, 82))
            pygame.draw.rect(s, border, br, 2 if ready else 1)
            if kind == "ult" and ready:
                # flowing frame for a fully charged ultimate
                for j in range(3):
                    px = br.x + int((self.time * 54 + j * br.w / 3) % br.w)
                    pygame.draw.circle(s, (255, 238, 150), (px, br.y), 2)
                    pygame.draw.circle(s, (255, 210, 100), (px, br.bottom - 1), 2)
            if cd > 0 and c.alive and not ready:
                ratio = max(0.0, min(1.0, cd / cdmax))
                ow = max(0, int(br.w * ratio))
                if ow > 0:
                    ov = pygame.Surface((ow, br.h), pygame.SRCALPHA)
                    ov.fill((132, 142, 152, 92))
                    s.blit(ov, br.topleft)
                    if ow < br.w:
                        pygame.draw.line(s, (170, 182, 194), (br.x + ow, br.y + 2),
                                         (br.x + ow, br.bottom - 2), 1)
            self.text(s, f"[{key}]", (br.x + 8, br.y + 6), col if ready else DIM, self.mono10)
            self.text(s, label, (br.x + 34, br.y + 6), TEXT if ready else DIM, self.font12)
            status_col = ((190, 245, 255) if targeting_this else
                          (GREEN if ready else (255, 210, 100) if kind == "ult" else (120, 80, 80)))
            self.text(s, "选择目标" if targeting_this else status, (br.x + 34, br.y + 27),
                      status_col, self.mono10 if not targeting_this else self.font11)
            self.command_hits.append((kind, br))
        # hand
        slash_idx = self.slash["card"] if self.slash else self.slash_armed
        if slash_idx is not None and 0 <= slash_idx < len(self.hand) and self.hand[slash_idx]:
            card = self.hand[slash_idx]
            info = card.info
            pygame.draw.rect(s, (18, 35, 42), (462, 544, 792, 20))
            pygame.draw.rect(s, (120, 245, 255), (462, 544, 792, 20), 1)
            self.text(s, "滑剪", (470, 548), (150, 245, 255), self.font11)
            hit_n = len(self.slash.get("links", [])) if self.slash else 0
            self.text(s, f"拖动划过引用线 · {info['cn']}：{info['desc']}",
                      (520, 548), TEXT, self.font11)
            cap_txt = " · MAX" if self.slash and self.slash.get("capped") else ""
            self.text(s, (f"命中 {hit_n} 条{cap_txt} · 右键取消" if self.slash
                          else "松开执行 · 右键取消"),
                      (1080, 548), (190, 230, 240), self.font10 if hasattr(self, "font10") else self.font11)
        elif self.card_target is not None and 0 <= self.card_target < len(self.hand) and self.hand[self.card_target]:
            card = self.hand[self.card_target]
            info = card.info
            pygame.draw.rect(s, (35, 31, 14), (462, 544, 792, 20))
            pygame.draw.rect(s, (255, 220, 100), (462, 544, 792, 20), 1)
            self.text(s, "选择目标", (470, 548), (255, 220, 100), self.font11)
            self.text(s, f"选择一个敌人 · {info['cn']}：{info['desc']}", (548, 548),
                      TEXT, self.font11)
            self.text(s, "右键取消", (1170, 548), DIM, self.font10 if hasattr(self, "font10") else self.font11)
        else:
            self.text(s, "手牌 / HAND", (466, 550), MUTED, self.font11)
            self.text(s, "点击卡牌 → 拖动划过引用线", (566, 551), DIM, self.mono10)
        self.hand_hits = []
        for i in range(5):
            cr = pygame.Rect(468 + i * 158, 568, 148, 132)
            card = self.hand[i] if i < len(self.hand) else None
            if card is None:
                pygame.draw.rect(s, (12, 18, 26), cr)
                pygame.draw.rect(s, (32, 44, 56), cr, 1)
                self.text(s, "EMPTY SLOT", (cr.centerx, cr.centery - 8), (48, 64, 78), self.mono10, center=True)
                self.text(s, "CD / REFRESH", (cr.centerx, cr.centery + 12), (40, 54, 66), self.mono10, center=True)
                self.hand_hits.append((i, cr))
                continue
            key = card.key
            info = CARD_INFO[key]
            selected = self.card_target == i
            pygame.draw.rect(s, (14, 25, 34) if not selected else (28, 31, 20), cr)
            pygame.draw.rect(s, (255, 220, 100) if selected else info["color"], cr, 2)
            pygame.draw.rect(s, info["color"], (cr.x, cr.y, cr.w, 3))
            self.text(s, info["cn"] + ("+" * card.plus), (cr.x + 10, cr.y + 12), TEXT, self.font16)
            self.text(s, info["en"], (cr.x + 10, cr.y + 34), info["color"], self.mono10)
            pygame.draw.line(s, (38, 54, 68), (cr.x + 10, cr.y + 54), (cr.right - 10, cr.y + 54), 1)
            self.text(s, info["desc"], (cr.x + 10, cr.y + 66), MUTED, self.font11)
            self.text(s, "CARD", (cr.x + 10, cr.bottom - 22), DIM, self.mono10)
            self.text(s, "已选目标" if selected else "点击选择", (cr.right - 64, cr.bottom - 22),
                      (255, 220, 100) if selected else (62, 84, 100), self.font11)
            self.hand_hits.append((i, cr))
        self.text(s, "点击角色或左侧头像切换 · 点击技能释放 · SPACE 暂停", (12, 706), DIM, self.font10 if hasattr(self, "font10") else self.font11)

    def draw_tooltip(self, s):
        if not self.hover_skill:
            return
        c = self.selected_char()
        kind = self.hover_skill
        if kind == "skill":
            title, desc, cd = ("裂空跃击", "1.8×ATK\n剪断 1 条引用", 8.0) if c.cid == "ds" else ("书灵修补", "治疗 260\n护盾 100 / 4s", 9.0)
        else:
            title, desc, cd = ("蓝鲸现世", "2.2×ATK\n全体剪断 1 条引用", 20.0) if c.cid == "ds" else ("同体校订", "治疗 25% 最大生命\n8 秒伤害分担", 20.0)
        box = pygame.Rect(12, 470, 250, 70)
        pygame.draw.rect(s, (6, 10, 15), box)
        pygame.draw.rect(s, c.color, box, 1)
        self.text(s, title, (box.x + 8, box.y + 7), c.color, self.font12)
        for i, line in enumerate(desc.split("\n")):
            self.text(s, line, (box.x + 8, box.y + 27 + i * 16), MUTED, self.font11)
        self.text(s, f"CD {cd:.0f}s", (box.right - 52, box.y + 7), DIM, self.mono10)

    def draw_cutin(self, s):
        char = self.cutin["char"]
        t = max(0.0, min(CUTIN_TIME, self.cutin["t"]))
        p = 1.0 - t / CUTIN_TIME

        def ease_out(x):
            x = max(0.0, min(1.0, x))
            return 1.0 - (1.0 - x) ** 3

        entry = ease_out(min(1.0, p / 0.40))
        text_e = ease_out(min(1.0, max(0.0, p - 0.04) / 0.36))
        line_e = ease_out(min(1.0, max(0.0, p - 0.10) / 0.34))
        out = max(0.0, min(1.0, t / 0.14))
        exit_dx = int((1.0 - out) * -56)

        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((3, 5, 10, int(218 * min(1.0, p / 0.10) * out)))
        s.blit(overlay, (0, 0))
        # background layer: diagonal speed lines + sliding color slab
        for i in range(-8, 20):
            x = i * 86 + int((1.0 - entry) * -260)
            pygame.draw.line(s, (18, 31, 43), (x, 0), (x + 340, H), 2)
        slab = pygame.Rect(-40 + int((1.0 - entry) * -420), 0, 560, H)
        band = pygame.Surface(slab.size, pygame.SRCALPHA)
        band.fill((*char.color, 18))
        s.blit(band, slab.topleft)
        pygame.draw.line(s, char.color, (slab.right, 120), (slab.right, 500), 2)

        # portrait layer
        shift = int((1.0 - entry) * -430) + exit_dx
        pr = pygame.Rect(180 + shift, 170 + int((1.0 - text_e) * 14), 330, 360)
        pygame.draw.rect(s, (7, 12, 18), (pr.x + 8, pr.y + 8, pr.w, pr.h))
        pygame.draw.rect(s, (12, 21, 31), pr)
        pygame.draw.rect(s, char.color, pr, 2)
        portrait = pygame.transform.scale(char.portrait, (286, 286))
        s.blit(portrait, (pr.centerx - 143, pr.y + 28))
        self.text(s, "PORTRAIT PLACEHOLDER", (pr.centerx, pr.bottom - 20), (63, 83, 98),
                  self.mono10, center=True)

        # decorative layer
        line_x = 580 + int((1.0 - line_e) * 180)
        line_w = max(1, int(520 * line_e))
        pygame.draw.line(s, char.color, (line_x, 218), (line_x + line_w, 218), 2)
        pygame.draw.line(s, (255, 210, 110), (line_x, 420), (line_x + line_w, 420), 2)

        # text layer: staggered slide from the right
        x = 580 + int((1.0 - text_e) * 390)
        self.text(s, f"{char.en} // ULTIMATE", (x, 190 + int((1.0 - text_e) * 8)), char.color, self.mono12)
        self.text(s, self.cutin["name"], (x, 238 + int((1.0 - line_e) * 12)), (240, 252, 255), self.font64)
        self.text(s, "TIME STOP", (x, 320 + int((1.0 - line_e) * 16)), (255, 210, 110), self.font28)
        self.text(s, "全场时停 · 大招动画期间无敌", (x, 360 + int((1.0 - line_e) * 20)), MUTED, self.font12)
        # bottom timer
        pygame.draw.rect(s, (35, 52, 68), (x, 420, 500, 4))
        k = max(0.0, min(1.0, t / CUTIN_TIME))
        pygame.draw.rect(s, char.color, (x, 420, int(500 * k), 4))

    def draw_victory(self, s):
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((4, 8, 10, 170))
        s.blit(overlay, (0, 0))
        r = pygame.Rect(W // 2 - 190, H // 2 - 90, 380, 180)
        pygame.draw.rect(s, (13, 20, 18), r)
        pygame.draw.rect(s, GREEN, r, 2)
        self.text(s, "WAVE CLEAR", (r.centerx, r.y + 26), GREEN, self.font24, center=True)
        self.text(s, "引用节点已全部回收", (r.centerx, r.y + 62), MUTED, self.font14, center=True)
        self.text(s, "点击返回装配" if self.embedded else "点击任意位置重开",
                  (r.centerx, r.y + 94), DIM, self.font11, center=True)
        self.text(s, f"TIME {self.clock_text()}", (r.centerx, r.y + 120), DIM, self.mono10, center=True)

    def draw_defeat(self, s):
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((4, 6, 10, 170))
        s.blit(overlay, (0, 0))
        r = pygame.Rect(W // 2 - 190, H // 2 - 90, 380, 180)
        pygame.draw.rect(s, (13, 18, 26), r)
        pygame.draw.rect(s, RED, r, 2)
        self.text(s, "SYSTEM HALTED", (r.centerx, r.y + 26), RED, self.font24, center=True)
        self.text(s, "两名进程均已死亡", (r.centerx, r.y + 62), MUTED, self.font14, center=True)
        self.text(s, "点击返回装配" if self.embedded else "点击任意位置重开",
                  (r.centerx, r.y + 94), DIM, self.font11, center=True)
        self.text(s, f"TIME {self.clock_text()}   ENEMY DOWN {sum(1 for e in self.enemies if e.dead)}", (r.centerx, r.y + 120),
                  DIM, self.mono10, center=True)

    # ------------------------------------------------------------ input
    def handle_click(self, pos, button=1):
        self.mouse = pos
        if self.cutin:
            return
        if self.slash_armed is not None:
            if button == 3:
                self.slash_armed = None
            elif button == 1 and ARENA.collidepoint(pos):
                self.start_slash(pos)
            else:
                self.slash_armed = None
            return
        if self.slash is not None:
            if button == 3:
                self.cancel_slash()
            return
        if self.card_target is not None:
            if button == 3:
                self.card_target = None
                return
            target = self.enemy_at(pos)
            if target is not None:
                self.use_card(self.card_target, target)
            else:
                self.card_target = None
            return
        if self.targeting:
            if button == 3:
                self.cancel_targeting()
                return
            target = self.pick_target(pos)
            if target is None:
                self.cancel_targeting()
                return
            c = self.targeting["char"]
            self.targeting = None
            c.start_skill(self, target)
            return
        if self.state in ("defeat", "victory"):
            if self.embedded:
                self.exit_to_assembly = True
            else:
                self.reset()
            return
        if button != 1:
            return
        if self.pause_rect.collidepoint(pos):
            self.paused = not self.paused
            self.audio.play("tab")
            return
        if self.speed_rect.collidepoint(pos):
            self.speed = 2.0 if self.speed == 1.0 else 1.0
            self.audio.play("tab")
            return
        for i, r in self.party_hits:
            if r.collidepoint(pos) and i < len(self.chars):
                self.selected = i
                self.audio.play("pick")
                return
        for kind, r in self.command_hits:
            if r.collidepoint(pos):
                self.cast_selected(kind)
                return
        for i, r in self.hand_hits:
            if r.collidepoint(pos):
                self.begin_card(i)
                return
        # field selection
        for i, c in enumerate(self.chars):
            # sprite bounds approximate, shake ignored
            rr = pygame.Rect(c.x - 35, c.y - 82, 70, 88)
            rr.move_ip(ARENA.x, ARENA.y)
            if rr.collidepoint(pos) and c.alive:
                self.selected = i
                self.audio.play("pick")
                return

    def cast_selected(self, kind):
        c = self.selected_char()
        if kind == "skill":
            self.begin_targeting(c)
        else:
            if self.targeting:
                self.cancel_targeting()
            self.card_target = None
            c.start_ult(self)

    def run(self):
        running = True
        while running:
            dt = self.clock.tick(60) / 1000.0
            self.mouse = self.to_logical(pygame.mouse.get_pos())
            self.hover_skill = None
            for i, (kind, r) in enumerate(self.command_hits):
                if r.collidepoint(self.mouse):
                    self.hover_skill = kind
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    running = False
                elif e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_ESCAPE:
                        if self.targeting:
                            self.cancel_targeting()
                        elif self.slash_armed is not None or self.slash is not None:
                            self.cancel_slash()
                        elif self.card_target is not None:
                            self.card_target = None
                        elif self.cutin:
                            pass
                        elif self.embedded:
                            self.exit_to_assembly = True
                        else:
                            running = False
                    elif e.key == pygame.K_SPACE:
                        self.paused = not self.paused
                        self.audio.play("tab")
                    elif e.key == pygame.K_r:
                        self.reset()
                    elif e.key == pygame.K_q:
                        self.cast_selected("skill")
                    elif e.key == pygame.K_w:
                        self.cast_selected("ult")
                    elif e.key in (pygame.K_1, pygame.K_2):
                        self.speed = 1.0 if e.key == pygame.K_1 else 2.0
                    elif e.key == pygame.K_F11:
                        self.windowed = not self.windowed
                        self._set_window()
                elif e.type == pygame.MOUSEMOTION:
                    self.mouse = self.to_logical(e.pos)
                    self.update_slash(self.mouse)
                elif e.type == pygame.MOUSEBUTTONDOWN:
                    self.handle_click(self.to_logical(e.pos), e.button)
                elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
                    if self.slash is not None:
                        self.end_slash(self.to_logical(e.pos))
                elif e.type == pygame.MOUSEWHEEL:
                    if self.active_rect.collidepoint(self.mouse):
                        self.active_scroll = max(0.0, min(self.active_max, self.active_scroll - e.y * 23))
                    elif self.passive_rect.collidepoint(self.mouse):
                        self.passive_scroll = max(0.0, min(self.passive_max, self.passive_scroll - e.y * 23))
            self.update(dt)
            self.present()
            self.frames += 1
            if self.exit_to_assembly:
                break
            if self.shot and self.frames >= 5:
                os.makedirs(os.path.dirname(self.shot) or ".", exist_ok=True)
                pygame.image.save(self.window, self.shot)
                break
        self.result = {
            "necro": sorted(self.necro_cells),
            "damaged": sorted(self.damaged_uids),
            "won": self.state == "victory",
            "hp": {"ds": max(0.0, self.ds.hp), "claude": max(0.0, self.claude.hp)},
            "currency": self.kills_value,
        }
        if not self.embedded:
            pygame.quit()
        return self.result


def main():
    windowed = "--windowed" in sys.argv
    shot = None
    size = None
    if "--shot" in sys.argv:
        shot = sys.argv[sys.argv.index("--shot") + 1]
    if "--size" in sys.argv:
        try:
            ww, hh = sys.argv[sys.argv.index("--size") + 1].lower().split("x")
            size = (int(ww), int(hh))
        except Exception:
            size = None
    Battle(windowed=windowed, shot=shot, size=size).run()


if __name__ == "__main__":
    main()
