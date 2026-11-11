# -*- coding: utf-8 -*-
"""命令行演示：跑完一整局，验证核心链路。

运行：
    python tools/demo.py

它不画任何东西，只证明这条链路是通的：
    推进 → 战斗 → 奖励 → 回退 → 分支 → 合并 → Boss → 结算
"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import DT
from core import actions, battle, cards
from core.state import GameState
from data import CARDS

random.seed(7)


# ---------------------------------------------------------------- 自动驾驶

def autopilot(state):
    """保持中距离：太近后退，太远前进，刚好就绕圈。"""
    e = battle.nearest_enemy(state)
    if e is None:
        return (0.0, 0.0)

    rng = battle.attack_range(state)
    p = state.player
    d = battle.dist(p.x, p.y, e.x, e.y)
    dx, dy = battle.norm(e.x - p.x, e.y - p.y)

    if d < rng * 0.55:
        return (-dx, -dy)
    if d > rng * 0.85:
        return (dx, dy)
    return (-dy, dx)


# ---------------------------------------------------------------- 战斗

def run_battle(state, seconds, spawn_kinds, boss=False):
    """跑一段战斗：自动走位、自动放卡、危急时自动 commit。"""
    if boss:
        battle.spawn_enemy(state, "beast", hp_mult=12, size_mult=2.2)
        state.log("Boss 出现：它由你欠下的债构成")

    t = 0.0
    spawn_timer = 0.0
    cast_timer = 2.0
    report_timer = 0.0
    auto_commits = 0

    while t < seconds and not state.over and not state.player_down:
        spawn_timer -= DT
        if spawn_timer <= 0:
            spawn_timer = max(0.45, 1.3 - t * 0.015)
            battle.spawn_enemy(state, random.choice(spawn_kinds))

        cast_timer -= DT
        if cast_timer <= 0 and state.hand:
            cast_timer = 4.5
            cards.cast(state, random.choice(state.hand))

        # 危急时自动提交：但至少给 revert 留 2 个名额
        if (auto_commits < 2 and state.quota > 2
                and state.player.hp < state.player.max_hp * 0.55
                and len(state.alive_enemies()) >= 4):
            auto_commits += 1
            actions.commit(state)

        state.move = autopilot(state)
        battle.update(state, DT)
        cards.update(state, DT)
        t += DT

        report_timer += DT
        if report_timer >= 6.0:
            report_timer = 0.0
            st = state.memory.stats()
            print(f"    [{t:5.1f}s] 击杀 {state.kills:3d}  "
                  f"敌 {len(state.alive_enemies()):2d}  "
                  f"手牌 {len(state.hand)}  "
                  f"内存 {st['used']:2d}/{st['total']}（碎 {st['broken']}）  "
                  f"HP {state.player.hp:.0f}")

    state.enemies.clear()
    state.bullets.clear()
    state.drops.clear()

    if state.player_down:
        state.over = True
        state.win = False
        state.log("进程终止：稳定性归零")


# ---------------------------------------------------------------- 主流程

def play(state):
    """按顺序跑节点。死亡就立刻返回，后面的步骤不再执行。"""
    # ---------- 节点 1 ----------
    print("\n" + "-" * 64)
    actions.advance(state, "c1")
    print(f"【{state.map.head}】{state.map.label(state.map.head)}")
    run_battle(state, 28, ["bug"] * 10 + ["beast"])
    if state.over:
        return
    actions.finish_node(state)

    # ---------- 回退 ----------
    print("\n" + "-" * 64)
    print("【测试 revert：发现奖励不适合，退回重选】")
    q0 = state.quota
    err = actions.revert(state, "c0")
    if err:
        print(f"    失败：{err}")
        return
    print(f"    名额 {q0} → {state.quota}    腐化 {state.corruption:.0%}")
    print(f"    路由 {state.map.ascii()}")

    # ---------- 改走事件 ----------
    print("\n" + "-" * 64)
    actions.advance(state, "c2")
    print(f"【{state.map.head}】{state.map.label(state.map.head)}")
    actions.finish_node(state)
    print(f"    内存扩容到 {state.memory.stats()['total']} 格")

    # ---------- 分支 ----------
    print("\n" + "-" * 64)
    print("【测试 branch：花一个名额去看另一条路】")
    q0 = state.quota
    err = actions.branch(state)
    print(f"    {err if err else f'名额 {q0} → {state.quota}，支线暂存 {state.branch_loot}'}")

    # ---------- 主线 ----------
    print("\n" + "-" * 64)
    for node in ("c3", "c4"):
        actions.advance(state, node)
        print(f"【{state.map.head}】{state.map.label(state.map.head)}")
    run_battle(state, 30, ["bug"] * 8 + ["beast"] * 2)
    if state.over:
        return
    actions.finish_node(state)

    # ---------- 合并 ----------
    print("\n" + "-" * 64)
    print("【测试 merge：两条线的收获合到一起】")
    err = actions.merge(state)
    print(f"    {err if err else '合并完成'}")

    # ---------- Boss ----------
    print("\n" + "-" * 64)
    actions.advance(state, "c6")
    actions.advance(state, "c7")
    print(f"【{state.map.head}】{state.map.label(state.map.head)}")
    print(f"    腐化 {state.corruption:.0%} → Boss 血量 ×{1 + state.corruption:.2f}")
    run_battle(state, 45, ["bug"] * 4, boss=True)
    if state.player_down:
        state.over = True
        state.win = False
    else:
        actions.finish_node(state)


def report(state):
    print("\n" + "=" * 64)
    print("结算")
    print("=" * 64)
    print(f"  结果       : {'✔ 通关' if state.win else '✖ 失败'}")
    print(f"  击杀       : {state.kills}")
    print(f"  剩余名额   : {state.quota}")
    print(f"  腐化       : {state.corruption:.0%}")
    print(f"  孤儿节点   : {state.map.orphans or '无'}")
    print(f"  路由       : {state.map.ascii()}")
    st = state.memory.stats()
    print(f"  内存       : {st['used']}/{st['total']} 已用，"
          f"{st['broken']} 碎，{st['disabled']} 张卡被禁用")
    print(f"  存活卡牌   : {[CARDS[c]['name'] for c in state.memory.active_cards()]}")

    print("\n  最后 12 条日志：")
    for line in state.logs[-12:]:
        print(f"    {line}")
    print()


def main():
    print("=" * 64)
    print("版本控制 3.2 · 命令行演示（第 1 批：核心链路）")
    print("=" * 64)

    state = GameState.new("deepquest")
    print(f"\n角色：深索 R1   语言 C   引擎 Unity")
    st = state.memory.stats()
    print(f"内存：{st['used']}/{st['total']} 格   名额：{state.quota}   "
          f"牌库：{[CARDS[c]['name'] for c in state.memory.active_cards()]}")

    play(state)
    report(state)


if __name__ == "__main__":
    main()
