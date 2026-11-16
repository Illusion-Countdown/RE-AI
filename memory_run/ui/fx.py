# -*- coding: utf-8 -*-
"""打击感与屏幕特效：震屏、闪白、顿帧、粒子、浮字、冲击环、故障。"""
import math
import random
import pygame
from memory_run.const import *


class Particle:
    __slots__ = ("x", "y", "vx", "vy", "life", "max_life", "color",
                 "size", "drag", "grav", "add", "trail")

    def __init__(self, x, y, vx, vy, life, color, size, drag=2.2, grav=0.0,
                 add=True, trail=False):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.life = life
        self.max_life = life
        self.color = color
        self.size = size
        self.drag = drag
        self.grav = grav
        self.add = add
        self.trail = trail


class Floater:
    __slots__ = ("x", "y", "text", "color", "life", "max_life", "size",
                 "vy", "bold", "mono", "shake")

    def __init__(self, x, y, s, color, size=18, life=1.0, vy=-42,
                 bold=True, mono=False, shake=0.0):
        self.x = x
        self.y = y
        self.text = s
        self.color = color
        self.life = life
        self.max_life = life
        self.size = size
        self.vy = vy
        self.bold = bold
        self.mono = mono
        self.shake = shake


class Ring:
    __slots__ = ("x", "y", "r0", "r1", "life", "max_life", "color", "width", "fill")

    def __init__(self, x, y, r0, r1, life, color, width=3, fill=False):
        self.x = x
        self.y = y
        self.r0 = r0
        self.r1 = r1
        self.life = life
        self.max_life = life
        self.color = color
        self.width = width
        self.fill = fill


class Spark:
    """一条会收缩的斩击轨迹。"""
    __slots__ = ("a", "b", "life", "max_life", "color", "width")

    def __init__(self, a, b, color, life=0.28, width=3):
        self.a = a
        self.b = b
        self.life = life
        self.max_life = life
        self.color = color
        self.width = width


