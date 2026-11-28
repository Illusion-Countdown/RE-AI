# -*- coding: utf-8 -*-
"""《悬垂》DANGLING —— 常量、调色板、字体与绘制工具。"""
import math
import os
import functools
import pygame

# ---------------------------------------------------------------- 画布
W, H = 1600, 900
FPS = 60

TOPBAR = pygame.Rect(0, 0, W, 72)
LEFTPANEL = pygame.Rect(0, 0, 0, 0)
ARENA = pygame.Rect(0, 0, W, H)
RIGHT = pygame.Rect(0, 0, 0, 0)
BAND = 0                       # 本作不做越界，保留常量兼容
PLAY = pygame.Rect(0, 0, W, H - 140)
BOTTOM = pygame.Rect(0, H - 140, W, 140)

# ---------------------------------------------------------------- 调色
BG          = (7, 9, 13)
BG2         = (10, 13, 19)
PANEL       = (13, 16, 23)
PANEL_HI    = (19, 24, 34)
PANEL_LINE  = (34, 43, 58)
DIM         = (108, 122, 143)
DIM2        = (70, 82, 100)
WHITE       = (232, 240, 250)
CYAN        = (92, 228, 255)
CYAN_D      = (28, 92, 116)
MAGENTA     = (255, 96, 178)
MAGENTA_D   = (104, 30, 74)
AMBER       = (255, 190, 96)
AMBER_D     = (110, 74, 26)
GREEN       = (108, 255, 176)
GREEN_D     = (30, 96, 70)
RED         = (255, 84, 100)
RED_D       = (110, 26, 40)
PURPLE      = (186, 138, 255)
PURPLE_D    = (74, 46, 120)
BLUE        = (110, 160, 255)
TEAL        = (90, 240, 220)
GOLD        = (255, 214, 120)
HULL        = (18, 22, 31)

KIND_COLOR = {
    "PLAYER":    CYAN,
    "MINION":    RED,
    "SENTINEL":  AMBER,
    "CYCLER":    PURPLE,
    "ALLOCATOR": TEAL,
    "ZOMBIE":    (196, 96, 104),
    "BOMB":      GOLD,
    "PYLON":     MAGENTA,
    "CORE":      MAGENTA,
    "ROOT":      (96, 112, 132),
    "LEAK":      (92, 100, 96),
    "HIJACK":    GREEN,
    "LUNGER":    AMBER,
    "EXECUTOR":  GOLD,
}


def dim(c, k):
    return (int(c[0] * k), int(c[1] * k), int(c[2] * k))


def mix(a, b, t):
    t = max(0.0, min(1.0, t))
    return (int(a[0] + (b[0] - a[0]) * t),
            int(a[1] + (b[1] - a[1]) * t),
            int(a[2] + (b[2] - a[2]) * t))


def with_alpha(c, a):
    return (c[0], c[1], c[2], max(0, min(255, int(a))))


# ---------------------------------------------------------------- 数学
def clamp(v, a, b):
    return a if v < a else (b if v > b else v)


def lerp(a, b, t):
    return a + (b - a) * t


def approach(v, target, step):
    if v < target:
        return min(target, v + step)
    return max(target, v - step)


def ease_out(t):
    t = clamp(t, 0, 1)
    return 1 - (1 - t) ** 3


def ease_in(t):
    t = clamp(t, 0, 1)
    return t * t * t


def ease_io(t):
    t = clamp(t, 0, 1)
    return t * t * (3 - 2 * t)


def vdist(ax, ay, bx, by):
    return math.hypot(ax - bx, ay - by)


def seg_point_dist(px, py, ax, ay, bx, by):
    """点到线段距离。"""
    abx, aby = bx - ax, by - ay
    l2 = abx * abx + aby * aby
    if l2 < 1e-9:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * abx + (py - ay) * aby) / l2
    t = max(0.0, min(1.0, t))
    return math.hypot(px - (ax + abx * t), py - (ay + aby * t))


