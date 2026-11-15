# -*- coding: utf-8 -*-
"""输入管线测试：完全走鼠标/键盘事件路径，验证拖拽、剪线、强转菜单。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame
pygame.init()

from dangle.const import *
from dangle.content import BODIES
from dangle.battle import Battle, Run
from dangle.model import STRONG, WEAK
from dangle.screens import REWARD_CW

OK, BAD = [], []


def check(c, m):
    (OK if c else BAD).append(m)
    print(("  [ok] " if c else "  [FAIL] ") + m)


b = Battle(Run(BODIES[0]), 0)
b.state = "playing"
b.intro_t = 0
b.max_slices = 99
b.slices = 99

scope = [n for n in b.graph.nodes if n.name == "SCOPE"][0]
sent = [n for n in b.graph.nodes if n.kind == "SENTINEL"][0]
m1 = [n for n in b.graph.nodes if n.name == "MINION.02"][0]
m2 = [n for n in b.graph.nodes if n.name == "MINION.03"][0]


def edge(a, c, kind=STRONG):
    for e in b.graph.edges:
        if e.alive and e.src is a and e.dst is c and e.kind == kind:
            return e
    return None


def drag(tool, a, c):
    b.choose_tool(tool)
    p0 = (int(a.x), int(a.y))
    p1 = (int(c.x), int(c.y))
    b.on_mouse_down(p0, 1, 0)
    b.on_mouse_move(p1)
    b.on_mouse_up(p1, 1)


# 1. CUT：点击边
e = edge(sent, m1)
pts = e.points(12)
mid = pts[6]
b.choose_tool(1)
b.on_mouse_down((int(mid[0]), int(mid[1])), 1, 0)
b.on_mouse_up((int(mid[0]), int(mid[1])), 1)
b.fx.hitstop = 0
b.update(1 / 60, {"mvx": 0, "mvy": 0, "plan": False, "dash": False})
check(not m1.alive, "鼠标点击引用线 -> 剪断 -> GC 擦除")

# 2. LINK：从玩家拖到 sentinel
drag(0, b.player_node, sent)
check(edge(b.player_node, sent) is not None, "拖拽玩家->哨兵 建立强引用")
check(b.is_held(sent), "被持有的目标")
init_atk = sent.timers.get("atk", 9)
b.fx.hitstop = 0
b.update(1 / 60, {"mvx": 0, "mvy": 0, "plan": False, "dash": False})
check(b.graph.refcount(sent) == 2, "哨兵 refcount = 2")

# 3. WEAK：拖玩家 -> m2
drag(2, b.player_node, m2)
we = edge(b.player_node, m2, WEAK)
check(we is not None, "拖拽建立 WEAK 边")
check(b.graph.refcount(m2) == 1, "弱引用不计入 refcount")

# 4. ALIAS：m2 与 sentinel
b.heap = 5
hp_before = m2.hp + sent.hp
drag(3, m2, sent)
check(m2.alias is not None and sent.alias is m2.alias, "拖拽建立别名组")
check(abs(m2.alias.hp - hp_before) < 1, "共享血池 = 双方之和")
b.apply_damage(m2, 10, WHITE)
check(m2.alias.hp < hp_before, "对一侧造成伤害 -> 血池下降")

# 5. CAST：点击哨兵，打开菜单，点 NULL
b.choose_tool(4)
p = (int(sent.x), int(sent.y))
b.on_mouse_down(p, 1, 0)
check(b.cast_menu is not None and b.cast_menu["node"] is sent, "点击节点打开强转菜单")
# 计算菜单项坐标
x = min(max(sent.x + 50, 12), W - 300)
y = min(max(sent.y - 40, 100), H - 160)
opt = pygame.Rect(int(x) + 8, int(y) + 46, 286 - 16, 28)
b.on_mouse_down((opt.centerx, opt.centery), 1, 0)
b.cast_menu = None
check(sent.stun > 0, "点击 NULL 选项 -> 目标眩晕")

# 6. 剪线 slash：划过剩下的边
b.choose_tool(1)
b.slices = 99
target_edges = [e for e in b.graph.edges if e.alive and e.kind == STRONG]
if target_edges:
    e = target_edges[0]
    pts = e.points(10)
    a = (pts[2][0] - 40, pts[2][1] - 40)
    c = (pts[2][0] + 40, pts[2][1] + 40)
    b.on_mouse_down(a, 1, 0)
    b.on_mouse_move((a[0] + 20, a[1] + 20))
    b.on_mouse_move((a[0] + 40, a[1] + 40))
    b.on_mouse_up(c, 1)
    check(not e.alive, "划过引用线 -> 剪断")

# 7. WRITE
b.choose_tool(0)
b.write_cd = 0
b.slices = 99
tgt = [n for n in b.graph.nodes if n.alive and n.hostile and not n.hijacked]
if tgt:
    n = tgt[0]
    n.x, n.y = b.px + 40, b.py
    b.mouse = (n.x, n.y)
    hp0 = n.hp if not n.alias else n.alias.hp
    b.write_attack()
    hp1 = n.hp if not n.alias else n.alias.hp
    check(hp1 < hp0, "右键/写入造成伤害")

print("\nPASS %d / FAIL %d" % (len(OK), len(BAD)))
sys.exit(1 if BAD else 0)
