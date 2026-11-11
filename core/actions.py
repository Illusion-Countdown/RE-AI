# -*- coding: utf-8 -*-
"""玩家能做的高层动作：推进、回退、分支、合并、提交、领奖励。

这是唯一改 GameState 的地方（除了战斗内部）。
"""
import random

import config
from core import battle, cards
from core.state import card_shape
from data import CARDS, NODES


# ---------------------------------------------------------------- 推进

def advance(state, node=None) -> str:
    """走到下一个节点。node 为空时自动选择第一个子节点。"""
    kids = state.map.children()
    if not kids:
        return ""
    if node is None:
        node = kids[0]
    if node not in kids:
        return f"{node} 不可达"

    state.map.advance(node)
    state.node_cleared = False
    state.log(f"进入 {state.map.label(node)}（{state.map.node_type(node)}）")
    state.emit("enter_node", node=node)
    return ""


def finish_node(state) -> list:
    """一个节点打完了：发奖励，返回获得的东西。"""
    node = state.map.head
    ntype = state.map.node_type(node)
    got = []

    if ntype == "combat":
        got.append(_grant_card(state, rare=False))
    elif ntype == "elite":
        got.append(_grant_card(state, rare=True))
    elif ntype == "event":
        state.memory.expand(5)
        state.log("事件：内存 +5 格")
        got.append("cells+5")
    elif ntype == "boss":
        state.over = True
        state.win = state.player.hp > 0
        if state.win:
            state.log("打上 v1.0，版本发布")

    state.node_cleared = True
    got = [g for g in got if g]
    if got:
        state.log("获得：" + "、".join(str(g) for g in got))

    # 节点之间：修 1 格内存，回一口血
    if not state.over and state.player.hp > 0:
        if state.memory.repair(1):
            state.log("运维修复了 1 格内存")
        heal = state.player.max_hp * 0.35
        state.player.hp = min(state.player.max_hp, state.player.hp + heal)
    return got


def _grant_card(state, rare=False):
    pool = [c for c in CARDS
            if c not in state.memory.placed and c not in state.branch_loot]
    if not pool:
        return ""
    if rare and "divide" in pool:
        cid = "divide"
    else:
        cid = random.choice(pool)
    cw, ch = card_shape(CARDS[cid])
    if state.memory.place(cid, cw, ch):
        state.log(f"装载新卡：{CARDS[cid]['name']}（{CARDS[cid]['cells']} 格）")
    else:
        state.pending_cards += 1
        state.log(f"内存放不下 {CARDS[cid]['name']}，转进手牌")
    return cid


# ---------------------------------------------------------------- 提交（战斗中）

def commit(state) -> str:
    """冻结全场：敌人停止行动 1.5 秒，并变成地形。"""
    if state.quota <= 0:
        return "没有名额了"
    state.quota -= 1
    state.freeze = 1.5

    frozen = 0
    for e in state.enemies:
        if e.alive:
            e.hp = 0
            frozen += 1
    state.enemies = [e for e in state.enemies if e.alive]

    state.emit("commit", count=frozen)
    state.log(f"★ 提交：冻结 {frozen} 个敌人，名额剩 {state.quota}")
    return ""


# ---------------------------------------------------------------- 回退

def revert(state, node) -> str:
    """退回历史节点。代价：名额、腐化、孤儿。"""
    if state.quota <= 0:
        return "没有名额了"
    if not state.map.can_revert_to(node):
        return f"没法退到 {node}"

    dropped = state.map.revert_to(node)
    state.quota -= 1
    state.corruption += config.CORRUPTION_STEP

    # 回滚构筑：丢一张卡（演示用最简单的规则）
    if state.memory.placed:
        lost = random.choice(list(state.memory.placed))
        state.memory.remove(lost)
        state.log(f"回滚：丢失 {CARDS[lost]['name']}")

    state.hand.clear()
    state.enemies.clear()
    state.bullets.clear()
    state.drops.clear()
    state.player.hp = state.player.max_hp
    state.node_cleared = False

    state.emit("revert", node=node, dropped=dropped)
    state.log(f"↩ 回退到 {node}，腐化 {state.corruption:.0%}，"
              f"孤儿 {state.map.orphans}")
    return ""


# ---------------------------------------------------------------- 分支

def branch(state) -> str:
    """开分支：去侦察同层的另一个节点，把收获暂存。"""
    if state.quota <= 0:
        return "没有名额了"

    sib = state.map.sibling(state.map.head)
    if sib is None:
        return "这个节点没有兄弟节点，分支不了"

    state.quota -= 1
    state.map.mark_scouted(sib)

    # 侦察收益：一条分支配一张卡
    pool = [c for c in CARDS if c not in state.memory.placed
            and c not in state.branch_loot]
    loot = random.choice(pool) if pool else ""
    if loot:
        state.branch_loot.append(loot)

    state.emit("branch", node=sib, loot=loot)
    state.log(f"⑂ 开分支侦察 {sib}：暂存 {CARDS[loot]['name'] if loot else '空'}"
              f"（名额剩 {state.quota}）")
    return ""


def merge(state) -> str:
    """合并分支。普通收获全收，稀有冲突二选一。"""
    if not state.branch_loot:
        return "没有可合并的分支"

    # 演示规则：支线只留一张，且必须牺牲主线的一张（冲突）
    got = state.branch_loot.pop()
    cw, ch = card_shape(CARDS[got])
    ok = state.memory.place(got, cw, ch)

    if ok:
        state.log(f"⑃ 合并：支线卡「{CARDS[got]['name']}」进入内存")
    else:
        state.pending_cards += 1
        state.log(f"⑃ 合并：内存没位置，「{CARDS[got]['name']}」转进手牌")

    state.emit("merge", card=got)
    return ""


# ---------------------------------------------------------------- 战斗驱动

def damage_memory_preview(state) -> str:
    st = state.memory.stats()
    return f"内存 {st['used']}/{st['total']}  碎 {st['broken']}  禁用 {st['disabled']}"
