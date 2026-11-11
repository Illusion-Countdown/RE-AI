# -*- coding: utf-8 -*-
"""卡牌：牌库、抽卡、手牌、施放。

加一张新卡 = 在 data.CARDS 里加一条 + 在文件末尾写一个 @effect 函数。
不用改 cast()。
"""
import math
import random

import config
from config import DRAW_INTERVAL, HAND_MAX
from core.entities import Bullet
from data import CARDS

EFFECTS = {}


def effect(name):
    def deco(fn):
        EFFECTS[name] = fn
        return fn
    return deco


# ---------------------------------------------------------------- 牌库

def passive_ids() -> set:
    return {cid for cid, c in CARDS.items() if c["kind"] == "passive"}


def draw_interval(state) -> float:
    """抽卡间隔。缓存卡会加速。"""
    speed_up = sum(
        CARDS[cid]["power"] for cid in state.memory.active_cards()
        if CARDS[cid]["kind"] == "passive" and CARDS[cid]["effect"] == "draw_speed"
    )
    return DRAW_INTERVAL / (1.0 + speed_up)


def drawable(state) -> list:
    """能从牌库里抽的卡：已放置、未禁用、不在手上、不在冷却。"""
    hand = set(state.hand)
    out = []
    for cid in state.memory.active_cards():
        card = CARDS[cid]
        if card["kind"] == "passive":
            continue
        if cid in hand:
            continue
        if state.cooldowns.get(cid, 0) > 0:
            continue
        out.append(cid)
    return out


def draw_one(state) -> str:
    pool = drawable(state)
    if not pool:
        return ""
    cid = random.choice(pool)
    state.hand.append(cid)
    state.emit("draw", card=cid)
    return cid


def update(state, dt):
    """每帧推进抽卡计时。"""
    if state.over:
        return

    state.draw_timer += dt

    # 捡到的卡包：立刻抽
    while state.pending_cards > 0 and len(state.hand) < HAND_MAX:
        state.pending_cards -= 1
        if not draw_one(state):
            break

    if len(state.hand) >= HAND_MAX:
        state.draw_timer = 0.0
        return

    if state.draw_timer >= draw_interval(state):
        state.draw_timer -= draw_interval(state)
        draw_one(state)

    # 冷却走时
    for cid in list(state.cooldowns):
        state.cooldowns[cid] = max(0.0, state.cooldowns[cid] - dt)


# ---------------------------------------------------------------- 施放

def cast(state, card_id) -> bool:
    """打出一张手牌。返回是否成功。"""
    if card_id not in state.hand:
        state.log(f"手上没有 {card_id}")
        return False

    card = CARDS[card_id]
    if card["kind"] == "passive":
        state.log(f"{card['name']} 是被动卡，不能施放")
        return False

    handler = EFFECTS.get(card["effect"])
    if handler is None:
        raise ValueError(f"卡 {card_id} 的效果 {card['effect']} 没实现")

    state.hand.remove(card_id)
    state.cooldowns[card_id] = card["cd"]
    state.emit("cast", card=card_id)
    handler(state, card)
    state.log(f"释放 {card['name']}")
    return True


# ================================================================
# 效果实现。全部是"空间/时间"效果，没有纯数值技能。
# ================================================================

@effect("mark")
def _mark(state, card):
    """标记最近的敌人，它死亡时爆炸。"""
    from core.battle import attack_range, nearest_enemy

    target = nearest_enemy(state, max_range=attack_range(state) * 1.6)
    if target is None:
        return
    target.marked = True
    state.emit("mark", uid=target.uid)


@effect("pierce")
def _pierce(state, card):
    """朝最近敌人打一发穿透弹。"""
    from core.battle import attack_power, nearest_enemy, norm

    target = nearest_enemy(state)
    if target is None:
        return
    p = state.player
    dx, dy = norm(target.x - p.x, target.y - p.y)
    state.bullets.append(Bullet(
        x=p.x, y=p.y,
        vx=dx * 900, vy=dy * 900,
        damage=attack_power(state) * card["power"],
        radius=9, life=1.5, pierce=True,
    ))


@effect("ring")
def _ring(state, card):
    """以自己为中心的一圈冲击波。"""
    from core.battle import attack_power, damage_enemy, dist

    p = state.player
    radius = 170
    for e in list(state.enemies):
        if e.alive and dist(p.x, p.y, e.x, e.y) <= radius + e.radius:
            damage_enemy(state, e, attack_power(state) * card["power"], "ring")
    state.emit("ring", x=p.x, y=p.y, radius=radius)


@effect("slow")
def _slow(state, card):
    """范围内的敌人减速。"""
    from core.battle import dist

    p = state.player
    radius = 240
    n = 0
    for e in state.enemies:
        if e.alive and dist(p.x, p.y, e.x, e.y) <= radius:
            e.slow_timer = 3.0
            n += 1
    state.emit("slow", x=p.x, y=p.y, radius=radius, count=n)


@effect("spread")
def _spread(state, card):
    """朝目标方向扇形打出 6 发。"""
    from core.battle import attack_power, nearest_enemy, norm

    p = state.player
    target = nearest_enemy(state)
    if target is None:
        base = random.uniform(0, math.tau)
    else:
        dx, dy = norm(target.x - p.x, target.y - p.y)
        base = math.atan2(dy, dx)

    dmg = attack_power(state) * card["power"]
    for i in range(6):
        ang = base + (i - 2.5) * 0.18
        state.bullets.append(Bullet(
            x=p.x, y=p.y,
            vx=math.cos(ang) * 700, vy=math.sin(ang) * 700,
            damage=dmg, radius=5, life=0.9,
        ))


@effect("draw_speed")
def _draw_speed(state, card):
    """被动：在 draw_interval() 里生效，这里什么都不做。"""
    return
