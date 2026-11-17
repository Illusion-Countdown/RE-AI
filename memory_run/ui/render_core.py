# -*- coding: utf-8 -*-
from .render_deps import *
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
        self.zoom = 1.25
        self.cam = [W / 2, H / 2]
        self._cam_ready = False

    def _make_bg(self):
        """整张屏幕都是战场：没有左右栏，也没有顶栏底板。"""
        s = pygame.Surface((W, H), pygame.SRCALPHA)
        for y in range(0, H, 4):
            k = y / max(1, H - 1)
            s.fill((int(5 + 4 * k), int(8 + 5 * k), int(12 + 7 * k)),
                   (0, y, W, 4))
        # 远处的冷色光，把视线压回中央
        glow(s, W // 2, int(H * 0.46), 520, (24, 64, 78), 0.055)
        glow(s, W // 2, int(H * 0.46), 260, (20, 48, 60), 0.05)
        # 全屏网格
        step = 48
        for x in range(0, W + 1, step):
            pygame.draw.line(s, (14, 22, 30), (x, 0), (x, H), 1)
        for y in range(0, H + 1, step):
            pygame.draw.line(s, (14, 22, 30), (0, y), (W, y), 1)
        # 斜向数据流，只保留很淡的一层
        for i in range(-8, 28):
            x = i * 84
            pygame.draw.line(s, (9, 17, 23), (x, 0), (x + 260, H), 1)
        return s

    # ------------------------------------------------------------ 相机

    def reset_camera(self):
        self._cam_ready = False

    def zoom_by(self, steps):
        self.zoom = clamp(self.zoom + steps * 0.08, 1.0, 2.0)

    def update_camera(self, b, dt):
        vw, vh = W / self.zoom, H / self.zoom
        tx = clamp(b.player_node.x, vw / 2, W - vw / 2)
        ty = clamp(b.player_node.y, vh / 2, H - vh / 2)
        if not self._cam_ready:
            self.cam = [tx, ty]
            self._cam_ready = True
            return
        k = min(1.0, max(0.0, dt) * 7.0)
        self.cam[0] += (tx - self.cam[0]) * k
        self.cam[1] += (ty - self.cam[1]) * k

    def screen_to_world(self, pos):
        vw, vh = W / self.zoom, H / self.zoom
        sx, sy = self.cam[0] - vw / 2, self.cam[1] - vh / 2
        return (sx + pos[0] / self.zoom, sy + pos[1] / self.zoom)

    def world_to_screen(self, pos):
        vw, vh = W / self.zoom, H / self.zoom
        sx, sy = self.cam[0] - vw / 2, self.cam[1] - vh / 2
        return ((pos[0] - sx) * self.zoom, (pos[1] - sy) * self.zoom)

    def _camera_view(self):
        if self.zoom <= 1.001:
            return self.world
        vw, vh = W / self.zoom, H / self.zoom
        sx = clamp(self.cam[0] - vw / 2, 0, max(0, W - vw))
        sy = clamp(self.cam[1] - vh / 2, 0, max(0, H - vh))
        src = pygame.Rect(int(sx), int(sy), max(1, int(vw)), max(1, int(vh)))
        return pygame.transform.smoothscale(self.world.subsurface(src), (W, H))

    # ------------------------------------------------------------ 主绘制

    def draw(self, screen, b, mouse, dt=0.0):
        self.t += dt
        self.hand_rects = []
        self.card_at = None
        q = b.quality()
        self.last_quality = q
        b.screen_mouse = mouse
        self.update_camera(b, dt)
        b.mouse = self.screen_to_world(mouse)
        b.hover_node = b.node_at(*b.mouse)
        b.hover_edge = None if b.hover_node else b.edge_at(*b.mouse)

        self.world.fill((0, 0, 0, 0))
        self.world.blit(self.bg, (0, 0))
        ox, oy = b.fx.offset()
        self.world.set_clip(ARENA)
        self.draw_world(self.world, b, (ox, oy), b.mouse)
        self.world.set_clip(None)

        # 先做视野缩放，再做画质降级；UI 永远最后画，保持清晰
        surf = self._camera_view()
        band = b.quality_band()
        if band >= 1:
            factor = {1: 0.58, 2: 0.30, 3: 0.11}[band]
            size = (max(1, int(W * factor)), max(1, int(H * factor)))
            if band >= 3:
                # 最低画质：最近邻降采样，像素块要肉眼可见
                small = pygame.transform.scale(surf, size)
            else:
                small = pygame.transform.smoothscale(surf, size)
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
                                     random.randint(0, H - 80),
                                     random.randint(18, 90), random.randint(2, 8))
                    pygame.draw.rect(surf, random.choice(
                        [(20, 40, 38), (8, 16, 20), (40, 30, 20)]), rr)
        screen.blit(surf, (0, 0))
        screen.set_clip(None)

        # 世界屏幕特效（扫描线 / 暗角 / 受击闪）
        self.post.draw(screen, b.fx)

        self.draw_ui(screen, b, mouse)
        self.draw_drag_ghost(screen, b)

    def draw_drag_ghost(self, screen, b):
        if not getattr(b, "drag_active", False) or not b.aim:
            return
        card = b.aim["card"]
        mx, my = getattr(b, "screen_mouse", pygame.mouse.get_pos())
        r = pygame.Rect(mx - 72, my - 94, 144, 82)
        draw_card(screen, r, card.key, card.up, selected=True, alpha=225)
        blit_text(screen, "松开放下", (r.centerx, r.y - 14), 10,
                  card.color, anchor="center", mono=True)

    def _tear(self, surf, band):
        n = 4 if band == 2 else 10
        for _ in range(n):
            y = random.randint(0, H - 20)
            h = random.randint(2, 10)
            dx = random.randint(-14, 14)
            try:
                strip = surf.subsurface((0, y, W, h)).copy()
                surf.blit(strip, (dx, y))
            except Exception:
                pass
