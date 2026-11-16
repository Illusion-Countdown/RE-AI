# -*- coding: utf-8 -*-
import math
import random
import pygame
from memory_run.const import *
from memory_run.core.model import STRONG, WEAK, DANGLING
from memory_run.core.cards import CARD_DEFS, SHAPE_NAMES, RARITY_CN
from memory_run.content import GIRLS
from memory_run.ui.fx import ScreenPost, draw_rings, draw_sparks, draw_floaters
from .render_common import *
from .render_world import WorldMixin
from .render_hud import HudMixin
from .render_hand import HandMixin

class BattleRenderer(WorldMixin, HudMixin, HandMixin):
    def __init__(self):
        self.post = ScreenPost()
        self.post.build(W, H)
        self.pixel_overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        for yy in range(0, H, 3):
            pygame.draw.line(self.pixel_overlay, (0, 0, 0, 55),
                             (0, yy), (W, yy), 1)
        for xx in range(0, W, 4):
            pygame.draw.line(self.pixel_overlay, (0, 0, 0, 28),
                             (xx, 0), (xx, H), 1)
        self.bg = self._make_bg()
        self.world = pygame.Surface((W, H), pygame.SRCALPHA)
        self.hand_rects = []
        self.card_at = None
        self.t = 0.0
        self.last_quality = 100
        self.trail = []

    def _make_bg(self):
        s = pygame.Surface((W, H), pygame.SRCALPHA)
        # 竞技场地板
        pygame.draw.rect(s, (8, 11, 16), ARENA)
        inner = PLAY.inflate(8, 8)
        pygame.draw.rect(s, (6, 8, 12), inner)
        # 网格
        step = 42
        for x in range(PLAY.x, PLAY.right + 1, step):
            pygame.draw.line(s, (16, 22, 30), (x, PLAY.y), (x, PLAY.bottom), 1)
        for y in range(PLAY.y, PLAY.bottom + 1, step):
            pygame.draw.line(s, (16, 22, 30), (PLAY.x, y), (PLAY.right, y), 1)
        # 斜向数据流
        for i in range(-6, 20):
            x = PLAY.x + i * 70
            pygame.draw.line(s, (10, 18, 24), (x, PLAY.y), (x + 170, PLAY.bottom), 1)
        # 边框
        pygame.draw.rect(s, (26, 36, 48), ARENA, 1)
        bracket(s, ARENA.inflate(-8, -8), (36, 52, 68), 22, 2)
        # 四角标记
        for x, y, txt in ((ARENA.x + 14, ARENA.y + 10, "MEM"),
                          (ARENA.right - 14, ARENA.y + 10, "0x00"),
                          (ARENA.x + 14, ARENA.bottom - 10, "REF"),
                          (ARENA.right - 14, ARENA.bottom - 10, "GC")):
            blit_text(s, txt, (x, y), 9, (40, 54, 68), mono=True,
                      anchor="topright" if x > W // 2 else "topleft")
        # 左侧 / 右侧底板
        panel(s, pygame.Rect(0, 72, 248, 714), (10, 13, 19), (24, 32, 43))
        panel(s, pygame.Rect(1308, 78, 292, 704), (10, 13, 19), (24, 32, 43))
        panel(s, pygame.Rect(0, 786, W, 114), (9, 12, 17), (26, 36, 48))
        # 顶栏底
        pygame.draw.rect(s, (8, 10, 15), (0, 0, W, 72))
        pygame.draw.line(s, (30, 42, 56), (0, 71), (W, 71))
        return s

    # ------------------------------------------------------------ 主绘制

    def draw(self, screen, b, mouse, dt=0.0):
        self.t += dt
        self.hand_rects = []
        self.card_at = None
        q = b.quality()
        self.last_quality = q

        self.world.fill((0, 0, 0, 0))
        self.world.blit(self.bg, (0, 0))
        ox, oy = b.fx.offset()
        old_clip = screen.get_clip()
        self.world.set_clip(ARENA)
        self.draw_world(self.world, b, (ox, oy + 12), mouse)
        self.world.set_clip(None)

        # 画质降级：世界先退化，UI 后画，保证文字高清
        band = b.quality_band()
        surf = self.world
        if band >= 1:
            factor = {1: 0.58, 2: 0.30, 3: 0.11}[band]
            size = (max(1, int(W * factor)), max(1, int(H * factor)))
            if band >= 3:
                # 最低画质：最近邻降采样，像素块要肉眼可见
                small = pygame.transform.scale(self.world, size)
            else:
                small = pygame.transform.smoothscale(self.world, size)
            surf = pygame.transform.scale(small, (W, H))
            if band >= 2:
                ov = pygame.Surface((W, H), pygame.SRCALPHA)
                ov.fill((10, 26, 24, 38 if band == 2 else 74))
                surf.blit(ov, (0, 0))
                self._tear(surf, band)
            if band >= 3:
                surf.blit(self.pixel_overlay, (0, 0))
                for _ in range(18):
                    rr = pygame.Rect(random.randint(0, W - 80),
                                     random.randint(ARENA.y, ARENA.bottom - 24),
                                     random.randint(18, 90), random.randint(2, 8))
                    pygame.draw.rect(surf, random.choice(
                        [(20, 40, 38), (8, 16, 20), (40, 30, 20)]), rr)
        screen.blit(surf, (0, 0))
        screen.set_clip(None)

        # 世界屏幕特效（扫描线 / 暗角 / 受击闪）
        self.post.draw(screen, b.fx)

        self.draw_ui(screen, b, mouse)
        self.draw_drag_ghost(screen, b)
        if band >= 1:
            self._quality_note(screen, b, q)

    def draw_drag_ghost(self, screen, b):
        if not getattr(b, "drag_active", False) or not b.aim:
            return
        card = b.aim["card"]
        mx, my = getattr(b, "mouse", pygame.mouse.get_pos())
        r = pygame.Rect(mx - 72, my - 94, 144, 82)
        draw_card(screen, r, card.key, card.up, selected=True, alpha=225)
        blit_text(screen, "松开放下", (r.centerx, r.y - 14), 10,
                  card.color, anchor="center", mono=True)

    def _tear(self, surf, band):
        n = 4 if band == 2 else 10
        for _ in range(n):
            y = random.randint(ARENA.y, ARENA.bottom - 20)
            h = random.randint(2, 10)
            dx = random.randint(-14, 14)
            try:
                strip = surf.subsurface((0, y, W, h)).copy()
                surf.blit(strip, (dx, y))
            except Exception:
                pass

    def _quality_note(self, screen, b, q):
        y = TOPBAR.bottom + 8
        txt = f"画质 {int(q)}%  负载 {len(b.deck.grid.owner) + len(b.deck.grid.dead)}/{b.deck.grid.w * b.deck.grid.h}  工作内存 {b.work_used:.0f}/{b.deck.grid.free_count()}"
        blit_text(screen, txt, (ARENA.right - 12, y), 12, AMBER,
                  mono=True, anchor="topright", shadow=2)

    # ------------------------------------------------------------ 世界
