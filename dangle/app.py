# -*- coding: utf-8 -*-
"""应用入口：状态机、输入、主循环。"""
import argparse
import math
import random
import sys

import pygame

from .const import *
from .content import BODIES, MODULES, ROOMS
from .battle import Battle, Run, set_sfx
from .fx import FX, ScreenPost
from .render import Renderer
from . import screens
from . import audio


class App:
    def __init__(self, fullscreen=True, headless=False):
        pygame.init()
        audio.init()
        set_sfx(audio.play)
        self.headless = headless
        self.fullscreen = fullscreen and not headless
        if headless:
            self.screen = pygame.Surface((W, H))
        else:
            self._make_display()
        pygame.display.set_caption("悬垂 DANGLING")
        self.clock = pygame.time.Clock()
        self.post = ScreenPost()
        self.post.build(W, H)
        self.renderer = Renderer()
        self.renderer.build()
        self.t = 0.0
        self.state = "title"
        self.title_bg = screens.TitleBG()
        self.run = None
        self.battle = None
        self.mouse = (W // 2, H // 2)
        self.body_idx = 0
        self.reward_options = []
        self.reward_idx = 0
        self.pause_idx = 0
        self.paused = False
        self.inp = {"mvx": 0, "mvy": 0, "plan": False, "dash": False}
        self.dash_req = False
        self.toast = ""
        self.toast_t = 0.0
        self.fade = 0.0
        self.msg = ""
        self.msg_t = 0.0
        self.end_wait = 0.0
        self.shake_extra = 0.0
        self.fx = FX()

    # ------------------------------------------------------------ 显示
    def _make_display(self):
        attempts = []
        if self.fullscreen:
            attempts.append(((W, H), pygame.SCALED | pygame.FULLSCREEN, 1))
            attempts.append(((W, H), pygame.SCALED | pygame.FULLSCREEN, 0))
            attempts.append(((W, H), pygame.FULLSCREEN, 0))
        attempts.append(((W, H), pygame.SCALED, 1))
        attempts.append(((W, H), 0, 0))
        last = None
        for size, flags, vsync in attempts:
            try:
                self.screen = pygame.display.set_mode(size, flags, vsync=vsync)
                return
            except Exception as e:      # noqa: BLE001
                last = e
                continue
        raise RuntimeError("无法创建显示窗口: %s" % last)

    def toggle_fullscreen(self):
        if self.headless:
            return
        self.fullscreen = not self.fullscreen
        self._make_display()

    def to_virtual(self, pos):
        return pos

    # ------------------------------------------------------------ 流程
    def start_run(self, idx):
        self.run = Run(BODIES[idx])
        self.run.room_index = 0
        self.battle = Battle(self.run, 0)
        self.state = "play"
        self.fade = 1.0
        self.paused = False
        audio.play("select")

    def next_room(self):
        self.run.room_index += 1
        if self.run.room_index >= len(ROOMS):
            self.state = "victory"
            return
        self.battle = Battle(self.run, self.run.room_index)
        self.state = "play"
        self.paused = False

    def make_rewards(self):
        owned = {m["id"] for m in self.run.modules}
        pool = [m for m in MODULES if m["id"] not in owned]
        if not pool:
            pool = MODULES[:]
        self.reward_options = random.sample(pool, min(3, len(pool)))
        self.reward_idx = 0

    def take_reward(self):
        if self.reward_options:
            self.run.add(self.reward_options[self.reward_idx])
            audio.play("select")

    def sync_run(self):
        b = self.battle
        if not b:
            return
        self.run.score = b.run.score
        self.run.lives = b.lives
        self.run.hp = max(1, int(b.hp))
        self.run.heap = b.heap

    def restart(self):
        self.start_run(BODIES.index(self.run.body) if self.run else self.body_idx)

    # ------------------------------------------------------------ 事件
    def handle_event(self, ev):
        if ev.type == pygame.QUIT:
            return False
        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_F11:
                self.toggle_fullscreen()
                return True
            if ev.key == pygame.K_m:
                muted = audio.toggle_mute()
                self.msg = "静音" if muted else "声音开"
                self.msg_t = 1.6
                return True
        if ev.type == pygame.MOUSEMOTION:
            self.mouse = self.to_virtual(ev.pos)
        if ev.type == pygame.MOUSEBUTTONDOWN:
            self.mouse = self.to_virtual(ev.pos)

        if self.state == "title":
            self.ev_title(ev)
        elif self.state == "body":
            self.ev_body(ev)
        elif self.state == "play":
            self.ev_play(ev)
        elif self.state == "reward":
            self.ev_reward(ev)
        elif self.state in ("gameover", "victory"):
            self.ev_end(ev)
        return True

    def ev_title(self, ev):
        if ev.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                self.quit_game()
                return
            self.state = "body"
            audio.play("ui")

    def ev_body(self, ev):
        if ev.type == pygame.KEYDOWN:
            if ev.key in (pygame.K_LEFT, pygame.K_a):
                self.body_idx = (self.body_idx - 1) % len(BODIES)
                audio.play("ui")
            elif ev.key in (pygame.K_RIGHT, pygame.K_d):
                self.body_idx = (self.body_idx + 1) % len(BODIES)
                audio.play("ui")
            elif ev.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
                self.body_idx = ev.key - pygame.K_1
                self.start_run(self.body_idx)
            elif ev.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
                self.start_run(self.body_idx)
            elif ev.key == pygame.K_ESCAPE:
                self.state = "title"
        elif ev.type == pygame.MOUSEMOTION:
            for i in range(len(BODIES)):
                if screens.body_card_rect(i).collidepoint(self.mouse):
                    if self.body_idx != i:
                        audio.play("ui")
                    self.body_idx = i
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            for i in range(len(BODIES)):
                if screens.body_card_rect(i).collidepoint(self.mouse):
                    self.body_idx = i
                    self.start_run(i)
                    return

    def ev_play(self, ev):
        b = self.battle
        if self.paused:
            self.ev_pause(ev)
            return
        if b is None:
            return
        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_ESCAPE:
                self.paused = True
                self.pause_idx = 0
                audio.play("ui")
                return
            if b.state == "intro" and ev.key in (pygame.K_RETURN, pygame.K_SPACE):
                b.intro_t = 0.0
                return
            if ev.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5):
                if b.cast_menu:
                    idx = ev.key - pygame.K_1
                    if idx in (0, 1):
                        b.action_cast(b.cast_menu["node"], "NULL" if idx == 0 else "INT")
                        b.cast_menu = None
                else:
                    b.choose_tool(ev.key - pygame.K_1)
                return
            if ev.key == pygame.K_r:
                self.use_dead_code()
                return
            if ev.key == pygame.K_f:
                if b.state == "playing":
                    b.write_attack()
                return
            if ev.key == pygame.K_e and b.cast_menu:
                b.cast_menu = None
                return
            if ev.key == pygame.K_LSHIFT or ev.key == pygame.K_RSHIFT:
                self.dash_req = True
                return
        elif ev.type == pygame.MOUSEBUTTONDOWN:
            if b.state != "playing":
                if b.state == "intro":
                    b.intro_t = 0.0
                return
            if ev.button == 1:
                b.on_mouse_down(self.mouse, 1, pygame.key.get_mods())
            elif ev.button == 3:
                if b.cast_menu:
                    b.on_mouse_down(self.mouse, 3, 0)
                else:
                    b.write_attack()
                return
        elif ev.type == pygame.MOUSEBUTTONUP:
            if ev.button == 1 and b.state == "playing":
                b.on_mouse_up(self.mouse, 1)
        elif ev.type == pygame.MOUSEMOTION:
            if b.state == "playing":
                b.on_mouse_move(self.mouse)

    def ev_pause(self, ev):
        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_ESCAPE:
                self.paused = False
                audio.play("ui")
            elif ev.key in (pygame.K_UP, pygame.K_w):
                self.pause_idx = (self.pause_idx - 1) % 4
                audio.play("ui")
            elif ev.key in (pygame.K_DOWN, pygame.K_s):
                self.pause_idx = (self.pause_idx + 1) % 4
                audio.play("ui")
            elif ev.key in (pygame.K_RETURN, pygame.K_SPACE):
                self.pause_choose()
        elif ev.type == pygame.MOUSEMOTION:
            for i in range(4):
                if pygame.Rect(W // 2 - 170, 240 + i * 58, 340, 44).collidepoint(self.mouse):
                    self.pause_idx = i
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            for i in range(4):
                if pygame.Rect(W // 2 - 170, 240 + i * 58, 340, 44).collidepoint(self.mouse):
                    self.pause_idx = i
                    self.pause_choose()
                    break

    def pause_choose(self):
        i = self.pause_idx
        audio.play("select")
        if i == 0:
            self.paused = False
        elif i == 1:
            self.paused = False
            self.start_run(BODIES.index(self.run.body))
        elif i == 2:
            self.paused = False
            self.state = "title"
            self.battle = None
        else:
            self.quit_game()

    def use_dead_code(self):
        b = self.battle
        if b is None or b.state != "playing":
            return
        if not self.run.has("dead_code") or b.dead_code_used:
            if b.state == "playing":
                b.toast("需要模块「死代码消除」")
            return
        b.dead_code_used = True
        for n in b.graph.hostiles():
            n.timers["atk"] = max(n.timers.get("atk", 0), 3.0)
            n.timers["spawn"] = max(n.timers.get("spawn", 0), 3.0)
            n.timers["rebuild"] = max(n.timers.get("rebuild", 0), 3.0)
        b.fx.add_flash(0.14, (160, 170, 190), 8)
        b.fx.add_glitch(0.5)
        b.fx.add_text(b.px, b.py - 50, "DEAD CODE ELIMINATED", DIM, 20, 1.4)
        b.toast("死代码消除：全场停火 3 秒")
        audio.play("meta")

    def ev_reward(self, ev):
        if ev.type == pygame.KEYDOWN:
            if ev.key in (pygame.K_LEFT, pygame.K_a):
                self.reward_idx = (self.reward_idx - 1) % len(self.reward_options)
                audio.play("ui")
            elif ev.key in (pygame.K_RIGHT, pygame.K_d):
                self.reward_idx = (self.reward_idx + 1) % len(self.reward_options)
                audio.play("ui")
            elif ev.key in (pygame.K_RETURN, pygame.K_SPACE):
                self.take_reward()
                self.next_room()
            elif ev.key in (pygame.K_1, pygame.K_2, pygame.K_3):
                idx = ev.key - pygame.K_1
                if idx < len(self.reward_options):
                    self.reward_idx = idx
                    self.take_reward()
                    self.next_room()
        elif ev.type == pygame.MOUSEMOTION:
            for i in range(len(self.reward_options)):
                if screens.reward_card_rect(i, len(self.reward_options)).collidepoint(self.mouse):
                    self.reward_idx = i
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            for i in range(len(self.reward_options)):
                if screens.reward_card_rect(i, len(self.reward_options)).collidepoint(self.mouse):
                    self.reward_idx = i
                    self.take_reward()
                    self.next_room()
                    break

    def ev_end(self, ev):
        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_r:
                self.start_run(self.body_idx)
            elif ev.key == pygame.K_ESCAPE:
                self.state = "title"
                self.battle = None
            elif ev.key in (pygame.K_RETURN, pygame.K_SPACE) and self.state == "victory":
                self.state = "title"
                self.battle = None
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            if self.state == "victory" and pygame.Rect(W // 2 - 170, 760, 340, 44).collidepoint(self.mouse):
                self.state = "title"

    def quit_game(self):
        pygame.quit()
        sys.exit(0)

    # ------------------------------------------------------------ 更新
    def update(self, dt):
        self.t += dt
        if self.msg_t > 0:
            self.msg_t -= dt
        if self.fade > 0:
            self.fade = max(0.0, self.fade - dt * 3.2)
        if self.state == "title":
            self.title_bg.update(dt)
            self.fx.update(dt)
        elif self.state == "body":
            self.fx.update(dt)
        elif self.state == "reward":
            self.fx.update(dt)
        elif self.state == "play":
            self.update_play(dt)
        elif self.state in ("gameover", "victory"):
            self.fx.update(dt)

    def update_play(self, dt):
        b = self.battle
        if b is None:
            return
        self.sync_run()
        keys = pygame.key.get_pressed()
        mvx = (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT])
        mvy = (keys[pygame.K_s] or keys[pygame.K_DOWN]) - (keys[pygame.K_w] or keys[pygame.K_UP])
        self.inp = {
            "mvx": float(mvx), "mvy": float(mvy),
            "plan": bool(keys[pygame.K_SPACE]),
            "dash": self.dash_req,
        }
        self.dash_req = False
        b.mouse = self.mouse
        if self.paused:
            return
        if b.state in ("playing", "intro", "clear", "dead", "victory"):
            b.update(dt, self.inp)
            if b.mouse != self.mouse:
                b.mouse = self.mouse
            # 鼠标悬停（键盘移动时也要更新）
            if b.state == "playing" and not b.drag and not b.slash:
                b.hover_node = b.node_at(self.mouse[0], self.mouse[1])
                b.hover_edge = (b.graph.edge_at(self.mouse[0], self.mouse[1], 13)
                                if not b.hover_node else None)
        self.sync_run()
        if b.state == "done":
            # 清关 -> 奖励
            self.run.hp = min(self.run.max_hp, int(b.hp + self.run.max_hp * 0.25))
            for m in b.run.modules:
                pass
            self.state = "reward"
            self.make_rewards()
            self.fade = 0.6
        elif b.state == "dead":
            self.end_wait += dt
            if self.end_wait > 1.6:
                self.state = "gameover"
                self.end_wait = 0.0
        elif b.state == "victory":
            self.end_wait += dt
            if self.end_wait > 2.4:
                self.state = "victory"
                self.end_wait = 0.0

    # ------------------------------------------------------------ 绘制
    def draw(self):
        if self.state != "play":
            self._set_cursor_visible(True)
        if self.state == "title":
            screens.draw_title(self.screen, self)
            self.post.draw(self.screen, self.fx)
        elif self.state == "body":
            screens.draw_body_select(self.screen, self)
            self.post.draw(self.screen, self.fx)
        elif self.state == "play":
            self.draw_play()
        elif self.state == "reward":
            screens.draw_reward(self.screen, self)
            self.post.draw(self.screen, self.fx)
        elif self.state == "gameover":
            screens.draw_gameover(self.screen, self, self.t)
            self.post.draw(self.screen, self.fx)
        elif self.state == "victory":
            screens.draw_victory(self.screen, self, self.t)
            self.post.draw(self.screen, self.fx)
        self.draw_global_overlay()

    def draw_play(self):
        b = self.battle
        if b is None:
            return
        self.renderer.draw(self.screen, b, self.mouse)
        self.post.draw(self.screen, b.fx)
        if self.paused:
            screens.draw_pause(self.screen, self)
        else:
            self.renderer.draw_cursor(self.screen, b)
        self._set_cursor_visible(self.paused)

    def _set_cursor_visible(self, vis):
        if self.headless:
            return
        if getattr(self, "_cur_vis", None) != vis:
            pygame.mouse.set_visible(vis)
            self._cur_vis = vis

    def draw_global_overlay(self):
        if self.msg_t > 0:
            s = pygame.Surface((W, 34), pygame.SRCALPHA)
            s.fill((0, 0, 0, 160))
            self.screen.blit(s, (0, H // 2 - 17))
            blit_text(self.screen, self.msg, (W // 2, H // 2), 16, WHITE,
                      anchor="center", bold=True)
        if self.fade > 0:
            s = pygame.Surface((W, H), pygame.SRCALPHA)
            s.fill((0, 0, 0, int(255 * min(1.0, self.fade))))
            self.screen.blit(s, (0, 0))

    # ------------------------------------------------------------ 主循环
    def run_loop(self):
        running = True
        while running:
            dt = self.clock.tick(60) / 1000.0
            dt = min(dt, 1 / 20)
            for ev in pygame.event.get():
                if not self.handle_event(ev):
                    running = False
                    break
            self.update(dt)
            self.draw()
            pygame.display.flip()
        pygame.quit()


def main(argv=None):
    ap = argparse.ArgumentParser(description="悬垂 DANGLING")
    ap.add_argument("--windowed", action="store_true", help="窗口模式")
    ap.add_argument("--room", type=int, default=0, help="从第 N 关开始（0-8）")
    ap.add_argument("--body", type=str, default=None, help="list/array/hash/tree")
    ap.add_argument("--shots", action="store_true", help="无头渲染截图")
    args = ap.parse_args(argv)

    if args.shots:
        from .shotter import run_shots
        run_shots(args)
        return

    app = App(fullscreen=not args.windowed)
    if args.body or args.room:
        idx = 0
        if args.body:
            for i, b in enumerate(BODIES):
                if b["id"] == args.body:
                    idx = i
        app.body_idx = idx
        app.start_run(idx)
        if args.room > 0:
            app.run.room_index = args.room
            app.battle = Battle(app.run, min(args.room, len(ROOMS) - 1))
    app.run_loop()