class FX:
    def __init__(self):
        self.shake = 0.0
        self.shake_decay = 6.0
        self.flash_color = (255, 255, 255)
        self.flash = 0.0
        self.flash_decay = 4.0
        self.hitstop = 0.0
        self.parts = []
        self.floaters = []
        self.rings = []
        self.sparks = []
        self.glitch = 0.0
        self.slowmo = 0.0
        self.slow_t = 0.0
        self.slow_scale = 1.0
        self.time = 0.0
        self.vignette_red = 0.0
        self.scan_y = -200.0
        self.scan = 0.0
        self._off = (0, 0)

    # ------------------------------------------------------------ 触发
    def add_shake(self, amount, decay=6.0):
        self.shake = max(self.shake, amount)
        if amount > self.shake:
            self.shake_decay = decay

    def add_flash(self, amount, color=(255, 255, 255), decay=4.0):
        if amount >= self.flash:
            self.flash = amount
            self.flash_color = color
            self.flash_decay = decay

    def add_hitstop(self, t):
        self.hitstop = max(self.hitstop, t)

    def slow(self, scale=0.35, dur=0.45):
        """复用 asymptote 的慢放：只影响战斗世界时间。"""
        self.slow_scale = scale
        self.slow_t = max(self.slow_t, dur)

    def time_scale(self):
        return self.slow_scale if self.slow_t > 0 else 1.0

    def add_glitch(self, amount):
        self.glitch = max(self.glitch, amount)

    def add_parts(self, x, y, color, n=12, speed=220, life=0.5, size=2.4,
                  spread=None, drag=2.4, grav=0.0, add=True):
        for _ in range(n):
            a = random.uniform(0, math.tau) if spread is None else \
                random.uniform(spread[0], spread[1])
            sp = speed * random.uniform(0.35, 1.25)
            self.parts.append(Particle(
                x, y, math.cos(a) * sp, math.sin(a) * sp,
                life * random.uniform(0.55, 1.2), color,
                size * random.uniform(0.6, 1.5), drag, grav, add))

    def add_dir_parts(self, x, y, angle, color, n=10, speed=260, life=0.4,
                      size=2.2, cone=0.6):
        for _ in range(n):
            a = angle + random.uniform(-cone, cone)
            sp = speed * random.uniform(0.3, 1.2)
            self.parts.append(Particle(
                x, y, math.cos(a) * sp, math.sin(a) * sp,
                life * random.uniform(0.5, 1.2), color,
                size * random.uniform(0.5, 1.4), 2.8, 0, True))

    def add_ring(self, x, y, r0, r1, color, life=0.45, width=3, fill=False):
        self.rings.append(Ring(x, y, r0, r1, life, color, width, fill))

    def add_spark(self, a, b, color, life=0.26, width=3):
        self.sparks.append(Spark(a, b, color, life, width))

    def add_text(self, x, y, s, color, size=18, life=1.0, vy=-42, bold=True,
                 mono=False, shake=0.0):
        self.floaters.append(Floater(x, y, s, color, size, life, vy, bold,
                                     mono, shake))

    # ------------------------------------------------------------ 更新
    def update(self, dt):
        self.time += dt
        self.shake = max(0.0, self.shake - self.shake_decay * dt * self.shake
                         - 14.0 * dt)
        self.flash = max(0.0, self.flash - self.flash_decay * dt)
        self.glitch = max(0.0, self.glitch - dt * 1.6)
        self.slowmo = max(0.0, self.slowmo - dt)
        if self.slow_t > 0:
            self.slow_t = max(0.0, self.slow_t - dt)
            if self.slow_t <= 0:
                self.slow_scale = 1.0
        self.vignette_red = max(0.0, self.vignette_red - dt * 1.2)
        self.scan = max(0.0, self.scan - dt * 2.5)

        for p in self.parts:
            p.life -= dt
            d = max(0.0, 1.0 - p.drag * dt)
            p.vx *= d
            p.vy *= d
            p.vy += p.grav * dt
            p.x += p.vx * dt
            p.y += p.vy * dt
        self.parts = [p for p in self.parts if p.life > 0]

        for f in self.floaters:
            f.life -= dt
            f.y += f.vy * dt
            f.vy *= max(0.0, 1 - 2.2 * dt)
        self.floaters = [f for f in self.floaters if f.life > 0]

        for r in self.rings:
            r.life -= dt
        self.rings = [r for r in self.rings if r.life > 0]

        for s in self.sparks:
            s.life -= dt
        self.sparks = [s for s in self.sparks if s.life > 0]

        amp = min(18.0, self.shake)
        if amp > 0.3:
            self._off = (random.uniform(-amp, amp), random.uniform(-amp, amp))
        else:
            self._off = (0, 0)

    def offset(self):
        return self._off

    # ------------------------------------------------------------ 绘制
    def draw_world(self, surf, cam):
        """世界空间特效（会跟着镜头抖动）。"""
        ox, oy = cam
        for p in self.parts:
            a = p.life / p.max_life
            c = p.color
            if p.add:
                glow(surf, p.x + ox, p.y + oy, p.size * 5, c, 0.55 * a)
                pygame.draw.circle(surf, mix(c, WHITE, 0.4 * a),
                                   (int(p.x + ox), int(p.y + oy)),
                                   max(1, int(p.size * (0.4 + a * 1.2))))
            else:
                pygame.draw.circle(surf, c, (int(p.x + ox), int(p.y + oy)),
                                   max(1, int(p.size * a)))


