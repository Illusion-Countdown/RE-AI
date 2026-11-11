"""Scene 基类。"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

if TYPE_CHECKING:
    from app import App


class Scene:
    def __init__(self, app: "App") -> None:
        self.app = app

    def handle_event(self, event: pygame.event.Event) -> None:
        pass

    def update(self, dt: float) -> None:
        pass

    def draw(self, surface: pygame.Surface) -> None:
        pass
