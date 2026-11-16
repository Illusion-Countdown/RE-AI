# -*- coding: utf-8 -*-
from memory_run.const import CYAN, MAGENTA, PURPLE, AMBER, GREEN, RED, GOLD, TEAL, BLUE, WHITE, DIM

CARD_DEFS = {
    "CUT": {
        "cn": "单剪", "en": "CUT", "shape": (1, 2), "color": CYAN,
        "target": "edge", "rarity": 0, "work": 1,
        "desc": "消耗 1 工作内存，按住左键划过引用线，剪断划到的第一条边；引用归零会触发 GC 级联。",
        "up": "一次划过剪断前 2 条边；仍然只消耗 1 工作内存。",
    },
    "LINK": {
        "cn": "硬链", "en": "LINK", "shape": (1, 2), "color": BLUE,
        "target": "two", "rarity": 0, "work": 0,
        "desc": "从 A 拖到 B，建立强引用。可从自己连向敌人：它停火并分摊伤害；不会把它锚在内存里。",
        "up": "建立强引用时额外获得 1 点工作内存。",
    },
    "WEAK": {
        "cn": "弱观测", "en": "WEAK", "shape": (1, 1), "color": PURPLE,
        "target": "two", "rarity": 0, "work": 0,
        "desc": "标记目标：它受到的伤害 +35%，对玩家造成的伤害 -35%；不计入 refcount。",
        "up": "同时标记两个目标。",
    },
    "CLIP": {
        "cn": "连剪", "en": "CLIP", "shape": (1, 3), "color": TEAL,
        "target": "node", "rarity": 1, "work": 0,
        "desc": "点一个对象，剪断它的全部入边。",
        "up": "剪断全部入边，并返还 1 点工作内存。",
    },
    "SWEEP": {
        "cn": "横扫", "en": "SWEEP", "shape": (2, 1), "color": GREEN,
        "target": "area", "rarity": 1, "work": 0,
        "desc": "在鼠标处横扫，剪断半径 150 内最多 3 条边。",
        "up": "最多剪断 5 条边。",
    },
    "WEAKEN": {
        "cn": "弱化", "en": "WEAKEN", "shape": (1, 1), "color": PURPLE,
        "target": "edge", "rarity": 1, "work": 0,
        "desc": "把一条强引用降级为弱引用，refcount 立刻 -1。",
        "up": "一次降级 2 条强引用。",
    },
    "ALIAS": {
        "cn": "别名", "en": "ALIAS", "shape": (2, 2), "color": MAGENTA,
        "target": "two", "rarity": 1, "work": 2,
        "desc": "6 秒内两个对象共享血池，伤害与死亡同步。",
        "up": "共享持续 8 秒。",
    },
    "VOID": {
        "cn": "空转", "en": "CAST<void>", "shape": (2, 2), "color": WHITE,
        "target": "node", "rarity": 1, "work": 2,
        "desc": "剥掉析构器，眩晕 2 秒，并让出边悬空 2 秒。",
        "up": "眩晕 3 秒，悬空 3 秒。",
    },
    "TRUNC": {
        "cn": "截断", "en": "CAST<int>", "shape": (2, 2), "color": AMBER,
        "target": "node", "rarity": 1, "work": 2,
        "desc": "剥掉析构器，禁止重建，并对周围造成 34 伤害。",
        "up": "范围伤害提高到 50。",
    },
    "DELAY": {
        "cn": "延迟剪", "en": "DELAY CUT", "shape": (1, 1), "color": CYAN,
        "target": "edge", "rarity": 1, "work": 0,
        "desc": "3 秒后自动剪断这条边。可以提前离场。",
        "up": "2 秒后剪断 2 条边。",
    },
    "REFLECT": {
        "cn": "反射剪", "en": "REFLECT", "shape": (1, 2), "color": GOLD,
        "target": "edge", "rarity": 2, "work": 0,
        "desc": "剪断一条边，并把目标的析构伤害反射给最近的敌人。",
        "up": "反射伤害翻倍。",
    },
    "STEAL": {
        "cn": "引用窃取", "en": "STEAL", "shape": (1, 2), "color": GREEN,
        "target": "edge", "rarity": 2, "work": 1,
        "desc": "剪断一条敌方边，并把这条引用收归自己（不触发 refcount 下降）。",
        "up": "偷走后返还 1 点工作内存。",
    },
    "COMPRESS": {
        "cn": "压缩", "en": "COMPRESS", "shape": (1, 2), "color": RED,
        "target": "self", "rarity": 2, "work": 0,
        "desc": "把工作内存拉到 90%，8 秒内伤害 +30%；之后双倍回落。",
        "up": "12 秒 +40% 伤害，拉到 95%。",
    },
    "ECC": {
        "cn": "纠错码", "en": "ECC", "shape": (1, 1), "color": GREEN,
        "target": "dead", "rarity": 2, "work": 0,
        "desc": "修复 1 个坏死格，或清除 1 个泄漏。画质会随之回升。",
        "up": "修复 2 个坏死格。",
    },
    "LOSSY": {
        "cn": "有损爆发", "en": "LOSSY BURST", "shape": (2, 3), "color": GOLD,
        "target": "area", "rarity": 2, "work": 3,
        "desc": "半径 180 内造成 80 伤害；永久毁掉 2 个空闲格。",
        "up": "120 伤害，毁掉 3 个空闲格。",
    },
    "DOWN": {
        "cn": "降采样", "en": "DOWNSAMPLE", "shape": (2, 2), "color": CYAN,
        "target": "area", "rarity": 1, "work": 2,
        "desc": "敌人与子弹减速 30%，持续 5 秒；画质上限 -20。",
        "up": "减速 40% 持续 7 秒，画质 -15。",
    },
}

SHAPE_NAMES = {(1, 1): "1×1", (1, 2): "1×2", (1, 3): "1×3",
               (2, 1): "2×1", (2, 2): "2×2", (2, 3): "2×3",
               (3, 2): "3×2"}

RARITY_CN = ["基础", "进阶", "稀有"]
