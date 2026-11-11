# -*- coding: utf-8 -*-
"""所有内容数据。

先写成 Python dict，不上 JSON —— 原型阶段改起来最快。
等玩法定稿再挪到 data/*.json。
"""

# ================= 角色 =================
CHARACTERS = {
    "deepquest": {
        "id": "deepquest",
        "name": "深索 R1",
        "company": "deepseek",
        "lang": "C",
        "engine": "unity",
        "hp": 100,
        "speed": 150,
        "desc": "慢、疼、远程。站着不动的炮台。",
    },
    "gml": {
        "id": "gml",
        "name": "知谱 GML",
        "company": "zhipu",
        "lang": "Python",
        "engine": "godot",
        "hp": 110,
        "speed": 180,
        "desc": "快、轻、贴脸。走 A 流。",
    },
}

# ================= 语言 =================
# atk: 伤害倍率   rate: 攻速倍率   range: 基础射程
# beats: 克制哪种敌人类型（×1.3）   loses_to: 被哪种克（×0.8）
LANGUAGES = {
    "C": {
        "name": "C",
        "atk": 1.50,
        "rate": 0.80,
        "range": 220,
        "beats": "hardware",
        "loses_to": "memory",
    },
    "Python": {
        "name": "Python",
        "atk": 0.80,
        "rate": 1.15,
        "range": 200,
        "beats": "data",
        "loses_to": "concurrency",
    },
}

# ================= 引擎 =================
# form: ranged / melee
ENGINES = {
    "unity": {
        "name": "Unity",
        "form": "ranged",
        "range_mult": 1.00,
        "rate_mult": 1.00,
        "dmg_mult": 1.00,
        "desc": "远程 · 单体 · 均衡",
    },
    "godot": {
        "name": "Godot",
        "form": "melee",
        "range_mult": 0.40,
        "rate_mult": 1.40,
        "dmg_mult": 0.95,
        "desc": "近战 · 单体 · 快",
    },
}

# ================= 算法卡 =================
# cells: 占几格    cd: 冷却（打出后开始算）
CARDS = {
    "hash": {
        "name": "哈希", "cells": 1, "cd": 4.0, "kind": "active",
        "effect": "mark", "power": 1.0,
        "desc": "标记最近的敌人；它死亡时爆炸。",
    },
    "binary": {
        "name": "二分查找", "cells": 1, "cd": 6.0, "kind": "active",
        "effect": "pierce", "power": 2.2,
        "desc": "朝最近敌人打出一条穿透激光。",
    },
    "bfs": {
        "name": "BFS", "cells": 2, "cd": 8.0, "kind": "active",
        "effect": "ring", "power": 1.8,
        "desc": "以你为中心扩散一圈冲击波。",
    },
    "prune": {
        "name": "剪枝", "cells": 2, "cd": 8.0, "kind": "active",
        "effect": "slow", "power": 0.6,
        "desc": "范围内敌人减速 3 秒。",
    },
    "divide": {
        "name": "分治", "cells": 4, "cd": 10.0, "kind": "active",
        "effect": "spread", "power": 0.7,
        "desc": "朝前方扇形打出 6 发小弹。",
    },
    "cache": {
        "name": "缓存", "cells": 1, "cd": 0.0, "kind": "passive",
        "effect": "draw_speed", "power": 0.15,
        "desc": "抽卡速度 +15%。",
    },
}

# ================= 敌人 =================
ENEMIES = {
    "bug": {
        "id": "bug", "name": "Bug", "hp": 10, "speed": 95,
        "damage": 4, "radius": 12, "type": "data",
        "special": None,
    },
    "beast": {
        "id": "beast", "name": "编译错误巨兽", "hp": 40, "speed": 45,
        "damage": 14, "radius": 26, "type": "hardware",
        "special": "smash_memory",   # 每 6 秒打碎一格内存
    },
}

# ================= 地图 =================
# 2 层 × 2 节点 + 汇合 + Boss
NODES = {
    "c0": {"label": "c0 初始化", "type": "start", "layer": 0},
    "c1": {"label": "硬件层 · 战斗", "type": "combat", "layer": 1},
    "c2": {"label": "硬件层 · 事件", "type": "event", "layer": 1},
    "c3": {"label": "硬件层 · 汇合", "type": "junction", "layer": 2},
    "c4": {"label": "内核层 · 战斗", "type": "combat", "layer": 3},
    "c5": {"label": "内核层 · 精英", "type": "elite", "layer": 3},
    "c6": {"label": "内核层 · 汇合", "type": "junction", "layer": 4},
    "c7": {"label": "deploy Boss", "type": "boss", "layer": 5},
}

EDGES = {
    "c0": ["c1", "c2"],
    "c1": ["c3"],
    "c2": ["c3"],
    "c3": ["c4", "c5"],
    "c4": ["c6"],
    "c5": ["c6"],
    "c6": ["c7"],
    "c7": [],
}

# 每个节点打完给什么（原型简化：战斗给卡，事件给容量）
NODE_REWARDS = {
    "combat": {"kind": "card"},
    "elite": {"kind": "rare_card"},
    "event": {"kind": "cells"},
    "boss": {"kind": "none"},
}
