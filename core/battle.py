# -*- coding: utf-8 -*-
"""战斗模拟：移动、自动攻击、子弹、敌人、拾取。

这个文件只负责"世界怎么动"，不负责"玩家做了什么决定"。
玩家决策在 actions.py。
"""
import math
import random

import config
from config import ARENA, BASE_ATTACK, BASE_RATE
from core.entities import Bullet, Drop, Enemy
from data import ENEMIES, ENGINES, LANGUAGES


# ---------------------------------------------------------------- 数学

def dist(ax, ay, bx, by) -> float:
    return math.hypot(bx - ax, by - ay)


def norm(dx, dy):
    d = math.hypot(dx, dy)
    if d < 1e-6:
        return 0.0, 0.0
    return dx / d, dy / d


def clamp_arena(x, y, r):
    x0, y0, w, h = ARENA
    return (min(max(x, x0 + r), x0 + w - r),
            min(max(y, y0 + r), y0 + h - r))


# ---------------------------------------------------------------- 属性计算

def attack_interval(state) -> float:
    """两次普攻之间隔多久。语言 × 引擎 决定。"""
    lang = LANGUAGES[state.player.lang]
    eng = ENGINES[state.player.engine]
    return 1.0 / (BASE_RATE * lang["rate"] * eng["rate_mult"])


def attack_range(state) -> float:
    lang = LANGUAGES[state.player.lang]
    eng = ENGINES[state.player.engine]
    return lang["range"] * eng["range_mult"]


def attack_power(state) -> float:
    lang = LANGUAGES[state.player.lang]
    eng = ENGINES[state.player.engine]
    return BASE_ATTACK * lang["atk"] * eng["dmg_mult"]


def counter_coef(state, enemy) -> float:
    """语言克制：克 ×1.3，被克 ×0.8。"""
    lang = LANGUAGES[state.player.lang]
    if enemy.etype == lang["beats"]:
        return 1.3
    if enemy.etype == lang["loses_to"]:
        return 0.8
    return 1.0


def nearest_enemy(state, max_range=None, from_pos=None):
    px, py = from_pos or (state.player.x, state.player.y)
    best, best_d = None, 1e9
    for e in state.enemies:
        if not e.alive:
            continue
        d = dist(px, py, e.x, e.y)
        if max_range is not None and d > max_range:
            continue
        if d < best_d:
            best, best_d = e, d
    return best


# ---------------------------------------------------------------- 生成

def spawn_enemy(state, kind, x=None, y=None, hp_mult=1.0, size_mult=1.0):
    """在战场边缘刷一个敌人。腐化会强化它。"""
    data = ENEMIES[kind]
    x0, y0, w, h = ARENA
    if x is None or y is None:
        side = random.choice("tblr")
        if side == "t":
            x, y = random.uniform(x0, x0 + w), y0 + 20
        elif side == "b":
            x, y = random.uniform(x0, x0 + w), y0 + h - 20
        elif side == "l":
            x, y = x0 + 20, random.uniform(y0, y0 + h)
        else:
            x, y = x0 + w - 20, random.uniform(y0, y0 + h)

    scale = 1.0 + state.corruption
    hp = data["hp"] * scale * hp_mult
    e = Enemy(
        uid=state.next_uid(),
        kind=data["name"] if hp_mult > 1 else kind,
        x=x, y=y,
        hp=hp, max_hp=hp,
        speed=data["speed"],
        damage=data["damage"] * scale,
        radius=data["radius"] * size_mult,
        etype=data["type"],
        special=("boss" if hp_mult >= 10 else (data["special"] or "")),
        base_speed=data["speed"],
    )
    state.enemies.append(e)
    return e


# ---------------------------------------------------------------- 伤害

def damage_enemy(state, enemy, dmg, source="hit"):
    if not enemy.alive:
        return
    enemy.hp -= dmg
    state.emit("damage", uid=enemy.uid, value=round(dmg, 1))

    if enemy.hp <= 0:
        enemy.hp = 0
        _on_death(state, enemy)


def _on_death(state, enemy):
    state.emit("death", uid=enemy.uid)
    state.kills += 1

    # 被标记的敌人死亡时爆炸
    if enemy.marked:
        for other in state.enemies:
            if other is enemy or not other.alive:
                continue
            if dist(enemy.x, enemy.y, other.x, other.y) <= 90:
                damage_enemy(state, other, 25.0, source="mark")

    # 掉东西
    r = random.random()
    if r < 0.08:
        state.drops.append(Drop("swap", enemy.x, enemy.y))
    elif r < 0.16:
        state.drops.append(Drop("card", enemy.x, enemy.y))


def damage_player(state, dmg):
    if state.invuln > 0 or not state.player.alive:
        return
    state.player.hp -= dmg
    state.invuln = 0.5
    state.emit("hurt", value=round(dmg, 1))
    if state.player.hp <= 0:
        state.player.hp = 0


# ---------------------------------------------------------------- 每帧

