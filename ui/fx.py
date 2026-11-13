"""运行时视觉特效：光束、飘字、粒子、波次横幅、核心受击闪光。

core 只产生 fx_events；这里只读事件，不碰游戏状态。
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

import pygame

import settings
from ui.hexview import HexView
from ui.widgets import get_font, panel


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    max_life: float
    color: tuple[int, int, int]
    size: float
    gravity: float = 0.0


@dataclass
class FloatText:
    text: str
    x: float
    y: float
    color: tuple[int, int, int]
    life: float
    max_life: float
    size: int = 15


@dataclass
class Beam:
    start: tuple[float, float]
    end: tuple[float, float]
    color: tuple[int, int, int]
    life: float
    max_life: float
    width: float = 2.0


@dataclass
class Ring:
    x: float
    y: float
    color: tuple[int, int, int]
    life: float
    max_life: float
    radius: float
    width: int = 2


@dataclass
class Banner:
    title: str
    subtitle: str
    color: tuple[int, int, int]
    life: float
    max_life: float
    size: int = 30


class FXManager:
    def __init__(self, view: HexView) -> None:
        self.view = view
        self.particles: list[Particle] = []
        self.floats: list[FloatText] = []
        self.beams: list[Beam] = []
        self.rings: list[Ring] = []
        self.banners: list[Banner] = []
        self.flash_color = (0, 0, 0)
        self.flash_alpha = 0.0
        self.flash_life = 0.0
        self.flash_max = 1.0
        self.shake = 0.0
        self.shake_max = 0.0
        self.time = 0.0
        self._rng = random.Random(4404)

    # ------------------------------------------------------------------
    def clear(self) -> None:
        self.particles.clear()
        self.floats.clear()
        self.beams.clear()
        self.rings.clear()
        self.banners.clear()
        self.flash_alpha = 0.0
        self.shake = 0.0

    def center(self, cell) -> tuple[float, float]:
        if cell is None:
            return (640.0, 200.0)
        return self.view.cell_center(cell[0], cell[1])

    def _burst(self, cell, color, count: int = 10, speed: float = 90.0, size: float = 2.4) -> None:
        x, y = self.center(cell)
        for _ in range(count):
            angle = self._rng.uniform(0, math.tau)
            velocity = self._rng.uniform(speed * 0.35, speed)
            life = self._rng.uniform(0.28, 0.62)
            self.particles.append(
                Particle(
                    x=x, y=y,
                    vx=math.cos(angle) * velocity,
                    vy=math.sin(angle) * velocity,
                    life=life, max_life=life,
                    color=color,
                    size=self._rng.uniform(size * 0.6, size),
                    gravity=self._rng.uniform(10, 55),
                )
            )

    def _float(self, text: str, cell, color, size: int = 15, life: float = 0.75) -> None:
        x, y = self.center(cell)
        self.floats.append(
            FloatText(str(text), x + self._rng.uniform(-8, 8), y - 14, color, life, life, size)
        )

    def _banner(self, title: str, subtitle: str, color, life: float = 2.0, size: int = 30) -> None:
        self.banners = [Banner(title, subtitle, color, life, life, size)]

    def _flash(self, color, alpha: float, life: float = 0.35) -> None:
        self.flash_color = color
        self.flash_alpha = max(self.flash_alpha, alpha)
        self.flash_life = life
        self.flash_max = life

    def _shake(self, amount: float, life: float = 0.35) -> None:
        self.shake = max(self.shake, amount)
        self.shake_max = max(self.shake_max, life)

    # ------------------------------------------------------------------
    def spawn(self, events: list[dict]) -> None:
        for event in events:
            kind = event.get("kind", "")
            cell = event.get("cell")
            if kind == "wave":
                wave = int(event.get("wave", 1))
                total = int(event.get("total", 3))
                self._banner(f"第 {wave} / {total} 波", "外部写入正在进入内存", settings.CYAN, 2.2, 34)
                self._flash((20, 60, 90), 45, 0.3)
            elif kind == "boss_start":
                self._banner("首领战 · 生产环境", "灰度发布 / 全量发布 / 熔断", settings.RED, 2.6, 30)
                self._flash((90, 20, 40), 55, 0.4)
            elif kind == "spawn":
                self._burst(cell, settings.RED, 7, 55, 2.0)
                self.rings.append(Ring(*self.center(cell), settings.RED, 0.5, 0.5, 8, 1))
            elif kind == "beam":
                start = self.center(event.get("source"))
                end = self.center(event.get("target"))
                color = tuple(event.get("color", (80, 170, 255)))
                self.beams.append(Beam(start, end, color, 0.16, 0.16, 2.2))
            elif kind == "enemy_hit":
                amount = float(event.get("amount", 0))
                self._float(f"-{amount:.0f}", cell, settings.AMBER if amount < 20 else settings.RED, 14)
                self._burst(cell, (245, 158, 11), 5, 75, 1.7)
            elif kind == "enemy_death":
                self._burst(cell, settings.RED, 16, 120, 2.8)
                self._float("清除", cell, settings.RED, 13, 0.65)
                self.rings.append(Ring(*self.center(cell), settings.RED, 0.45, 0.45, 10, 2))
            elif kind == "piece_hit":
                self._float(f"-{float(event.get('amount', 0)):.0f}", cell, settings.RED, 13, 0.6)
                self._burst(cell, settings.RED, 5, 55, 1.6)
            elif kind == "piece_death":
                self._burst(cell, (255, 80, 80), 18, 130, 3.0)
                self._float("进程终止", cell, settings.RED, 13, 0.8)
                self._shake(5, 0.25)
            elif kind == "core_hit":
                self._flash((255, 36, 36), 85, 0.28)
                self._shake(7, 0.3)
                self._float(f"核心 -{event.get('amount', 4)}", (0, 0), settings.RED, 18, 1.0)
                self.rings.append(Ring(*self.center((0, 0)), settings.RED, 0.55, 0.55, 20, 3))
            elif kind == "boss_hit":
                self._float(f"-{float(event.get('amount', 0)):.0f}", (0, 0), settings.RED, 16, 0.55)
                self._burst((0, 0), settings.RED, 3, 60, 2.0)
            elif kind == "boss_phase":
                name = str(event.get("name", "阶段"))
                phase = int(event.get("phase", 2))
                self._banner(f"阶段 {phase} · {name}", "生产环境正在改变规则", settings.RED, 2.4, 31)
                self._flash((100, 20, 110), 70, 0.4)
                self._shake(6, 0.3)
            elif kind == "boss_death":
                self._banner("部署完成", "v1.0 已写入生产环境", settings.GREEN, 3.0, 36)
                self._flash((32, 160, 100), 80, 0.6)
            elif kind == "explosion":
                self._burst(cell, tuple(event.get("color", (255, 120, 80))), 22, 150, 3.2)
                self.rings.append(Ring(*self.center(cell), settings.ORANGE, 0.5, 0.5, 16, 3))
            elif kind == "card":
                name = str(event.get("name", "指令卡"))
                self._banner(f"系统调用 // {name}", "指令已注入运行时", settings.CARD_COLOR, 1.35, 22)
                target = event.get("target")
                if target:
                    self._burst(target, settings.CARD_COLOR, 14, 100, 2.4)
                    self.rings.append(Ring(*self.center(target), settings.CARD_COLOR, 0.5, 0.5, 10, 2))
                self._flash((90, 70, 10), 28, 0.25)
            elif kind == "ultimate":
                self._banner("长思考 · CoT", "6 秒内不再卡顿", settings.CYAN, 2.0, 30)
                self._flash((20, 100, 130), 75, 0.45)
                self._shake(4, 0.3)

    # ------------------------------------------------------------------
    def update(self, dt: float) -> None:
        self.time += dt
        for p in self.particles:
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.vy += p.gravity * dt
            p.life -= dt
        self.particles = [p for p in self.particles if p.life > 0][:240]
        for f in self.floats:
            f.y -= 34 * dt
            f.life -= dt
        self.floats = [f for f in self.floats if f.life > 0][:24]
        for b in self.beams:
            b.life -= dt
        self.beams = [b for b in self.beams if b.life > 0]
        for r in self.rings:
            r.life -= dt
            r.radius += 42 * dt
        self.rings = [r for r in self.rings if r.life > 0]
        for b in self.banners:
            b.life -= dt
        self.banners = [b for b in self.banners if b.life > 0]
        self.flash_life = max(0.0, self.flash_life - dt)
        if self.flash_life <= 0:
            self.flash_alpha = 0.0
        self.shake = max(0.0, self.shake - dt * 28)

    def shake_offset(self) -> tuple[int, int]:
        if self.shake <= 0.2:
            return (0, 0)
        return (self._rng.randint(-int(self.shake), int(self.shake)), self._rng.randint(-int(self.shake), int(self.shake)))

    # ------------------------------------------------------------------
    def draw_world(self, surface: pygame.Surface) -> None:
        for beam in self.beams:
            ratio = max(0.0, beam.life / beam.max_life)
            width = max(1, int(beam.width * (0.5 + ratio)))
            glow = pygame.Surface((settings.WIDTH, settings.HEIGHT), pygame.SRCALPHA)
            pygame.draw.line(glow, (*beam.color, int(70 * ratio)), beam.start, beam.end, width + 5)
            pygame.draw.line(glow, (*beam.color, int(210 * ratio)), beam.start, beam.end, width)
            surface.blit(glow, (0, 0))
        for ring in self.rings:
            ratio = max(0.0, ring.life / ring.max_life)
            if ratio <= 0:
                continue
            glow = pygame.Surface((settings.WIDTH, settings.HEIGHT), pygame.SRCALPHA)
            pygame.draw.circle(glow, (*ring.color, int(150 * ratio)), (int(ring.x), int(ring.y)), int(ring.radius), ring.width)
            surface.blit(glow, (0, 0))
        for particle in self.particles:
            ratio = max(0.0, particle.life / particle.max_life)
            color = tuple(int(channel * (0.45 + ratio * 0.55)) for channel in particle.color)
            pygame.draw.circle(surface, color, (int(particle.x), int(particle.y)), max(1, int(particle.size * ratio + 0.5)))
        for float_text in self.floats:
            ratio = max(0.0, float_text.life / float_text.max_life)
            image = get_font(float_text.size, True).render(float_text.text, True, float_text.color)
            image.set_alpha(int(255 * min(1.0, ratio * 1.8)))
            surface.blit(image, image.get_rect(center=(int(float_text.x), int(float_text.y))))

    def draw_overlay(self, surface: pygame.Surface) -> None:
        if self.flash_alpha > 0:
            ratio = max(0.0, self.flash_life / max(0.001, self.flash_max))
            overlay = pygame.Surface((settings.WIDTH, settings.HEIGHT), pygame.SRCALPHA)
            overlay.fill((*self.flash_color, int(self.flash_alpha * ratio)))
            surface.blit(overlay, (0, 0))
        for banner in self.banners:
            ratio = max(0.0, banner.life / banner.max_life)
            alpha = int(255 * min(1.0, ratio * 2.2))
            y = 112
            center_x = 330
            panel_w = 560
            panel_x = center_x - panel_w // 2
            glow = pygame.Surface((settings.WIDTH, 94), pygame.SRCALPHA)
            pygame.draw.rect(glow, (5, 8, 13, int(210 * min(1.0, ratio * 2))), (panel_x, 0, panel_w, 84), border_radius=10)
            pygame.draw.rect(glow, (*banner.color, int(120 * ratio)), (panel_x, 0, panel_w, 84), width=1, border_radius=10)
            surface.blit(glow, (0, y - 10))
            title = get_font(banner.size, True).render(banner.title, True, banner.color)
            title.set_alpha(alpha)
            surface.blit(title, title.get_rect(center=(center_x, y + 20)))
            subtitle = get_font(12).render(banner.subtitle, True, settings.TEXT)
            subtitle.set_alpha(alpha)
            surface.blit(subtitle, subtitle.get_rect(center=(center_x, y + 52)))