def seg_intersect(a, b, c, d):
    """两线段是否相交。"""
    def ccw(p, q, r):
        return (r[1] - p[1]) * (q[0] - p[0]) > (q[1] - p[1]) * (r[0] - p[0])
    return (ccw(a, c, d) != ccw(b, c, d)) and (ccw(a, b, c) != ccw(a, b, d))


def bezier(p0, p1, p2, t):
    u = 1 - t
    return (u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0],
            u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1])


def bezier_pts(p0, p1, p2, n=14):
    return [bezier(p0, p1, p2, i / (n - 1)) for i in range(n)]


def edge_ctrl(a, b, bend=0.22):
    """边的控制点：垂直于连线方向弯一点，让图更好看。"""
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    dx, dy = b[0] - a[0], b[1] - a[1]
    l = math.hypot(dx, dy) or 1
    return (mx - dy / l * l * bend, my + dx / l * l * bend)


# ---------------------------------------------------------------- 字体
_IS_WIN = os.name == "nt"
_FONT_FILES = {
    (False, False): ["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyh.ttf",
                     "C:/Windows/Fonts/simhei.ttf", "C:/Windows/Fonts/deng.ttf"],
    (True, False):  ["C:/Windows/Fonts/msyhbd.ttc", "C:/Windows/Fonts/msyhbd.ttf",
                     "C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf"],
    (False, True):  ["C:/Windows/Fonts/consola.ttf", "C:/Windows/Fonts/consolab.ttf",
                     "C:/Windows/Fonts/msyh.ttc"],
    (True, True):   ["C:/Windows/Fonts/consolab.ttf", "C:/Windows/Fonts/consola.ttf",
                     "C:/Windows/Fonts/msyhbd.ttc"],
}
_font_cache = {}


@functools.lru_cache(maxsize=64)
def get_font(size, bold=False, mono=False):
    key = (size, bold, mono)
    if key in _font_cache:
        return _font_cache[key]
    path = None
    for p in _FONT_FILES[(bool(bold), bool(mono))]:
        if os.path.exists(p):
            path = p
            break
    if path:
        f = pygame.font.Font(path, size)
    else:
        f = pygame.font.SysFont("microsoftyahei", size, bold=bold)
    _font_cache[key] = f
    return f


@functools.lru_cache(maxsize=3000)
def text(s, size, color, bold=False, mono=False):
    # Consolas 没有中文字形：混排时自动退回中文字体
    if mono and any(ord(c) > 127 for c in str(s)):
        mono = False
    try:
        return get_font(size, bold, mono).render(s, True, color)
    except Exception:
        return get_font(size).render(str(s), True, color)


def blit_text(dst, s, pos, size, color, bold=False, mono=False,
              anchor="topleft", alpha=255, shadow=0):
    if len(color) == 4:
        alpha = min(alpha, color[3])
        color = color[:3]
    surf = text(str(s), size, color, bold, mono)
    if alpha < 255:
        surf = surf.copy()
        surf.set_alpha(alpha)
    r = surf.get_rect(**{anchor: (int(pos[0]), int(pos[1]))})
    if shadow:
        sh = text(str(s), size, (0, 0, 0), bold, mono)
        if alpha < 255:
            sh = sh.copy()
            sh.set_alpha(alpha)
        for ox, oy in ((-shadow, 0), (shadow, 0), (0, -shadow), (0, shadow)):
            dst.blit(sh, (r.x + ox, r.y + oy))
    dst.blit(surf, r)
    return r


def text_w(s, size, bold=False, mono=False):
    return text(str(s), size, WHITE, bold, mono).get_width()


# ---------------------------------------------------------------- 光晕
_GLOW_CACHE = {}
_GLOW_BASE = 56


def _make_glow(color, power):
    n = _GLOW_BASE
    s = pygame.Surface((n, n))
    s.fill((0, 0, 0))
    cx = cy = (n - 1) / 2
    rr = n / 2
    for y in range(n):
        for x in range(n):
            d = math.hypot(x - cx, y - cy) / rr
            if d >= 1:
                continue
            a = (1 - d) ** 2.4
            s.set_at((x, y), (int(color[0] * a * power),
                              int(color[1] * a * power),
                              int(color[2] * a * power)))
    return s


