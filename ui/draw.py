# -*- coding: utf-8 -*-
"""画图小工具。所有界面都用这几个函数拼。"""
import pygame

from ui import theme


def text(surf, s, size, color, pos, anchor="topleft", bold=False):
    f = theme.font(size, bold)
    img = f.render(str(s), True, color)
    rect = img.get_rect()
    setattr(rect, anchor, pos)
    surf.blit(img, rect)
    return rect


def clip(s, size, max_w, bold=False):
    f = theme.font(size, bold)
    s = str(s)
    if f.size(s)[0] <= max_w:
        return s
    while s and f.size(s + "…")[0] > max_w:
        s = s[:-1]
    return s + "…"


def panel(surf, rect, fill=theme.PANEL, border=theme.LINE, radius=8):
    pygame.draw.rect(surf, fill, rect, border_radius=radius)
    pygame.draw.rect(surf, border, rect, 1, border_radius=radius)


def bar(surf, rect, ratio, color, bg=(40, 46, 54)):
    ratio = max(0.0, min(1.0, ratio))
    pygame.draw.rect(surf, bg, rect, border_radius=4)
    w = int(rect.w * ratio)
    if w > 0:
        pygame.draw.rect(surf, color, (rect.x, rect.y, w, rect.h), border_radius=4)


def circle(surf, center, r, color, width=0):
    pygame.draw.circle(surf, color, (int(center[0]), int(center[1])), int(r), width)


def ring(surf, center, r, color, width=3):
    pygame.draw.circle(surf, color, (int(center[0]), int(center[1])), int(r), width)
