"""RUNTIME 4.0 demo：全屏/窗口、逻辑画布、场景切换。"""

from __future__ import annotations

import pygame

import settings
from core.content import Content
from ui.widgets import draw_scanlines


_MOUSE_EVENTS = {pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP}


class App:
    def __init__(self) -> None:
        pygame.display.init()
        pygame.font.init()
        pygame.key.set_repeat(0)
        self.logical = pygame.Surface((settings.WIDTH, settings.HEIGHT))
        self.fullscreen = bool(settings.FULLSCREEN_DEFAULT)
        self.screen = None
        self.view_scale = 1.0
        self.view_offset = (0, 0)
        self._create_screen(pygame.FULLSCREEN if self.fullscreen else 0)
        pygame.display.set_caption(settings.CAPTION)
        self.clock = pygame.time.Clock()
        self.content = Content(settings.DATA_DIR)
        self.run = None
        self.scene = None
        self.input_lock = 0.0
        self.running = True
        self._start_boot()

    def _create_screen(self, flags: int) -> None:
        try:
            size = (0, 0) if self.fullscreen else (settings.WIDTH, settings.HEIGHT)
            self.screen = pygame.display.set_mode(size, flags)
            self.fullscreen = bool(flags & pygame.FULLSCREEN)
        except pygame.error:
            self.fullscreen = False
            self.screen = pygame.display.set_mode((settings.WIDTH, settings.HEIGHT))
        self._recalc_view()

    def _recalc_view(self) -> None:
        if self.screen is None:
            self.view_scale = 1.0
            self.view_offset = (0, 0)
            return
        sw, sh = self.screen.get_size()
        self.view_scale = min(sw / settings.WIDTH, sh / settings.HEIGHT)
        w = int(settings.WIDTH * self.view_scale)
        h = int(settings.HEIGHT * self.view_scale)
        self.view_offset = ((sw - w) // 2, (sh - h) // 2)

    def toggle_fullscreen(self) -> None:
        self.fullscreen = not self.fullscreen
        self._create_screen(pygame.FULLSCREEN if self.fullscreen else 0)
        pygame.display.set_caption(settings.CAPTION)
        self.input_lock = 0.15

    def to_logical(self, pos: tuple[int, int]) -> tuple[int, int] | None:
        x = (pos[0] - self.view_offset[0]) / max(0.0001, self.view_scale)
        y = (pos[1] - self.view_offset[1]) / max(0.0001, self.view_scale)
        if 0 <= x < settings.WIDTH and 0 <= y < settings.HEIGHT:
            return int(x), int(y)
        return None

    def _map_event(self, event: pygame.event.Event) -> pygame.event.Event | None:
        if event.type not in _MOUSE_EVENTS:
            return event
        pos = self.to_logical(event.pos)
        if pos is None:
            return None
        data = dict(event.dict)
        data["pos"] = pos
        return pygame.event.Event(event.type, data)

    def present(self) -> None:
        if self.screen is None:
            return
        sw, sh = self.screen.get_size()
        w = int(settings.WIDTH * self.view_scale)
        h = int(settings.HEIGHT * self.view_scale)
        self.screen.fill((0, 0, 0))
        if (w, h) == (settings.WIDTH, settings.HEIGHT) and self.view_scale == 1.0:
            self.screen.blit(self.logical, self.view_offset)
        else:
            scaled = pygame.transform.smoothscale(self.logical, (w, h))
            self.screen.blit(scaled, self.view_offset)
        pygame.display.flip()

    def switch_to(self, scene) -> None:
        self.scene = scene
        self.input_lock = 0.12

    def _start_boot(self) -> None:
        from scenes.boot import BootScene

        self.run = None
        self.switch_to(BootScene(self))

    def start_game(self) -> None:
        from scenes.game import GameScene

        self.run = self.content.make_run()
        self.switch_to(GameScene(self))

    def quit(self) -> None:
        self.running = False

    def _draw_frame(self) -> None:
        self.logical.fill(settings.BG)
        if self.scene is not None:
            self.scene.draw(self.logical)
        draw_scanlines(self.logical)
        self.present()

    def loop(self) -> None:
        while self.running:
            dt = self.clock.tick(settings.FPS) / 1000.0
            self.input_lock = max(0.0, self.input_lock - dt)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    break
                if event.type == pygame.KEYDOWN and (
                    event.key == pygame.K_F11
                    or (event.key == pygame.K_RETURN and bool(event.mod & pygame.KMOD_ALT))
                ):
                    self.toggle_fullscreen()
                    continue
                if self.scene is not None and self.input_lock <= 0:
                    mapped = self._map_event(event)
                    if mapped is not None:
                        self.scene.handle_event(mapped)
            if not self.running:
                break
            if self.scene is not None:
                self.scene.update(dt)
            self._draw_frame()
        pygame.quit()
