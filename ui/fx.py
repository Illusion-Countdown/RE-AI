# -*- coding: utf-8 -*-
"""特效：粒子、飘字、屏幕震动、闪光。

这些是"手感"的全部来源，而且不需要一张图。
"""
import math
import random

import pygame

from ui import theme


class FX:
    def __init__(self):
        self.particles = []     # [x, y, vx, vy, age, life, color, size]
        self.floaters = []      # [x, y, text, color, life]
        self.shake = 0.0
        self.flash = 0.0

    # ---------------- 触发 ----------------

    def burst(self, x, y, color, n=8, speed=180):
        for _ in range(n):
            ang = random.uniform(0, math.tau)
            sp = random.uniform(speed * 0.3, speed)
            self.particles.append([
                x, y,
                math.cos(ang) * sp, math.sin(ang) * sp,
                0.0, 0.45, color, random.randint(2, 5),
            ])

    def floater(self, x, y, txt, color):
        self.floaters.append([x, y, str(txt), color, 0.9])

    def do_shake(self, amount=8.0):
        self.shake = max(self.shake, amount)

    def do_flash(self, amount=0.35):
        self.flash = max(self.flash, amount)

    # ---------------- 更新 ----------------

    def update(self, dt):
        for p in self.particles:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[2] *= 0.92
            p[3] *= 0.92
            p[4] += dt
        self.particles = [p for p in self.particles if p[4] < p[5]]

        for f in self.floaters:
            f[1] -= 40 * dt
            f[4] -= dt
        self.floaters = [f for f in self.floaters if f[4] > 0]

        self.shake = max(0.0, self.shake - dt * 30)
        self.flash = max(0.0, self.flash - dt * 2.2)

    def offset(self):
        if self.shake <= 0.2:
            return 0, 0
        return (random.uniform(-self.shake, self.shake),
                random.uniform(-self.shake, self.shake))

    # ---------------- 绘制 ----------------

    def draw(self, surf):
        for p in self.particles:
            a = 1.0 - p[4] / p[5]
            r = max(1, int(p[7] * a))
            pygame.draw.circle(surf, p[6], (int(p[0]), int(p[1])), r)

        f18 = theme.font(18, True)
        for f in self.floaters:
            a = max(0.0, f[4] / 0.9)
            color = tuple(int(c * (0.55 + 0.45 * a)) for c in f[3])
            img = f18.render(f[2], True, color)
            surf.blit(img, img.get_rect(center=(int(f[0]), int(f[1]))))

    def draw_flash(self, surf):
        if self.flash <= 0:
            return
        overlay = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        overlay.fill((255, 255, 255, int(60 * self.flash)))
        surf.blit(overlay, (0, 0))
