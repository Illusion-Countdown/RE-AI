# -*- coding: utf-8 -*-
"""《悬垂：内存远征》主循环与状态机。"""
import argparse
import math
import os
import sys
import traceback

import pygame

from memory_run.const import *
from memory_run.platform import audio
from memory_run.core.cards import CARD_DEFS
from memory_run.content import TUTORIAL_COUNT, RUN_ROOMS
from memory_run.ui.fx import FX
from memory_run.run.runstate import RunState
from memory_run.battle.battle import Battle
from memory_run.ui.deckui import DeckEditor
from memory_run.ui.render import BattleRenderer
from memory_run.ui.screens import (
    draw_title, draw_help, draw_pause, draw_reward, draw_end,
    draw_tutorial_clear, draw_tutorial_end, button, draw_title_bg, draw_shop,
)

TITLE = "悬垂：内存远征  DANGLING RUN"


class App:
    def __init__(self, fullscreen=True, headless=False):
        self.headless = headless
        if headless:
            os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
            os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        # 512 样本 @44.1k ≈ 11.6ms：兼容性与延迟的折中
        pygame.mixer.pre_init(44100, -16, 2, 512)
        pygame.init()
        pygame.display.set_caption(TITLE)
        flags = pygame.SCALED
        if fullscreen and not headless:
            flags |= pygame.FULLSCREEN
        try:
            self.screen = pygame.display.set_mode((W, H), flags)
        except Exception:
            self.screen = pygame.display.set_mode((W, H))
        self.fullscreen = fullscreen and not headless
        self.audio_ok = audio.init()
        audio.play("gcstart", 0.38, gap=0)
        self.clock = pygame.time.Clock()
        self.t = 0.0
        self.state = "title"
        self.body_id = "tree"
        self.run = None
        self.battle = None
        self.editor = None
        self.renderer = BattleRenderer()
        self.ui = {}
        self.result = None
        self.reward_options = []
        self.choice_mode = "card"
        self.pending_boss = False
        self.pending_module = False
        self.safehouse = False
        self.shop_items = []
        self.shop_from = "deck"
        self.prep_context = "initial"
        self.death_reason = ""
        self._finished_handled = False
        self.help_from = "title"
        self.notice = ""
        self.notice_t = 0.0
        if not self.audio_ok:
            self.notice = "音频设备不可用；画面与操作不受影响"
            self.notice_t = 4.0
        self.shot_mode = False
        self.card_press = None

    # ================================================================ 流程
    def new_run(self, tutorial=False):
        self.run = RunState(tutorial=tutorial, body_id=self.body_id)
        self.safehouse = False
        self.prep_context = "initial"
        self.state = "deck"
        self.editor = DeckEditor(self.run)
        self.editor.say("开始前：确认空闲格 ≥ 3；战斗从整个卡组抽牌，未入网格的卡在 BENCH。")

    def start_battle(self):
        if not self.run or not self.run.room:
            self.end_run(True)
            return
        self.run.begin_room()
        self.battle = Battle(self.run, FX())
        self.renderer.reset_camera()
        self.state = "battle"
        self._finished_handled = False
        self.result = None
        self.safehouse = False
        self.card_press = None
        audio.play("gcstart", 0.7)

    def end_run(self, victory):
        self.run.victory = victory
        self.run.ended = True
        self.battle = None
        self.state = "end"
        audio.play("win" if victory else "death")

    def on_battle_finished(self):
        if self._finished_handled or not self.battle:
            return
        self._finished_handled = True
        self.card_press = None
        b = self.battle
        res = b.result or {}
        if res.get("cleared"):
            self.run.hp = max(1, int(b.hp))
            if self.run.tutorial:
                self.state = "tutorial_clear"
                self.battle = None
                return
            self.result = res
            self.pending_boss = bool(self.run.room.get("boss"))
            self.pending_module = (not self.pending_boss and
                                   self.run.rooms_cleared % 2 == 0)
            self.reward_options = self.run.make_card_rewards(
                3, rare=bool(res.get("perfect")))
            self.choice_mode = "card"
            self.state = "reward"
            self.battle = None
        else:
            self.death_reason = b.ending or "hp"
            self.run.refs -= 1
            self.battle = None
            if self.run.refs <= 0:
                self.end_run(False)
            else:
                self.state = "retry"

    def retry(self):
        self.run.restore_room_snapshot()
        self.run.hp = max(20, int(self.run.body["hp"] * 0.55))
        self.start_battle()

    def finish_room(self, skip_safehouse=False):
        was_boss = self.pending_boss
        self.run.advance()
        if self.run.room is None:
            self.end_run(True)
            return
        if was_boss and not skip_safehouse:
            self.safehouse = True
            self.state = "deck"
            self.editor = DeckEditor(self.run)
            self.prep_context = "initial"
            self.editor.say("安全屋：修坏死格、拖同名卡免费 ++、重排网格、进商店。")
            audio.play("clear")
        else:
            self.start_battle()

    def choose_card(self, idx):
        if idx < 0:
            self.notice = "跳过奖励（不获得碎片）"
        else:
            key = self.reward_options[idx]
            card = self.run.add_card(key)
            if card.anchor:
                self.notice = f"{CARD_DEFS[key]['cn']} 已放进网格"
            else:
                self.notice = f"{CARD_DEFS[key]['cn']} 放不下，进入仓库（安全屋可换）"
            audio.play("meta")
        if self.pending_boss:
            self.choice_mode = "rule"
            self.reward_options = self.run.make_rule_rewards()
            self.state = "rule"
        elif self.pending_module:
            self.choice_mode = "module"
            self.reward_options = self.run.make_module_rewards()
            self.state = "module"
        else:
            self.open_prep("postreward", "奖励已入库：先整备，再继续下一关。")
            self.notice = "整备后点「开始战斗」继续"

    def choose_module(self, idx):
        self.run.add_module(self.reward_options[idx])
        audio.play("alias")
        self.open_prep("postreward", "增幅已安装：整备后继续。")

    def choose_rule(self, idx):
        self.run.add_rule(self.reward_options[idx])
        audio.play("meta")
        self.open_prep("postreward", "Boss 规则已生效：整备后继续。")

    def tutorial_next(self):
        if self.run.step + 1 >= TUTORIAL_COUNT:
            self.state = "tutorial_end"
        else:
            self.run.advance()
            self.start_battle()

    def enter_main_run(self):
        self.run.tutorial = False
        self.run.tutorial_done = True
        self.run.step = TUTORIAL_COUNT
        self.run.hp = self.run.body["hp"]
        self.run.refs = 3
        self.run.shards += 1
        self.run.deck.add("ECC")
        self.state = "deck"
        self.editor = DeckEditor(self.run)
        self.editor.say("教程奖励：纠错码 ×1，碎片 +1。调整卡组后出发。")

    # ================================================================ 输入
    def handle_event(self, ev):
        if ev.type == pygame.QUIT:
            self.quit()
        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_F11:
                self.toggle_fullscreen()
                return
            if ev.key == pygame.K_m:
                muted = audio.toggle_mute()
                self.notice = "静音" if muted else "声音已开"
                self.notice_t = 1.2
                return
            if ev.key == pygame.K_F2:
                audio.play("win", 0.8, gap=0)
                self.notice = "音频测试：应听到上行和弦"
                self.notice_t = 1.5
                return
            if ev.key == pygame.K_F3:
                name = audio.next_device()
                self.audio_ok = bool(name)
                self.notice = f"音频输出：{name}" if name else "没有可切换的音频设备"
                self.notice_t = 2.0
                if name:
                    audio.play("select", 0.7, gap=0)
                return
        if self.state == "title":
            self.ev_title(ev)
        elif self.state == "help":
            self.ev_help(ev)
        elif self.state == "deck":
            self.ev_deck(ev)
        elif self.state == "shop":
            self.ev_shop(ev)
        elif self.state == "battle":
            self.ev_battle(ev)
        elif self.state == "pause":
            self.ev_pause(ev)
        elif self.state == "reward":
            self.ev_choice(ev, "card")
        elif self.state == "module":
            self.ev_choice(ev, "module")
        elif self.state == "rule":
            self.ev_choice(ev, "rule")
        elif self.state == "retry":
            self.ev_retry(ev)
        elif self.state == "tutorial_clear":
            self.ev_tutorial_clear(ev)
        elif self.state == "tutorial_end":
            self.ev_tutorial_end(ev)
        elif self.state == "end":
            self.ev_end(ev)

    def _hit(self, pos):
        for key, rect in self.ui.items():
            if hasattr(rect, "collidepoint") and rect.collidepoint(pos):
                return key
        return None

    def ev_title(self, ev):
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            k = self._hit(ev.pos)
            audio.play("ui")
            if k == "start":
                self.new_run(False)
            elif k == "tutorial":
                self.new_run(True)
            elif k == "help":
                self.help_from = "title"
                self.state = "help"
            elif k == "quit":
                self.quit()
            elif k and k.startswith("body_"):
                self.body_id = k[5:]

    def ev_help(self, ev):
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            if self._hit(ev.pos) == "back":
                audio.play("ui")
                self.state = self.help_from
        elif ev.type == pygame.KEYDOWN and ev.key in (pygame.K_ESCAPE, pygame.K_SPACE):
            self.state = self.help_from

    def ev_deck(self, ev):
        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_ESCAPE:
                if self.editor.held:
                    self.editor.key(ev.key)
                elif self.prep_context == "reward":
                    self.prep_context = "initial"
                    self.state = "reward"
                elif self.prep_context == "postreward":
                    self.deck_start()
                elif self.safehouse:
                    self.state = "title"
                else:
                    self.state = "title"
                return
            self.editor.key(ev.key)
            return
        if ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
            if self.editor.held is not None:
                self.editor.release(ev.pos)
            return
        if ev.type == pygame.MOUSEBUTTONDOWN:
            k = self._hit(ev.pos)
            if k == "start":
                self.deck_start()
                return
            if k == "auto":
                self.editor.auto_arrange()
                return
            if k == "repair":
                n = self.run.repair_dead(1, 2)
                self.editor.say(f"修复 {n} 格" if n else "碎片不足或没有坏死格")
                return
            if k == "shop":
                self.shop_from = "deck"
                self.shop_items = self.run.make_shop_items()
                self.state = "shop"
                return
            if k == "upgrade":
                self.editor.say("拖动一张同名基础卡到另一张上即可免费升级 ++")
                return
            if k == "back":
                if self.prep_context == "reward":
                    self.prep_context = "initial"
                    self.state = "reward"
                elif self.prep_context == "postreward":
                    self.deck_start()
                else:
                    self.state = "title"
                return
            if ev.button in (1, 3):
                self.editor.click(ev.pos, ev.button)

    def enter_shop(self, from_state="deck"):
        self.shop_from = from_state
        self.shop_items = self.run.make_shop_items()
        self.state = "shop"

    def ev_shop(self, ev):
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
            self.state = self.shop_from
            return
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            k = self._hit(ev.pos)
            if k == "back":
                self.state = self.shop_from
                return
            if isinstance(k, int) and 0 <= k < len(self.shop_items):
                ok, msg = self.run.buy_shop_item(self.shop_items[k])
                self.notice = msg
                if ok:
                    self.shop_items.pop(k)
                    audio.play("win")
                else:
                    audio.play("weak")

    def open_prep(self, context, msg=""):
        self.prep_context = context
        self.safehouse = context != "initial"
        self.state = "deck"
        self.editor = DeckEditor(self.run)
        self.editor.say(msg or "整备：拖卡入网格、同名卡互拖免费升级、修坏死格、进商店。")

    def deck_start(self):
        d = self.run.deck
        if d.grid.free_count() < 1:
            self.editor.say("网格已经塞满：至少留 1 个空闲格当工作内存。")
            return
        if not any(c.anchor for c in d.cards):
            self.editor.say("网格里没有可抽的卡。")
            return
        audio.play("gcstart")
        if self.prep_context == "reward":
            self.prep_context = "initial"
            self.state = "reward"
            return
        if self.prep_context == "postreward":
            self.prep_context = "initial"
            self.finish_room(skip_safehouse=True)
            return
        self.start_battle()

    def deck_upgrade(self):
        self.editor.say("升级不花碎片：把一张同名基础卡拖到另一张上，松手即 ++。")

    def ev_battle(self, ev):
        b = self.battle
        if b is None:
            return
        if ev.type == pygame.MOUSEWHEEL:
            self.renderer.zoom_by(ev.y)
            return
        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_ESCAPE:
                self.state = "pause"
                return
            b.on_key(ev.key, pygame.key.get_mods())
        elif ev.type == pygame.MOUSEMOTION:
            b.screen_mouse = ev.pos
            b.on_mouse_move(self.renderer.screen_to_world(ev.pos))
            if self.card_press is not None:
                sx, sy = self.card_press["pos"]
                if abs(ev.pos[0] - sx) + abs(ev.pos[1] - sy) > 8:
                    self.card_press["moved"] = True
        elif ev.type == pygame.MOUSEBUTTONDOWN:
            if ev.button in (4, 5):
                self.renderer.zoom_by(1 if ev.button == 4 else -1)
                return
            b.screen_mouse = ev.pos
            world = self.renderer.screen_to_world(ev.pos)
            # 按住手牌：先预览，松开时再决定是点击还是拖拽
            for rect, where, card in self.renderer.hand_rects:
                if ev.button == 1 and card is not None and rect.collidepoint(ev.pos):
                    kind, idx = where
                    self.card_press = {"where": kind, "idx": idx or 0,
                                       "card": card, "pos": ev.pos,
                                       "moved": False}
                    b.preview_card(kind, idx or 0)
                    audio.play("ui")
                    return
            if ev.button == 3:
                self.card_press = None
                b.aim = None
                b.drag_active = False
            b.on_mouse_down(world, ev.button, pygame.key.get_mods())
        elif ev.type == pygame.MOUSEBUTTONUP:
            b.screen_mouse = ev.pos
            world = self.renderer.screen_to_world(ev.pos)
            if self.card_press is not None:
                press = self.card_press
                self.card_press = None
                b.drag_active = False
                if press["moved"]:
                    over_hand = any(r.collidepoint(ev.pos)
                                    for r, _w, _c in self.renderer.hand_rects)
                    if over_hand or BOTTOM.collidepoint(ev.pos):
                        b.aim = None
                    else:
                        b.drop_card_at(world)
                else:
                    b.aim = None
                    b.select_where(press["where"], press["idx"], immediate=True)
                return
            b.on_mouse_up(world, ev.button, pygame.key.get_mods())

    def ev_pause(self, ev):
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
            self.state = "battle"
            return
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            k = self._hit(ev.pos)
            audio.play("ui")
            if k == "resume":
                self.state = "battle"
            elif k == "help":
                self.help_from = "pause"
                self.state = "help"
            elif k == "abandon":
                self.run.refs = 0
                self.end_run(False)

    def ev_choice(self, ev, mode):
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            if "deck" in self.ui and self.ui["deck"].collidepoint(ev.pos):
                self.open_prep("reward", "奖励前整备：可调整卡组、修格、进商店；完成后返回奖励。")
                return
            if mode == "card":
                for i, rect in enumerate(self.ui.get("options", [])):
                    if rect.collidepoint(ev.pos):
                        self.choose_card(i)
                        return
                if "skip" in self.ui and self.ui["skip"].collidepoint(ev.pos):
                    self.choose_card(-1)
                    return
            else:
                for i, rect in enumerate(self.ui.get("options", [])):
                    if rect.collidepoint(ev.pos):
                        if mode == "module":
                            self.choose_module(i)
                        else:
                            self.choose_rule(i)
                        return

    def ev_retry(self, ev):
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            k = self._hit(ev.pos)
            if k == "retry":
                audio.play("ui")
                self.retry()
            elif k == "giveup":
                self.run.refs = 0
                self.end_run(False)

    def ev_tutorial_clear(self, ev):
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            if self._hit(ev.pos) == "next":
                audio.play("ui")
                self.tutorial_next()

    def ev_tutorial_end(self, ev):
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            k = self._hit(ev.pos)
            if k == "run":
                audio.play("gcstart")
                self.enter_main_run()
            elif k == "title":
                self.state = "title"

    def ev_end(self, ev):
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            k = self._hit(ev.pos)
            if k == "again":
                self.new_run(False)
            elif k == "title":
                self.state = "title"

    # ================================================================ 更新
    def update(self, dt):
        self.t += dt
        if self.notice_t > 0:
            self.notice_t -= dt
        if self.state == "battle" and self.battle:
            b = self.battle
            if not (b.state == "playing" and b.fx.hitstop > 0):
                b.fx.update(dt)
            inp = self.make_input()
            b.update(dt, inp)
            if b.finished:
                self.on_battle_finished()
        elif self.state == "pause" and self.battle:
            pass

    def make_input(self):
        keys = pygame.key.get_pressed()
        mvx = (1 if keys[pygame.K_d] or keys[pygame.K_RIGHT] else 0) - \
              (1 if keys[pygame.K_a] or keys[pygame.K_LEFT] else 0)
        mvy = (1 if keys[pygame.K_s] or keys[pygame.K_DOWN] else 0) - \
              (1 if keys[pygame.K_w] or keys[pygame.K_UP] else 0)
        dash = keys[pygame.K_e]
        plan = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
        return {"mvx": mvx, "mvy": mvy, "dash": dash,
                "plan": plan, "mouse": pygame.mouse.get_pos()}

    # ================================================================ 绘制
    def draw(self):
        self.screen.fill((6, 8, 12))
        if self.state == "title":
            self.ui = draw_title(self.screen, self.t, self.body_id)
        elif self.state == "help":
            self.ui = draw_help(self.screen)
        elif self.state == "deck":
            self.draw_deck()
        elif self.state == "shop":
            raw = draw_shop(self.screen, self.run, self.shop_items)
            self.ui = {"back": raw["back"]}
            for i, r in enumerate(raw["items"]):
                self.ui[i] = r
        elif self.state == "battle":
            self.draw_battle()
        elif self.state == "pause":
            self.draw_battle()
            self.ui = draw_pause(self.screen, self.t)
        elif self.state in ("reward", "module", "rule"):
            self.ui = draw_reward(self.screen, self.run, self.result,
                                  self.reward_options, self.choice_mode)
        elif self.state == "retry":
            self.draw_retry()
        elif self.state == "tutorial_clear":
            self.ui = draw_tutorial_clear(self.screen, self.run)
        elif self.state == "tutorial_end":
            self.ui = draw_tutorial_end(self.screen)
        elif self.state == "end":
            self.ui = draw_end(self.screen, self.run, self.run.victory, self.t)
        self.draw_notice()
        if audio.is_muted():
            blit_text(self.screen, "MUTED · 按 M 恢复声音", (W // 2, H - 6), 9,
                      AMBER, anchor="midbottom", mono=True)
        elif not self.audio_ok:
            blit_text(self.screen, "NO AUDIO · 按 F2 测试设备", (W // 2, H - 6),
                      9, RED, anchor="midbottom", mono=True)
        pygame.display.flip()

    def draw_deck(self):
        self.editor.draw(self.screen, self.t)
        # 顶部状态条
        blit_text(self.screen, "SAFEHOUSE" if self.safehouse else "PREPARATION",
                  (W - 30, 26), 10, DIM, mono=True, anchor="topright")
        blit_text(self.screen, f"STEP {self.run.step + 1:02d}/{TUTORIAL_COUNT + len(RUN_ROOMS)}   "
                               f"HP {self.run.hp}/{self.run.max_hp}   "
                               f"REF {self.run.refs}   SHARDS {self.run.shards}",
                  (W - 30, 44), 12, WHITE, mono=True, anchor="topright")
        blit_text(self.screen, f"{self.run.zone_name}",
                  (W - 30, 62), 10, CYAN, anchor="topright")
        self.ui = dict(self.editor.buttons)

    def draw_battle(self):
        mouse = pygame.mouse.get_pos()
        self.renderer.draw(self.screen, self.battle, mouse, 1 / 60)
        if self.notice_t > 0:
            tab = pygame.Rect(W // 2 - 180, 80, 360, 28)
            panel(self.screen, tab, (10, 14, 20), (50, 66, 82), 4, alpha=210)
            blit_text(self.screen, self.notice, (W // 2, 94), 12, WHITE,
                      anchor="center")

    def draw_retry(self):
        screen = self.screen
        screen.fill((7, 9, 13))
        draw_title_bg(screen, self.t)
        panel(screen, pygame.Rect(380, 190, 840, 480), (9, 12, 18),
              (44, 60, 76), 8)
        reason = {"hp": "进程崩溃", "render": "渲染崩溃",
                  "necro": "内存崩坏", "alias": "别名池死亡",
                  "self": "自毁"}.get(self.death_reason, "进程终止")
        blit_text(screen, reason, (W // 2, 240), 42, RED, bold=True,
                  anchor="center")
        blit_text(screen, f"REF 快照回滚：剩余 {self.run.refs} 次",
                  (W // 2, 300), 18, WHITE, anchor="center")
        blit_text(screen, "本次房间的坏死格和已用卡会重置；网格与模块保留。",
                  (W // 2, 336), 13, DIM, anchor="center")
        if self.death_reason == "render":
            blit_text(screen, "提示：修坏死格、删卡、扩格都会让画质回升。",
                      (W // 2, 366), 13, AMBER, anchor="center")
        if self.death_reason == "necro":
            blit_text(screen, "提示：坏死格 ≥50% 会直接结束本局；ECC 和安全屋能修。",
                      (W // 2, 366), 13, AMBER, anchor="center")
        self.ui = {
            "retry": button(screen, (540, 430, 250, 52), "重试本房", CYAN, size=18),
            "giveup": button(screen, (810, 430, 250, 52), "放弃本局", RED, size=16),
        }

    def draw_notice(self):
        if self.notice_t > 0 and self.notice:
            panel(self.screen, pygame.Rect(W // 2 - 300, H - 44, 600, 30),
                  (10, 14, 20), (50, 66, 82), 4, alpha=220)
            blit_text(self.screen, self.notice, (W // 2, H - 29), 13, WHITE,
                      anchor="center")

    # ================================================================ 杂项
    def toggle_fullscreen(self):
        if self.headless:
            return
        self.fullscreen = not self.fullscreen
        flags = pygame.SCALED | (pygame.FULLSCREEN if self.fullscreen else 0)
        try:
            self.screen = pygame.display.set_mode((W, H), flags)
        except Exception:
            self.screen = pygame.display.set_mode((W, H))

    def quit(self):
        pygame.quit()
        sys.exit(0)

    def run_loop(self):
        while True:
            dt = min(0.05, self.clock.tick(60) / 1000.0)
            for ev in pygame.event.get():
                self.handle_event(ev)
            self.update(dt)
            self.draw()

    # ================================================================ 截图
    def make_shots(self, outdir):
        os.makedirs(outdir, exist_ok=True)
        self.state = "title"
        self.draw()
        pygame.image.save(self.screen, os.path.join(outdir, "01_title.png"))
        self.run = RunState(tutorial=False, body_id="tree")
        self.state = "deck"
        self.editor = DeckEditor(self.run)
        self.draw()
        pygame.image.save(self.screen, os.path.join(outdir, "02_deck.png"))
        self.start_battle()
        for _ in range(170):
            self.battle.fx.update(1 / 60)
            self.battle.update(1 / 60, {"mvx": 0, "mvy": 0,
                                        "mouse": (W // 2, 300)})
        self.draw()
        pygame.image.save(self.screen, os.path.join(outdir, "03_battle.png"))
        # 直接跳到奖励画面
        self.run.complete_room(True, 86, 0, 0, 80)
        self.result = self.run.last_room
        self.pending_boss = False
        self.pending_module = False
        self.reward_options = self.run.make_card_rewards(3, rare=True)
        self.choice_mode = "card"
        self.state = "reward"
        self.draw()
        pygame.image.save(self.screen, os.path.join(outdir, "04_reward.png"))
        self.state = "end"
        self.run.victory = True
        self.draw()
        pygame.image.save(self.screen, os.path.join(outdir, "05_end.png"))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--windowed", action="store_true")
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--shots", action="store_true")
    args = ap.parse_args(argv)
    app = App(fullscreen=not args.windowed, headless=args.headless)
    if args.shots:
        app.make_shots(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))), "screenshots"))
        pygame.quit()
        return
    try:
        app.run_loop()
    except SystemExit:
        raise
    except BaseException:
        tb = traceback.format_exc()
        try:
            with open(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
                    os.path.abspath(__file__)))), "crash.log"),
                    "w", encoding="utf-8") as fh:
                fh.write(tb)
        except Exception:
            pass
        print(tb)
        try:
            pygame.quit()
        except Exception:
            pass
        raise


if __name__ == "__main__":
    main()