class ScreenPost:
    """全屏后期：闪白、故障切片、暗角、扫描线。"""

    def __init__(self):
        self.scanlines = None
        self.vignette = None

    def build(self, w, h):
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        for y in range(0, h, 4):
            pygame.draw.line(s, (0, 0, 0, 15), (0, y), (w, y))
        self.scanlines = s

        v = pygame.Surface((80, 45), pygame.SRCALPHA)
        for y in range(45):
            for x in range(80):
                dx = abs(x - 39.5) / 40.0
                dy = abs(y - 22) / 23.0
                d = min(1.0, (dx * dx * 0.85 + dy * dy) ** 0.62)
                a = int(112 * (d ** 2.6))
                v.set_at((x, y), (0, 0, 0, a))
        self.vignette = pygame.transform.smoothscale(v, (w, h))

    def draw(self, surf, fx):
        if self.scanlines:
            surf.blit(self.scanlines, (0, 0))
        if fx.vignette_red > 0.01:
            g = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
            g.fill((255, 30, 40, int(70 * min(1.0, fx.vignette_red))))
            surf.blit(g, (0, 0))
        if fx.flash > 0.01:
            a = int(min(1.0, fx.flash) * 210)
            f = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
            f.fill((fx.flash_color[0], fx.flash_color[1], fx.flash_color[2], a))
            surf.blit(f, (0, 0))
        if self.vignette:
            surf.blit(self.vignette, (0, 0))
        if fx.glitch > 0.01:
            self._glitch(surf, fx.glitch)

    def _glitch(self, surf, amt):
        w, h = surf.get_size()
        n = int(2 + amt * 8)
        for _ in range(n):
            yy = random.randint(0, h - 20)
            hh = random.randint(3, 18)
            dx = int(random.uniform(-1, 1) * (6 + 34 * amt))
            try:
                strip = surf.subsurface((0, yy, w, hh)).copy()
                surf.blit(strip, (dx, yy))
                if random.random() < 0.5:
                    edge = surf.subsurface((0, yy, w, 1)).copy()
                    edge.fill((90, 160, 190), special_flags=pygame.BLEND_RGB_ADD)
                    surf.blit(edge, (dx, yy))
            except Exception:
                pass


def draw_floaters(surf, fx, cam=(0, 0)):
    ox, oy = cam
    for f in fx.floaters:
        a = f.life / f.max_life
        alpha = int(255 * min(1.0, a * 1.6))
        pop = 1.0 + (1.0 - min(1.0, a * 2)) * 0.0
        x, y = f.x + ox, f.y + oy
        if f.shake > 0:
            x += random.uniform(-f.shake, f.shake)
            y += random.uniform(-f.shake, f.shake)
        blit_text(surf, f.text, (x, y), int(f.size * pop), f.color,
                  bold=f.bold, mono=f.mono, anchor="center", alpha=alpha,
                  shadow=2)


def draw_rings(surf, fx, cam=(0, 0)):
    ox, oy = cam
    for r in fx.rings:
        t = 1.0 - r.life / r.max_life
        rad = lerp(r.r0, r.r1, ease_out(t))
        a = int(255 * (1 - t) ** 1.2)
        if rad < 1:
            continue
        if r.fill:
            s = pygame.Surface((int(rad * 2) + 2, int(rad * 2) + 2), pygame.SRCALPHA)
            pygame.draw.circle(s, with_alpha(r.color, a // 3),
                               (int(rad) + 1, int(rad) + 1), int(rad))
            surf.blit(s, (r.x + ox - rad, r.y + oy - rad))
        pygame.draw.circle(surf, with_alpha(r.color, a),
                           (int(r.x + ox), int(r.y + oy)), int(rad),
                           max(1, int(r.width * (1 - t) + 1)))
        glow(surf, r.x + ox, r.y + oy, rad * 1.25, r.color, 0.16 * (1 - t))


def draw_sparks(surf, fx, cam=(0, 0)):
    ox, oy = cam
    for s in fx.sparks:
        t = s.life / s.max_life
        a = int(255 * t)
        col = with_alpha(s.color, a)
        ax, ay = s.a[0] + ox, s.a[1] + oy
        bx, by = s.b[0] + ox, s.b[1] + oy
        mx, my = (ax + bx) / 2, (ay + by) / 2
        w = max(1, int(s.width * t))
        pygame.draw.line(surf, col, (ax, ay), (mx, my), w)
        pygame.draw.line(surf, col, (mx, my), (bx, by), w)
        glow(surf, mx, my, 26 * t, s.color, 0.5 * t)