def glow(dst, x, y, radius, color, power=1.0):
    """加色光晕。radius 为目标屏幕半径。"""
    if radius <= 1:
        return
    key = (color, round(power, 2))
    spr = _GLOW_CACHE.get(key)
    if spr is None:
        spr = _make_glow(color, power)
        _GLOW_CACHE[key] = spr
    d = int(radius * 2)
    if d < 3:
        return
    img = pygame.transform.smoothscale(spr, (d, d))
    dst.blit(img, (int(x - radius), int(y - radius)), special_flags=pygame.BLEND_RGB_ADD)


def additive_line(dst, color, a, b, width=2):
    """在 dark 背景上用 additive 画线（先画暗边再画亮芯）。"""
    pygame.draw.line(dst, dim(color, 0.35), a, b, max(1, width + 2))


def vline_glow(dst, color, x, y0, y1, width=2):
    pygame.draw.line(dst, color, (x, y0), (x, y1), width)


# ---------------------------------------------------------------- 表面工具
def new_surf(w, h, alpha=True):
    return pygame.Surface((w, h), pygame.SRCALPHA if alpha else 0)


def panel(dst, rect, fill=PANEL, line=PANEL_LINE, radius=6, width=1, alpha=255):
    s = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
    pygame.draw.rect(s, with_alpha(fill, alpha), (0, 0, rect.w, rect.h),
                     border_radius=radius)
    if line:
        pygame.draw.rect(s, with_alpha(line, min(255, alpha + 20)),
                         (0, 0, rect.w, rect.h), width, border_radius=radius)
    dst.blit(s, rect.topleft)


def bracket(dst, rect, color, size=14, width=2, alpha=255):
    """四角括号，赛博 UI 用。"""
    c = with_alpha(color, alpha)
    x, y, w, h = rect
    for (cx, cy, dx, dy) in ((x, y, 1, 1), (x + w, y, -1, 1),
                             (x, y + h, 1, -1), (x + w, y + h, -1, -1)):
        pygame.draw.line(dst, c, (cx, cy), (cx + dx * size, cy), width)
        pygame.draw.line(dst, c, (cx, cy), (cx, cy + dy * size), width)


def dashed_line(dst, color, a, b, dash=9, gap=7, width=2, alpha=255):
    c = with_alpha(color, alpha)
    ax, ay = a
    bx, by = b
    total = math.hypot(bx - ax, by - ay)
    if total < 1e-3:
        return
    ux, uy = (bx - ax) / total, (by - ay) / total
    d = 0.0
    while d < total:
        e = min(d + dash, total)
        pygame.draw.line(dst, c, (ax + ux * d, ay + uy * d),
                         (ax + ux * e, ay + uy * e), width)
        d = e + gap


def bar(dst, rect, frac, color, bg=(24, 29, 39), radius=3, border=None):
    pygame.draw.rect(dst, bg, rect, border_radius=radius)
    f = clamp(frac, 0, 1)
    if f > 0:
        r = pygame.Rect(rect.x, rect.y, max(1, int(rect.w * f)), rect.h)
        pygame.draw.rect(dst, color, r, border_radius=radius)
        glow(dst, r.centerx, r.centery, max(r.w, r.h) * 0.6, color, 0.25)
    if border:
        pygame.draw.rect(dst, border, rect, 1, border_radius=radius)


def hex_points(cx, cy, r, rot=0.0, n=6):
    return [(cx + math.cos(rot + i * math.tau / n) * r,
             cy + math.sin(rot + i * math.tau / n) * r) for i in range(n)]


def ring(dst, color, cx, cy, r, width=2, alpha=255, segs=48):
    if r < 1:
        return
    pygame.draw.circle(dst, with_alpha(color, alpha), (int(cx), int(cy)),
                       int(r), width)