def update(state, dt):
    if state.over:
        return

    dt = min(dt, 0.05)          # 防止卡顿时穿模

    # 提交后的全场冻结：敌人不动
    if state.freeze > 0:
        state.freeze = max(0.0, state.freeze - dt)
        _update_bullets(state, dt)
        state.invuln = max(0.0, state.invuln - dt)
        state.time += dt
        return

    _update_player(state, dt)
    _update_attack(state, dt)
    _update_bullets(state, dt)
    _update_enemies(state, dt)
    _update_drops(state, dt)

    state.invuln = max(0.0, state.invuln - dt)
    state.time += dt

    if state.player.hp <= 0:
        state.emit("player_down")
        state.player_down = True


def _update_player(state, dt):
    p = state.player
    dx, dy = state.move
    mx, my = norm(dx, dy)
    p.moving = (mx != 0 or my != 0)
    if not p.moving:
        return
    p.x += mx * p.speed * dt
    p.y += my * p.speed * dt
    p.x, p.y = clamp_arena(p.x, p.y, p.radius)


def _update_attack(state, dt):
    p = state.player
    p.attack_timer -= dt
    if p.attack_timer > 0:
        return

    rng = attack_range(state)
    target = nearest_enemy(state, max_range=rng)
    if target is None:
        p.attack_timer = 0.05       # 没目标，下一帧再看
        return

    p.attack_timer = attack_interval(state)
    dmg = attack_power(state) * counter_coef(state, target)
    eng = ENGINES[p.engine]

    if eng["form"] == "melee":
        # 近战：瞬时命中
        damage_enemy(state, target, dmg, source="melee")
        state.emit("melee", x=target.x, y=target.y)
    else:
        dx, dy = norm(target.x - p.x, target.y - p.y)
        state.bullets.append(Bullet(
            x=p.x, y=p.y, vx=dx * 620, vy=dy * 620, damage=dmg))
        state.emit("shoot", x=p.x, y=p.y)


def _update_bullets(state, dt):
    alive = []
    for b in state.bullets:
        b.x += b.vx * dt
        b.y += b.vy * dt
        b.life -= dt

        hit = None
        for e in state.enemies:
            if not e.alive or e.uid in b.hits:
                continue
            if dist(b.x, b.y, e.x, e.y) <= e.radius + b.radius:
                hit = e
                break

        if hit is not None:
            damage_enemy(state, hit, b.damage, source="bullet")
            b.hits.add(hit.uid)
            if not b.pierce:
                continue          # 不加入 alive = 消失

        if b.life > 0:
            alive.append(b)
    state.bullets = alive


def _update_enemies(state, dt):
    p = state.player

    # 拆内存是全局节流：不管有几只巨兽，每 8 秒最多碎 1 格。
    # 不节流的话，5 只巨兽 30 秒就能把你的牌库拆光。
    state.smash_cd = max(0.0, state.smash_cd - dt)
    if state.smash_cd <= 0:
        beasts = [e for e in state.enemies if e.alive and e.special == "smash_memory"]
        if beasts:
            broken_card = state.memory.smash()
            state.smash_cd = 10.0
            state.emit("memory_smash", card=broken_card)
            if broken_card:
                state.log(f"{beasts[0].kind} 打碎了内存：{broken_card} 被禁用")
            else:
                state.log(f"{beasts[0].kind} 打碎了一格内存")

    for e in state.enemies:
        if not e.alive:
            continue

        e.slow_timer = max(0.0, e.slow_timer - dt)
        _tick_boss(state, e, dt)

        dx, dy = norm(p.x - e.x, p.y - e.y)
        e.x += dx * e.speed * e.coef * dt
        e.y += dy * e.speed * e.coef * dt

        if dist(e.x, e.y, p.x, p.y) <= e.radius + p.radius:
            damage_player(state, e.damage)


def _tick_boss(state, e, dt):
    """Boss 三阶段：越残血越快，中期还会召唤。"""
    if e.special != "boss":
        return

    ratio = e.hp / e.max_hp if e.max_hp else 0.0
    if ratio > 0.66:
        e.phase, target = 1, 1.0
    elif ratio > 0.33:
        e.phase, target = 2, 1.35
    else:
        e.phase, target = 3, 1.7

    e.speed = e.base_speed * target

    # 二阶段开始召唤小怪
    if e.phase >= 2:
        e.phase_timer += dt
        if e.phase_timer >= 4.0:
            e.phase_timer = 0.0
            spawn_enemy(state, "bug", x=e.x + random.uniform(-60, 60),
                        y=e.y + random.uniform(-60, 60))
            state.emit("boss_summon")


def _update_drops(state, dt):
    p = state.player
    keep = []
    for d in state.drops:
        if dist(d.x, d.y, p.x, p.y) <= p.radius + d.radius + 6:
            if d.kind == "swap":
                state.memory.expand(5)
                state.log("捡到 swap：内存 +5 格")
                state.emit("pickup", kind="swap")
            elif d.kind == "card":
                state.pending_cards += 1
                state.log("捡到第三方库：手牌 +1 抽")
                state.emit("pickup", kind="card")
            continue
        keep.append(d)
    state.drops = keep
