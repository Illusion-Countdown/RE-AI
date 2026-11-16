# -*- coding: utf-8 -*-
from .rooms import TUTORIAL_COUNT, TUTORIALS, RUN_ROOMS

# ---------------------------------------------------------------- 关卡顺序
def room_for_step(step):
    """0..21：教程 4 + 正式 18（5 区 15 战 + 5 Boss）。"""
    if step < TUTORIAL_COUNT:
        return TUTORIALS[step]
    idx = step - TUTORIAL_COUNT
    if idx < len(RUN_ROOMS):
        return RUN_ROOMS[idx]
    return None


def zone_of(step):
    if step < TUTORIAL_COUNT:
        return 0
    r = room_for_step(step)
    return r["zone"] if r else 0


ZONE_NAMES = {
    0: ("教学沙盒", "TUTORIAL SANDBOX"),
    1: ("引用荒原", "REFERENCE WASTES"),
    2: ("并发回廊", "CONCURRENCY CORRIDOR"),
    3: ("类型深渊", "TYPE ABYSS"),
    4: ("碎片浅滩", "FRAGMENT SHALLOWS"),
    5: ("内核深渊", "KERNEL ABYSS"),
}
