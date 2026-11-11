# -*- coding: utf-8 -*-
"""战斗场景：实时战斗 + 拖卡 + 内存块 HUD。"""
import pygame

import config
from config import DT as FIXED_DT
from core import actions, battle, cards
from core.state import card_shape
from data import CARDS, ENEMIES
from ui import draw, theme
from ui.fx import FX

DURATION = {"combat": 25.0, "elite": 35.0, "boss": 60.0}
SPAWN = {"combat": ["bug"] * 10 + ["beast"],
         "elite": ["bug"] * 8 + ["beast"] * 3,
         "boss": ["bug"] * 4}

CARD_W, CARD_H = 96, 84


class BattleScreen:
    def __init__(self, app):
        self.app = app
        self.state = app.state
        self.fx = FX()

        self.node_type = self.state.map.node_type(self.state.map.head)
        self.duration = DURATION.get(self.node_type, 25.0)
        self.t = 0.0
        self.spawn_timer = 0.0
        self.paused = False
        self.done = False

        self.drag = None          # 正在拖的卡
        self.drag_pos = (0, 0)
        self.hand_rects = {}

        if self.node_type == "boss":
            battle.spawn_enemy(self.state, "beast", hp_mult=12, size_mult=2.2)
            self.state.log("Boss 出现：它由你欠下的债构成")

    # ---------------------------------------------------------------- 输入

    def handle(self, e):
        if e.type == pygame.KEYDOWN:
            if e.key in (pygame.K_SPACE,):
                self.paused = not self.paused
            elif e.key == pygame.K_c:
                err = actions.commit(self.state)
                if err:
                    self.fx.floater(640, 240, err, theme.WARN)
                else:
                    self.fx.do_shake(12)
                    self.fx.do_flash(0.5)
            return

        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            for cid, rect in self.hand_rects.items():
                if rect.collidepoint(e.pos):
                    self.drag = cid
                    self.drag_pos = e.pos
                    return

        elif e.type == pygame.MOUSEMOTION and self.drag:
            self.drag_pos = e.pos

        elif e.type == pygame.MOUSEBUTTONUP and e.button == 1 and self.drag:
            self._release(e.pos)
            self.drag = None

    def _release(self, pos):
        p = self.state.player
        if battle.dist(pos[0], pos[1], p.x, p.y) <= p.radius + 46:
            ok = cards.cast(self.state, self.drag)
            if ok:
                self.fx.burst(p.x, p.y, theme.CARD, 10)
                self.fx.do_shake(4)
            else:
                self.fx.floater(p.x, p.y - 40, "不能施放", theme.WARN)
        else:
            self.fx.floater(pos[0], pos[1], "拖到角色头上", theme.MUTED)

    # ---------------------------------------------------------------- 更新

    def update(self, dt):
        if self.paused or self.done:
            return

        st = self.state
        self.t += dt

        # 移动：WASD
        keys = pygame.key.get_pressed()
        dx = (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT])
        dy = (keys[pygame.K_s] or keys[pygame.K_DOWN]) - (keys[pygame.K_w] or keys[pygame.K_UP])
        st.move = (dx, dy)

        # 刷怪
        self.spawn_timer -= dt
        if self.spawn_timer <= 0 and self.t < self.duration - 6:
            self.spawn_timer = max(0.45, 1.3 - self.t * 0.015)
            kinds = SPAWN.get(self.node_type, ["bug"])
            import random
            battle.spawn_enemy(st, random.choice(kinds))

        battle.update(st, dt)
        cards.update(st, dt)
        self.fx.update(dt)
        self._consume_events()

        if st.player_down:
            self.done = True
            self.app.goto_result(False)
            return

        if self.t >= self.duration:
            self.done = True
            st.enemies.clear()
            st.bullets.clear()
            if self.node_type == "boss":
                actions.finish_node(st)
                self.app.goto_result(st.win)
            else:
                self.app.goto_reward()

    def _consume_events(self):
        for ev in self.state.pop_events():
            t = ev["type"]
            if t == "damage":
                e = next((x for x in self.state.enemies if x.uid == ev["uid"]), None)
                if e:
                    self.fx.floater(e.x, e.y - 20, f"-{ev['value']:g}", theme.TEXT)
                    self.fx.burst(e.x, e.y, theme.ENEMY, 4, 120)
            elif t == "hurt":
                self.fx.do_shake(6)
                self.fx.floater(self.state.player.x, self.state.player.y - 30,
                                f"-{ev['value']:g}", theme.DANGER)
            elif t == "commit":
                self.fx.do_shake(14)
                self.fx.do_flash(0.6)
                self.fx.floater(640, 200, f"COMMIT  ×{ev['count']}", theme.ACCENT)
            elif t == "memory_smash":
                self.fx.do_shake(8)
                self.fx.do_flash(0.25)
            elif t == "boss_summon":
                self.fx.floater(640, 160, "Boss 召唤了新的 Bug", theme.ELITE)

    # ---------------------------------------------------------------- 绘制

    def draw(self, screen):
        screen.fill(theme.BG)
        ox, oy = self.fx.offset()
        layer = pygame.Surface(screen.get_size(), pygame.SRCALPHA)

        self._draw_arena(layer, ox, oy)
        self._draw_entities(layer, ox, oy)
        screen.blit(layer, (0, 0))

        self._draw_hud(screen)
        self._draw_boss_bar(screen)
        self._draw_hand(screen)
        self._draw_drag(screen)
        self.fx.draw(screen)
        self.fx.draw_flash(screen)

        if self.paused:
            overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 140))
            screen.blit(overlay, (0, 0))
            draw.text(screen, "暂停（空格继续）", 36, theme.TEXT,
                      (config.WIDTH // 2, config.HEIGHT // 2), "center", True)

    def _draw_arena(self, surf, ox, oy):
        x, y, w, h = config.ARENA
        rect = pygame.Rect(x + ox, y + oy, w, h)
        pygame.draw.rect(surf, (15, 19, 26), rect, border_radius=10)
        pygame.draw.rect(surf, theme.LINE, rect, 1, border_radius=10)

        for gx in range(x, x + w + 1, 80):
            pygame.draw.line(surf, (22, 28, 36), (gx + ox, y + oy), (gx + ox, y + h + oy))
        for gy in range(y, y + h + 1, 80):
            pygame.draw.line(surf, (22, 28, 36), (x + ox, gy + oy), (x + w + ox, gy + oy))

    def _draw_entities(self, surf, ox, oy):
        st = self.state

        for d in st.drops:
            color = theme.PURPLE if d.kind == "swap" else theme.CARD
            r = pygame.Rect(0, 0, 16, 16)
            r.center = (d.x + ox, d.y + oy)
            pygame.draw.rect(surf, color, r, border_radius=3)

        for b in st.bullets:
            pygame.draw.circle(surf, theme.BULLET, (int(b.x + ox), int(b.y + oy)), int(b.radius))

        for e in st.enemies:
            if not e.alive:
                continue
            color = theme.ELITE if e.radius > 20 else theme.ENEMY
            if e.slow_timer > 0:
                color = theme.PURPLE
            draw.circle(surf, (e.x + ox, e.y + oy), e.radius, color)
            draw.ring(surf, (e.x + ox, e.y + oy), e.radius, (0, 0, 0))
            # 血条：先画深底，再画红色，否则看起来像一条浮空的红线
            ratio = e.hp / e.max_hp if e.max_hp else 0
            bw = e.radius * 2
            bar_rect = pygame.Rect(e.x - bw / 2 + ox, e.y - e.radius - 12 + oy, bw, 5)
            pygame.draw.rect(surf, (30, 20, 22), bar_rect, border_radius=2)
            draw.bar(surf, bar_rect, ratio, theme.DANGER)
            if e.marked:
                draw.ring(surf, (e.x + ox, e.y + oy), e.radius + 5, theme.CARD, 2)

        p = st.player
        draw.circle(surf, (p.x + ox, p.y + oy), p.radius, theme.PLAYER)
        draw.ring(surf, (p.x + ox, p.y + oy), p.radius, (230, 245, 255), 2)
        draw.ring(surf, (p.x + ox, p.y + oy), p.radius + 5, (60, 120, 180), 1)
        rr = 30 if st.invuln > 0 else 24
        draw.ring(surf, (p.x + ox, p.y + oy), rr, (30, 60, 90), 2)

    def _draw_hud(self, screen):
        st = self.state
        p = st.player

        # 血条
        draw.bar(screen, pygame.Rect(60, 20, 300, 14), p.hp / p.max_hp, theme.DANGER)
        draw.text(screen, f"{int(p.hp)}/{int(p.max_hp)}", 15, theme.TEXT, (368, 27), "midleft")

        # 名额 / 腐化
        draw.text(screen, f"名额 {st.quota}", 18, theme.ACCENT, (600, 22), "midleft", True)
        draw.text(screen, f"腐化 {st.corruption:.0%}", 18, theme.WARN, (720, 22), "midleft", True)
        draw.text(screen, f"击杀 {st.kills}", 18, theme.MUTED, (880, 22), "midleft")

        # 剩余时间
        left = max(0.0, self.duration - self.t)
        draw.text(screen, f"{left:4.1f}s", 18, theme.MUTED, (1170, 22), "midright")

        self._draw_memory(screen)

    def _draw_memory(self, screen):
        mem = self.state.memory
        cell = 34
        x0, y0 = 1050, 70
        draw.panel(screen, pygame.Rect(x0 - 12, y0 - 34, cell * mem.w + 24, cell * mem.h + 60))
        draw.text(screen, "内存块", 16, theme.MUTED, (x0, y0 - 26), "topleft", True)

        for gy in range(mem.h):
            for gx in range(mem.w):
                rect = pygame.Rect(x0 + gx * cell, y0 + gy * cell, cell - 2, cell - 2)
                v = mem.grid[gy][gx]
                if v == "BROKEN":
                    pygame.draw.rect(screen, (40, 24, 26), rect, border_radius=3)
                    pygame.draw.line(screen, theme.DANGER, rect.topleft, rect.bottomright, 1)
                elif v is None:
                    pygame.draw.rect(screen, (18, 22, 28), rect, border_radius=3)
                    pygame.draw.rect(screen, theme.LINE, rect, 1, border_radius=3)
                else:
                    disabled = v in mem.disabled
                    color = (60, 62, 70) if disabled else theme.CARD
                    pygame.draw.rect(screen, color, rect, border_radius=3)
                    draw.text(screen, CARDS[v]["name"][:1], 14,
                              (20, 20, 20) if not disabled else theme.MUTED,
                              rect.center, "center", True)

        st = mem.stats()
        draw.text(screen, f"{st['used']}/{st['total']}  碎 {st['broken']}", 14,
                  theme.MUTED, (x0, y0 + cell * mem.h + 8))

    def _draw_boss_bar(self, screen):
        boss = next((e for e in self.state.enemies if e.special == "boss" and e.alive), None)
        if boss is None:
            return

        w, h = 640, 18
        rect = pygame.Rect(config.WIDTH // 2 - w // 2, 52, w, h)
        pygame.draw.rect(screen, (30, 16, 18), rect, border_radius=6)
        ratio = boss.hp / boss.max_hp if boss.max_hp else 0
        draw.bar(screen, rect, ratio, theme.ELITE)
        pygame.draw.rect(screen, theme.LINE, rect, 1, border_radius=6)

        draw.text(screen, f"Boss · 阶段 {boss.phase}", 15, theme.ELITE,
                  (rect.centerx, rect.y - 14), "center", True)
        draw.text(screen, f"{int(boss.hp)} / {int(boss.max_hp)}", 13, theme.MUTED,
                  (rect.centerx, rect.bottom + 12), "center")

    def _draw_hand(self, screen):
        st = self.state
        self.hand_rects = {}
        n = len(st.hand)
        if n == 0:
            draw.text(screen, "（手牌为空）", 16, theme.MUTED, (640, 660), "center")
            return

        total_w = n * (CARD_W + 10)
        x = config.WIDTH // 2 - total_w // 2
        y = 610

        for i, cid in enumerate(st.hand):
            rect = pygame.Rect(x + i * (CARD_W + 10), y, CARD_W, CARD_H)
            self.hand_rects[cid] = rect

            card = CARDS[cid]
            hover = rect.collidepoint(pygame.mouse.get_pos())
            draw.panel(screen, rect, (40, 36, 22) if hover else (28, 26, 20),
                       theme.CARD if hover else (90, 76, 40))

            draw.text(screen, card["name"], 15, theme.CARD,
                      (rect.centerx, rect.y + 22), "center", True)
            draw.text(screen, f"{card['cells']} 格 / CD {card['cd']:g}s", 12,
                      theme.MUTED, (rect.centerx, rect.y + 46), "center")
            draw.text(screen, f"[{i + 1}]", 12, theme.MUTED,
                      (rect.right - 8, rect.bottom - 6), "bottomright")

    def _draw_drag(self, screen):
        if not self.drag:
            return
        card = CARDS[self.drag]
        rect = pygame.Rect(0, 0, CARD_W, CARD_H)
        rect.center = self.drag_pos
        draw.panel(screen, rect, (44, 40, 24), theme.CARD)
        draw.text(screen, card["name"], 15, theme.CARD, (rect.centerx, rect.y + 22),
                  "center", True)

        p = self.state.player
        in_range = battle.dist(self.drag_pos[0], self.drag_pos[1], p.x, p.y) <= p.radius + 46
        if in_range:
            draw.ring(screen, (p.x, p.y), p.radius + 40, theme.OK, 3)
